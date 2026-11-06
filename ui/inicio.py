"""Componentes de presentación de inicio y continuidad."""
import gradio as gr


def construir_inicio(temas, formatos, niveles):
    with gr.Tab("Inicio y Mi ruta"):
        with gr.Row():
            meta = gr.Dropdown(temas, value="Backend con Node.js", label="Meta de aprendizaje")
            formato = gr.Radio(formatos, value="Visual", label="Formato preferido")
            nivel = gr.Dropdown(niveles, value="Principiante", label="Nivel")
        with gr.Row():
            iniciar = gr.Button("Iniciar simulación", variant="primary")
            aplicar_meta = gr.Button("Guardar meta y preferencias")
            reiniciar_btn = gr.Button("Reiniciar simulación", variant="stop")
        estado_ui = gr.Markdown("Sin progreso cargado")
        ruta_ui = gr.Markdown("Selecciona una meta y comienza.")
        aviso = gr.Markdown()
    return meta, formato, nivel, iniciar, aplicar_meta, reiniciar_btn, estado_ui, ruta_ui, aviso
