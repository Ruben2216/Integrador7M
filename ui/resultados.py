"""Formularios reales de evaluación y presentación del resultado calificado."""
import gradio as gr

from calificador import obtener_ejercicios_laboratorio
from integracion_calificador import preguntas_seguimiento, variantes_seguimiento


def construir_resultados():
    variantes = variantes_seguimiento()
    variante_inicial = variantes[0]
    preguntas = preguntas_seguimiento(variante_inicial)
    ejercicios = obtener_ejercicios_laboratorio()
    with gr.Tab("Resultados"):
        gr.Markdown(
            "### Evaluación real de PostgreSQL\n"
            "Las respuestas pasan por `calificador.py`; el formulario no decide la aprobación."
        )
        tipo = gr.Radio(
            ["Actividad de seguimiento", "Laboratorio diagnóstico"],
            value="Actividad de seguimiento", label="Tipo de actividad",
        )
        with gr.Group(visible=False) as grupo_laboratorio:
            gr.Markdown("#### Laboratorio diagnóstico · 4 ejercicios SQL")
            respuestas_laboratorio = [
                gr.Code(label=f"{ej['id']} · {ej['concepto']} — {ej['enunciado']}",
                        language="sql", lines=4)
                for ej in ejercicios
            ]
        with gr.Group(visible=True) as grupo_seguimiento:
            gr.Markdown("#### Actividad de seguimiento · 5 preguntas")
            variante = gr.Dropdown(variantes, value=variante_inicial, label="Variante")
            respuestas_seguimiento = [
                gr.Radio(choices=pregunta["opciones"], label=pregunta["enunciado"], value=None)
                for pregunta in preguntas
            ]
        tiempo = gr.Number(value=300, label="Tiempo de respuesta (segundos)", minimum=0)
        with gr.Row():
            reintentar = gr.Button("Reintentar", variant="secondary")
            enviar = gr.Button("Calificar y guardar intento", variant="primary")
        resultado_ui = gr.Markdown()
        ruta_resultado = gr.Markdown()
        resultado_estado = gr.Markdown()
    return (tipo, variante, respuestas_laboratorio, respuestas_seguimiento, tiempo,
            reintentar, enviar, resultado_ui, ruta_resultado, resultado_estado,
            grupo_laboratorio, grupo_seguimiento)


def actualizar_tipo(tipo):
    es_laboratorio = tipo == "Laboratorio diagnóstico"
    return gr.update(visible=es_laboratorio), gr.update(visible=not es_laboratorio)


def actualizar_preguntas(variante):
    preguntas = preguntas_seguimiento(variante)
    return [gr.update(label=p["enunciado"], choices=p["opciones"], value=None) for p in preguntas]


def presentar_resultado(estado, resultado, retroalimentacion=None):
    intento = next(i for i in estado["intentos"] if str(i["id"]) == str(resultado["id"]))
    criterios_ok = intento.get("criterios_cumplidos", [])
    criterios_no = intento.get("criterios_incumplidos", [])
    if isinstance(criterios_ok, (list, tuple)):
        criterios_ok = ", ".join(map(str, criterios_ok)) or "Ninguno"
    if isinstance(criterios_no, (list, tuple)):
        criterios_no = ", ".join(map(str, criterios_no)) or "Ninguno"
    salida = (
        f"## Resultado: {intento['tema']}\n\n"
        f"- **Actividad:** {intento['tipo_actividad']}\n"
        f"- **Puntaje:** {intento['puntaje']} / {intento.get('puntaje_maximo', 5)} "
        f"({intento.get('puntaje_proporcion', 0):.0%})\n"
        f"- **Estado:** {'Aprobado' if intento['aprobado'] else 'Pendiente'}\n"
        f"- **Criterios cumplidos:** {criterios_ok}\n"
        f"- **Criterios incumplidos:** {criterios_no}\n"
        f"- **Conceptos con error:** {', '.join(intento['conceptos_con_error']) or 'Ninguno'}\n"
    )
    if intento.get("variante"):
        salida += f"- **Variante:** {intento['variante']}\n"
    salida += "\n" + renderizar_retroalimentacion(retroalimentacion)
    return salida


def renderizar_retroalimentacion(retroalimentacion):
    """Misma presentación para la retroalimentación local (Plan B) y la de Gemini (Plan A)."""
    if not retroalimentacion:
        return "**Retroalimentación:** todavía no disponible."
    if not isinstance(retroalimentacion, dict):
        return "**Retroalimentación:** formato no reconocido; se conserva la calificación."
    partes = []
    origen = retroalimentacion.get("origen")
    if origen:
        partes.append("#### Retroalimentación")
        if origen == "gemini":
            modelo = retroalimentacion.get("modelo")
            partes.append(f"_Generada con Gemini{f' ({modelo})' if modelo else ''}._")
        else:
            partes.append("_Basada en la rúbrica de evaluación._")
        if retroalimentacion.get("motivo_respaldo"):
            motivo = str(retroalimentacion["motivo_respaldo"]).rstrip(".")
            partes.append(f"_Explicación con IA no disponible. Motivo: {motivo}._")
    if retroalimentacion.get("concepto_nombre"):
        partes.append(f"**Concepto a reforzar:** {retroalimentacion['concepto_nombre']}")
    for clave, etiqueta in (("acierto", "Fortaleza"),
                            ("mejora", "Área de mejora"),
                            ("comentario", "Comentario"),
                            ("pista", "Sugerencia")):
        if retroalimentacion.get(clave):
            partes.append(f"**{etiqueta}:** {retroalimentacion[clave]}")
    recurso = retroalimentacion.get("recurso")
    if isinstance(recurso, dict):
        titulo, enlace = recurso.get("titulo", "Material recomendado"), recurso.get("enlace")
        detalles = ", ".join(x for x in (recurso.get("formato"), recurso.get("fuente")) if x)
        texto = f"[{titulo}]({enlace})" if enlace else titulo
        partes.append(f"**Material recomendado:** {texto}" + (f" — {detalles}" if detalles else ""))
    elif isinstance(recurso, str) and recurso.strip():
        partes.append(f"**Material recomendado:** {recurso}")
    return "\n\n".join(partes) if partes else "**Retroalimentación:** no recibida."
