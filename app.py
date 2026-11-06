"""Aplicación local de continuidad y resultados. Ejecutar: python app.py"""
from pathlib import Path

import gradio as gr

from recomendador import FORMATOS, NIVELES, TEMA_A_NODO, Recomendador
from simulacion import (cambiar_meta, comenzar, configurar_recomendador,
                        guardar_intento_demo, inicializar, preparar_reintento,
                        reiniciar, registrar_resultado_calificado)
from ui.inicio import construir_inicio
from ui.resultados import construir_resultados

BASE = Path(__file__).resolve().parent
rec = Recomendador(str(BASE / "telemetria_estudiantes_simulada.csv"),
                   str(BASE / "grafo_conocimiento.json"))
configurar_recomendador(rec)
TEMAS = list(TEMA_A_NODO)


with gr.Blocks(title="Recomendador personalizado de rutas") as demo:
    gr.Markdown("# Sistema Inteligente de Recomendación\nDemo local de inicio, continuidad y resultados. El archivo `progreso.json` mantiene el estado de una sola simulación.")
    (meta, formato, nivel, iniciar, aplicar_meta, reiniciar_btn,
     estado_ui, ruta_ui, aviso) = construir_inicio(TEMAS, FORMATOS, NIVELES)
    (intento_id, tema_resultado, tipo, puntaje, minutos, conceptos,
     reintentar, guardar, resultado_ui, ruta_resultado,
     resultado_estado) = construir_resultados(TEMAS)

    iniciar.click(comenzar, [meta, formato, nivel], [iniciar, ruta_ui, estado_ui, aviso])
    aplicar_meta.click(comenzar, [meta, formato, nivel], [iniciar, ruta_ui, estado_ui, aviso])
    reintentar.click(preparar_reintento, [tema_resultado], [intento_id, resultado_estado])
    guardar.click(guardar_intento_demo, [intento_id, tema_resultado, tipo, puntaje, minutos, conceptos], [resultado_ui, ruta_resultado, resultado_estado])
    reiniciar_btn.click(reiniciar, outputs=[iniciar, ruta_ui, estado_ui, aviso])
    demo.load(inicializar, outputs=[meta, formato, nivel, iniciar, ruta_ui, estado_ui, aviso])


if __name__ == "__main__":
    demo.launch()
