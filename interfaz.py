"""Interfaz Gradio del recomendador.

El montaje vive en ``ui.aplicacion``; este módulo conserva el contrato público
que usa ``app.py`` (``construir_interfaz``) y mantiene la separación entre
punto de arranque, lógica y presentación.
"""
from ui.aplicacion import construir_interfaz

__all__ = ["construir_interfaz"]
