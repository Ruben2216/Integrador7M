"""Lanza la interfaz gráfica (Gradio) del recomendador. Uso:  python app.py"""
from recomendador import Recomendador, construir_interfaz

rec = Recomendador("telemetria_estudiantes_simulada.csv", "grafo_conocimiento.json")
construir_interfaz(rec).launch()
