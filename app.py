"""Punto de arranque: instancia el motor y monta las vistas de la simulación."""
import argparse
from pathlib import Path

import gradio as gr

from motor import Motor
from recomendador import FORMATOS, NIVELES, TEMA_A_NODO
from simulacion import (cambiar_meta, comenzar, configurar_motor, inicializar,
                        calificar_y_registrar, preparar_reintento, reiniciar)
from ui.inicio import construir_inicio
from ui.resultados import (actualizar_preguntas, actualizar_tipo,
                           construir_resultados)

TEMAS = list(TEMA_A_NODO)


def construir_app(motor):
    configurar_motor(motor)
    with gr.Blocks(title="Recomendador personalizado de rutas") as demo:
        gr.Markdown(
            "# Sistema Inteligente de Recomendación\n"
            "La ruta se calcula con el motor A* y el progreso local de la simulación."
        )
        (meta, formato, nivel, iniciar, aplicar_meta, reiniciar_btn,
         estado_ui, ruta_ui, aviso) = construir_inicio(TEMAS, FORMATOS, NIVELES)
        (tipo_actividad, variante, respuestas_lab, respuestas_seg, tiempo,
         reintentar, enviar, resultado_ui, ruta_resultado, resultado_estado,
         grupo_laboratorio, grupo_seguimiento) = construir_resultados()

        iniciar.click(comenzar, [meta, formato, nivel], [iniciar, ruta_ui, estado_ui, aviso])
        aplicar_meta.click(cambiar_meta, [meta, formato, nivel], [ruta_ui, estado_ui, aviso])
        reiniciar_btn.click(reiniciar, outputs=[iniciar, ruta_ui, estado_ui, aviso])
        tipo_actividad.change(actualizar_tipo, [tipo_actividad], [grupo_laboratorio, grupo_seguimiento])
        variante.change(actualizar_preguntas, [variante], respuestas_seg)
        reintentar.click(
            preparar_reintento,
            [tipo_actividad, variante], [variante, resultado_estado],
        )
        enviar.click(
            calificar_y_registrar,
            [tipo_actividad, variante, *respuestas_lab, *respuestas_seg, tiempo],
            [resultado_ui, ruta_resultado, resultado_estado],
        )
        demo.load(inicializar, outputs=[meta, formato, nivel, iniciar, ruta_ui, estado_ui, aviso])
    return demo


def main():
    parser = argparse.ArgumentParser(description="Recomendador de rutas de aprendizaje")
    parser.add_argument("--no-browser", action="store_true", help="No abrir navegador automáticamente")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--share", action="store_true")
    args = parser.parse_args()

    print("[app.py] Inicializando motor de recomendación…")
    motor = Motor()
    print("[app.py] Motor listo.")
    construir_app(motor).launch(
        server_name="127.0.0.1", server_port=args.port,
        inbrowser=not args.no_browser, share=args.share,
    )


if __name__ == "__main__":
    main()
