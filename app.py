"""
Punto de entrada Gradio. Integra el Motor real con la interfaz general del
integrante 2 y la persistencia/calificación de los integrantes 3 y 4.

Uso: python app.py [--no-browser] [--port 7860]
"""
import argparse
import os
import sys
from pathlib import Path

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from motor import Motor
from interfaz import construir_interfaz
import simulacion
from simulacion import configurar_motor


def main():
    parser = argparse.ArgumentParser(description="Recomendador de rutas de aprendizaje")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--share", action="store_true")
    parser.add_argument(
        "--progress-file",
        type=Path,
        help="Archivo local para el progreso (útil para aislar una demostración o prueba).",
    )
    args = parser.parse_args()

    print("[app.py] Inicializando motor de recomendación…")
    motor = Motor()
    if args.progress_file:
        from progreso import AlmacenProgreso

        simulacion.almacen = AlmacenProgreso(args.progress_file)
    configurar_motor(motor)
    print("[app.py] Motor listo.")
    demo = construir_interfaz(motor)
    demo.launch(
        server_name="127.0.0.1",
        server_port=args.port,
        inbrowser=not args.no_browser,
        share=args.share,
    )


if __name__ == "__main__":
    main()
