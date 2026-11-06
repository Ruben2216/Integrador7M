"""Coordinación de continuidad y registro de resultados de la simulación."""
from pathlib import Path
from uuid import uuid4

from adaptador_demo import construir_resultado_demo, construir_retroalimentacion_demo
from progreso import AlmacenProgreso, ErrorProgreso, temas_acreditados
from recomendador import NODO_A_TEMA, TEMA_A_NODO, ruta_a_estrella
from ui.resultados import presentar_resultado


BASE = Path(__file__).resolve().parent
almacen = AlmacenProgreso(BASE / "progreso.json")


def configurar_recomendador(recomendador):
    global rec
    rec = recomendador


def markdown_ruta(estado):
    acreditados = [TEMA_A_NODO[t] for t in temas_acreditados(estado)]
    meta = TEMA_A_NODO[estado["meta"]]
    ruta, costo, explorados = ruta_a_estrella(rec.grafo, acreditados, meta, estado["nivel"])
    if ruta is None:
        return "No se encontró una ruta para esta meta.", ""
    if not ruta:
        return f"## Meta completada\n\n**{estado['meta']}** ya está acreditada. Elige otra meta para continuar.", "Meta completada"
    detalle = []
    for i, nodo in enumerate(ruta, 1):
        recursos = rec.ordenar_recursos(nodo, estado["formato_preferido"])
        detalle.append(f"{i}. **{NODO_A_TEMA[nodo]}** — {recursos[0]['recurso']} ({recursos[0]['formato']})")
    return (f"## Ruta hacia {estado['meta']}\n\n" + "\n".join(detalle) +
            f"\n\nCosto A*: {costo} · estados explorados: {explorados}"), "Ruta actualizada"


def inicializar():
    try:
        estado = almacen.cargar()
        ruta, estado_meta = markdown_ruta(estado) if estado["simulacion_activa"] else ("Selecciona una meta y comienza.", "Sin simulación")
        label = "Continuar aprendizaje" if estado["simulacion_activa"] else "Iniciar simulación"
        import gradio as gr
        return (gr.update(value=estado["meta"]), gr.update(value=estado["formato_preferido"]),
                gr.update(value=estado["nivel"]), label, ruta, estado_meta,
                f"Estado local: {len(estado['intentos'])} intento(s), {len(estado['temas_acreditados'])} tema(s) acreditado(s).")
    except ErrorProgreso as exc:
        import gradio as gr
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
        return "Continuar aprendizaje", ruta, estado_meta, f"Preferencias guardadas. {len(estado['temas_acreditados'])} tema(s) acreditado(s)."
    except (ErrorProgreso, ValueError) as exc:
        return "Error", "", "Error", str(exc)


def registrar_resultado_calificado(resultado, retroalimentacion=None):
    """Punto de entrada del calificador real: persiste y presenta, no califica."""
    try:
        estado = almacen.guardar_intento(resultado)
        ruta, _ = markdown_ruta(estado)
        salida = presentar_resultado(estado, resultado, retroalimentacion)
        return salida, ruta, f"Guardado. Intentos totales: {len(estado['intentos'])}; acreditados: {len(estado['temas_acreditados'])}."
    except (ErrorProgreso, ValueError, TypeError, OverflowError, StopIteration) as exc:
        return f"No se pudo guardar: {exc}", "", "Error de persistencia"


def guardar_intento_demo(id_intento, tema, tipo, puntaje, minutos, conceptos):
    try:
        resultado = construir_resultado_demo(id_intento, tema, tipo, puntaje, minutos, conceptos)
        return registrar_resultado_calificado(resultado, construir_retroalimentacion_demo())
    except (ValueError, TypeError, OverflowError) as exc:
        return f"No se pudo preparar el intento de demostración: {exc}", "", "Datos de demostración inválidos"


def preparar_reintento(tema):
    nuevo_id = f"demo-{uuid4().hex[:12]}"
    return nuevo_id, f"Reintento preparado para **{tema}**. Aún no se agregó al historial; se guardará al enviar el intento."


def cambiar_meta(meta):
    try:
        estado = almacen.cambiar_meta(meta)
        ruta, status = markdown_ruta(estado)
        return ruta, status, "Meta cambiada; historial y acreditaciones conservados."
    except (ErrorProgreso, ValueError) as exc:
        return "", "Error", str(exc)


def reiniciar():
    try:
        almacen.reiniciar()
        return "Iniciar simulación", "Selecciona una meta y comienza.", "Estado inicial", "Simulación reiniciada explícitamente; historial anterior eliminado."
    except ErrorProgreso as exc:
        return "Error", "", "Error", str(exc)
