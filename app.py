"""
app.py — Punto de entrada principal de la aplicación.

Uso:
    python app.py              # abre la interfaz Gradio en el navegador
    python app.py --no-browser # solo inicia el servidor, sin abrir el navegador

El módulo motor.py expone el Motor (árbol + grafo + A*).
Este archivo carga el motor UNA vez y lo conecta a la interfaz Gradio.
"""
import argparse
import os
import sys

# ── Asegura que el directorio del proyecto esté en el path ──────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from motor import Motor
from interfaz import construir_interfaz

# ── Argumentos de línea de comandos ─────────────────────────────────────────
parser = argparse.ArgumentParser(description="Recomendador de rutas de aprendizaje")
parser.add_argument(
    "--no-browser", action="store_true",
    help="No abrir el navegador automáticamente al iniciar."
)
parser.add_argument(
    "--port", type=int, default=7860,
    help="Puerto donde se escucha la interfaz (por defecto 7860)."
)
parser.add_argument(
    "--share", action="store_true",
    help="Generar enlace público temporal con Gradio Share."
)
args = parser.parse_args()

# ── Carga del motor (una sola vez) ───────────────────────────────────────────
print("[app.py] Inicializando motor de recomendación…")
motor = Motor()
print("[app.py] Motor listo.")

# ── Interfaz Gradio ──────────────────────────────────────────────────────────
# La interfaz conecta el motor con la navegación, el grafo y las actividades.
demo = construir_interfaz(motor)

demo.launch(
    server_name="0.0.0.0",
    server_port=args.port,
    inbrowser=not args.no_browser,
    share=args.share,
)
