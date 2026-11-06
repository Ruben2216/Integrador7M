"""Coordinación de progreso, calificador real y motor A* del integrante 1."""
from pathlib import Path

import gradio as gr

from integracion_calificador import (calificar_laboratorio,
                                     calificar_seguimiento_real,
                                     preguntas_seguimiento,
                                     variantes_seguimiento)
from progreso import AlmacenProgreso, ErrorProgreso, temas_acreditados
from recomendador import TEMA_A_NODO
from ui.resultados import presentar_resultado

BASE = Path(__file__).resolve().parent
almacen = AlmacenProgreso(BASE / "progreso.json")
motor = None


def configurar_motor(instancia):
    global motor
    motor = instancia


def markdown_ruta(estado):
    if motor is None:
        raise RuntimeError("El motor del integrante 1 todavía no fue configurado")
    salida = motor.ruta_directa(temas_acreditados(estado), estado["meta"], estado["nivel"])
    if salida["estado_meta"] == "Meta completada":
        return (f"## Meta completada\n\n**{estado['meta']}** ya está acreditada. "
                "Elige otra meta para continuar."), "Meta completada"
    pasos = salida["ruta_pendiente"]
    if not pasos:
        return "No se encontró una ruta pendiente para esta meta.", salida["estado_meta"]
    detalle = "\n".join(f"{i}. **{tema}**" for i, tema in enumerate(pasos, 1))
    return (f"## Ruta hacia {estado['meta']}\n\n{detalle}\n\n"
            f"Siguiente tema: **{salida['siguiente_tema']}**"), salida["estado_meta"]


def inicializar():
    try:
        estado = almacen.cargar()
        ruta, estado_meta = markdown_ruta(estado) if estado["simulacion_activa"] else (
            "Selecciona una meta y comienza.", "Sin simulación"
        )
        boton = "Continuar aprendizaje" if estado["simulacion_activa"] else "Iniciar simulación"
        return (gr.update(value=estado["meta"]), gr.update(value=estado["formato_preferido"]),
                gr.update(value=estado["nivel"]), boton, ruta, estado_meta,
                f"Estado local: {len(estado['intentos'])} intento(s), "
                f"{len(estado['temas_acreditados'])} tema(s) acreditado(s).")
    except (ErrorProgreso, ValueError) as exc:
        return gr.update(), gr.update(), gr.update(), "Progreso ilegible", "", "Error", str(exc)


def comenzar(meta, formato, nivel):
    try:
        estado = almacen.cargar()
        if estado["simulacion_activa"]:
            estado.update(meta=meta, formato_preferido=formato, nivel=nivel)
            almacen.guardar(estado)
        else:
            estado = almacen.iniciar(meta, formato, nivel)
        ruta, estado_meta = markdown_ruta(estado)
        return "Continuar aprendizaje", ruta, estado_meta, "Preferencias y ruta actualizadas."
    except (ErrorProgreso, ValueError, RuntimeError) as exc:
        return "Error", "", "Error", str(exc)


def cambiar_meta(meta, formato, nivel):
    try:
        estado = almacen.cambiar_meta(meta)
        estado.update(formato_preferido=formato, nivel=nivel)
        estado = almacen.guardar(estado)
        ruta, estado_meta = markdown_ruta(estado)
        return ruta, estado_meta, "Meta cambiada; historial y acreditaciones conservados."
    except (ErrorProgreso, ValueError, RuntimeError) as exc:
        return "", "Error", str(exc)


def registrar_resultado_calificado(resultado, retroalimentacion=None):
    """Punto de entrada común: persiste resultado ya calificado y recalcula A*."""
    try:
        estado = almacen.guardar_intento(resultado)
        ruta, estado_meta = markdown_ruta(estado)
        presentacion = presentar_resultado(estado, resultado, retroalimentacion)
        return presentacion, ruta, (
            f"Guardado. Intentos: {len(estado['intentos'])}; "
            f"acreditados: {len(estado['temas_acreditados'])}; estado meta: {estado_meta}."
        )
    except (ErrorProgreso, ValueError, TypeError, OverflowError, StopIteration, RuntimeError) as exc:
        return f"No se registró el resultado: {exc}", "", "Error de registro"


def persistir_intento(resultado):
    """Guarda un resultado normalizado usando la actualización atómica del almacén."""
    return almacen.guardar_intento(resultado)


def calificar_y_registrar(tipo, variante, lab01, lab02, lab03, lab04,
                          seg01, seg02, seg03, seg04, seg05, tiempo):
    try:
        segundos = float(tiempo or 0)
        if tipo == "Laboratorio diagnóstico":
            from calificador import obtener_ejercicios_laboratorio
            ejercicios = obtener_ejercicios_laboratorio()
            respuestas = {ej["id"]: valor or "" for ej, valor in zip(
                ejercicios, (lab01, lab02, lab03, lab04)
            )}
            resultado = calificar_laboratorio(respuestas, segundos)
        elif tipo == "Actividad de seguimiento":
            preguntas = preguntas_seguimiento(variante)
            respuestas = {p["id"]: valor or "" for p, valor in zip(
                preguntas, (seg01, seg02, seg03, seg04, seg05)
            )}
            resultado = calificar_seguimiento_real(respuestas, segundos, variante)
        else:
            raise ValueError("Selecciona una actividad reconocida")
        return registrar_resultado_calificado(resultado)
    except (ValueError, TypeError, OverflowError, KeyError) as exc:
        return f"El calificador no pudo procesar las respuestas: {exc}", "", "Error de calificación"


def preparar_reintento(tipo, variante_actual):
    """Selecciona una variante equivalente sin añadir un intento al historial."""
    if tipo != "Actividad de seguimiento":
        return gr.update(value=variante_actual), "Reintento listo. No se guarda hasta enviar las respuestas."
    try:
        estado = almacen.cargar()
        usadas = [i.get("variante") for i in estado["intentos"] if i.get("variante")]
        disponible = [v for v in variantes_seguimiento() if v not in usadas]
        if not disponible:
            return gr.update(value=variante_actual), "Ya se usaron las variantes disponibles; el historial no cambió."
        nueva = disponible[0]
        return gr.update(value=nueva), f"Reintento preparado con **{nueva}**. Aún no se agregó al historial."
    except (ErrorProgreso, OSError, ValueError) as exc:
        return gr.update(value=variante_actual), f"No se pudo preparar el reintento: {exc}"


def reiniciar():
    try:
        almacen.reiniciar()
        return "Iniciar simulación", "Selecciona una meta y comienza.", "Estado inicial", "Simulación reiniciada explícitamente."
    except ErrorProgreso as exc:
        return "Error", "", "Error", str(exc)
