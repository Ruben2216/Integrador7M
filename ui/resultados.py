"""Componentes y formato de presentación de resultados."""
import gradio as gr


def construir_resultados(temas):
    with gr.Tab("Resultados"):
        gr.Markdown("### Resultado de actividad\nEl adaptador de prueba está separado en `adaptador_demo.py`. El punto de conexión para el calificador es `registrar_resultado_calificado(resultado, retroalimentacion=None)`: espera el intento ya calificado con `id`, `tema`, `tipo_actividad`, `puntaje`, `tiempo_segundos`, `conceptos_con_error` y `aprobado`.")
        with gr.Row():
            intento_id = gr.Textbox(value="demo-001", label="ID de intento")
            tema_resultado = gr.Dropdown(temas, value="Backend con Node.js", label="Tema evaluado")
            tipo = gr.Dropdown(["Laboratorio", "Diagnóstico", "Actividad de seguimiento"], value="Laboratorio", label="Tipo de actividad")
            puntaje = gr.Slider(0, 5, value=3, step=1, label="Puntaje")
            minutos = gr.Number(value=5, label="Tiempo (minutos)")
        conceptos = gr.Textbox(label="Conceptos con error (separados por coma)", value="JOIN")
        with gr.Row():
            reintentar = gr.Button("Reintentar", variant="secondary")
            guardar = gr.Button("Enviar intento de demostración", variant="primary")
        resultado_ui = gr.Markdown()
        ruta_resultado = gr.Markdown()
        resultado_estado = gr.Markdown()
    return (intento_id, tema_resultado, tipo, puntaje, minutos, conceptos,
            reintentar, guardar, resultado_ui, ruta_resultado, resultado_estado)


def renderizar_retroalimentacion(retroalimentacion):
    if not retroalimentacion:
        return "**Retroalimentación:** todavía no disponible."
    if not isinstance(retroalimentacion, dict):
        return "**Retroalimentación:** formato no reconocido; se conserva el resultado calificado."
    partes = []
    for campo, etiqueta in (("comentario", "Comentario"), ("pista", "Pista")):
        valor = retroalimentacion.get(campo)
        if valor:
            partes.append(f"**{etiqueta}:** {valor}")
    recurso = retroalimentacion.get("recurso")
    if isinstance(recurso, dict):
        titulo = recurso.get("titulo") or "Recurso recomendado"
        enlace = recurso.get("enlace")
        formato = recurso.get("formato")
        texto = f"[{titulo}]({enlace})" if enlace else titulo
        if formato:
            texto += f" ({formato})"
        partes.append(f"**Recurso:** {texto}")
    elif isinstance(recurso, str) and recurso.strip():
        partes.append(f"**Recurso:** {recurso}")
    return "\n\n".join(partes) if partes else "**Retroalimentación:** no se recibieron comentario, pista ni recurso."


def presentar_resultado(estado, resultado, retroalimentacion):
    ultima = next(i for i in estado["intentos"] if str(i["id"]) == str(resultado["id"]))
    maximo = ultima.get("puntaje_maximo", 5)
    return (f"## Resultado: {ultima['tema']}\n\n"
            f"- **Actividad:** {ultima['tipo_actividad']}\n- **Puntaje:** {ultima['puntaje']} / {maximo}\n"
            f"- **Estado:** {'Aprobado' if ultima['aprobado'] else 'Pendiente'}\n"
            f"- **Criterios:** {ultima.get('criterios_cumplidos', '—')}\n"
            f"- **Conceptos con error:** {', '.join(ultima['conceptos_con_error']) or 'Ninguno'}\n\n"
            f"{renderizar_retroalimentacion(retroalimentacion)}")
