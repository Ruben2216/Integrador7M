"""Verificación visual SIMULADA sobre la aplicación Gradio real.

Usa progreso temporal y sustituye únicamente el proveedor de explicación durante
la prueba: primera respuesta local por fallo y segunda respuesta de IA simulada.
Nunca llama a Gemini. Requiere Playwright como herramienta externa de pruebas.
Ejecutar desde la raíz: python scripts/verificar_retroalimentacion.py
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
PUERTO = 7873
URL = f"http://127.0.0.1:{PUERTO}"
SALIDA = RAIZ / "artifacts" / "retroalimentacion"


def servir():
    import gradio as gr
    import interfaz
    from motor import Motor
    from progreso import AlmacenProgreso
    import simulacion
    from ui.estilos import CSS

    llamadas = 0

    def explicacion_simulada(resultado, formato=None):
        nonlocal llamadas
        llamadas += 1
        local = interfaz.generar_retroalimentacion(resultado, formato)
        if llamadas == 1:
            return {**local, "motivo_respaldo": "Fallo SIMULADO: HTTP 503; modelo de prueba."}
        return {**local, "origen": "gemini", "modelo": "modelo-SIMULADO", "motivo_respaldo": None,
                "acierto": "Identificaste las condiciones en los casos resueltos correctamente.",
                "mejora": "Revisa el orden de las operaciones y contrasta cada resultado con el detalle del intento.",
                "pista": "Prueba **valores límite**: cero, números negativos y el último elemento de una lista.\n\n"
                         "Anota los valores paso a paso antes de ejecutar el código."}

    interfaz.GEMINI_ACTIVO = True
    interfaz.solicitar_explicacion = explicacion_simulada
    interfaz.estado_gemini = lambda: "Proveedor SIMULADO para verificación visual; sin solicitudes externas."
    with tempfile.TemporaryDirectory(prefix="retro-presentacion-") as temporal:
        simulacion.almacen = AlmacenProgreso(Path(temporal) / "progreso.json")
        motor = Motor()
        simulacion.configurar_motor(motor)
        demo = interfaz.construir_interfaz(motor)
        demo.launch(server_name="127.0.0.1", server_port=PUERTO, inbrowser=False,
                    theme=gr.themes.Base(), css=CSS)


def verificar():
    from playwright.sync_api import sync_playwright, expect
    from niveles import preguntas_nivel

    progreso = RAIZ / "progreso.json"
    hash_previo = hashlib.sha256(progreso.read_bytes()).hexdigest() if progreso.exists() else None
    SALIDA.mkdir(parents=True, exist_ok=True)
    registro = (SALIDA / "servidor.log").open("w", encoding="utf-8")
    servidor = subprocess.Popen([sys.executable, __file__, "--serve"], cwd=RAIZ,
                                stdout=registro, stderr=subprocess.STDOUT)
    resultados = []
    try:
        limite = time.monotonic() + 120
        while time.monotonic() < limite:
            try:
                with urlopen(URL, timeout=1) as respuesta:
                    if respuesta.status == 200:
                        break
            except OSError:
                if servidor.poll() is not None:
                    raise RuntimeError("El servidor terminó; consultar servidor.log")
                time.sleep(.3)
        else:
            raise RuntimeError("El servidor no inició; consultar servidor.log")

        with sync_playwright() as pw:
            chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
            browser = pw.chromium.launch(headless=True, executable_path=str(chrome) if chrome.exists() else None)
            page = browser.new_page(viewport={"width": 1366, "height": 768})
            page.goto(URL, wait_until="domcontentloaded")
            page.get_by_role("tab", name="Resultados", exact=True).click()
            feedback = page.locator("#feedback-view")
            (SALIDA / "dom-inicial.html").write_text(feedback.evaluate("el => el.outerHTML"), encoding="utf-8")
            expect(feedback.get_by_role("button", name="Pedir explicación con IA", exact=True)).to_be_disabled()
            expect(feedback.locator(".feedback-section")).to_have_count(0)

            def capturar(estado):
                for ancho, alto in ((1366, 768), (1536, 864), (390, 844)):
                    page.set_viewport_size({"width": ancho, "height": alto})
                    feedback.scroll_into_view_if_needed()
                    # Estabiliza el layout, sin temporizadores en la aplicación.
                    page.evaluate("() => new Promise(requestAnimationFrame)")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Desbordamiento de página"
                    assert feedback.evaluate("el => el.scrollWidth <= el.clientWidth + 1"), "Desbordamiento de retroalimentación"
                    columnas = feedback.locator(".feedback-layout:visible")
                    if columnas.count() and feedback.locator(".feedback-resource:visible").count():
                        principal = feedback.locator(".feedback-main:visible").bounding_box()
                        recurso = feedback.locator(".feedback-resource:visible").bounding_box()
                        if ancho == 390:
                            assert recurso["y"] >= principal["y"] + principal["height"] - 1
                        else:
                            assert recurso["x"] > principal["x"]
                    feedback.screenshot(path=str(SALIDA / f"{estado}-{ancho}x{alto}.png"))
                    resultados.append(f"{estado} {ancho}x{alto}: sin desbordamiento")

            capturar("01-inicial-deshabilitado")
            page.set_viewport_size({"width": 1366, "height": 768})
            page.get_by_role("tab", name="Actividad", exact=True).click()
            page.get_by_role("radio", name="Lógica de Programación · niveles", exact=True).check()
            preguntas = preguntas_nivel("Lógica de Programación", "basico")
            for indice, pregunta in enumerate(preguntas):
                # Intento simulado con un error, calificado por los callbacks reales.
                respuesta = pregunta["respuesta_correcta"] if indice != 1 else next(
                    opcion for opcion in pregunta["opciones"] if opcion != pregunta["respuesta_correcta"])
                page.get_by_role("radio", name=respuesta, exact=True).check()
                if indice < len(preguntas) - 1:
                    page.get_by_role("button", name="Siguiente", exact=True).click()
            page.get_by_role("button", name="Calificar nivel", exact=True).click()
            expect(feedback.get_by_text("Basada en la rúbrica", exact=True)).to_be_visible()
            pedir = feedback.get_by_role("button", name="Pedir explicación con IA", exact=True)
            expect(pedir).to_be_enabled()
            capturar("02-local-inicial-habilitado")
            pedir.click()
            expect(feedback.get_by_text("La explicación con IA no está disponible. Mostramos la retroalimentación de la rúbrica.", exact=True)).to_be_visible()
            expect(feedback.locator("#feedback-local")).to_be_hidden()
            expect(feedback.get_by_role("button", name="Reintentar explicación", exact=True)).to_be_enabled()
            assert not feedback.locator("details[open]").count()
            capturar("03-respaldo-simulado")
            feedback.get_by_role("button", name="Reintentar explicación", exact=True).click()
            expect(feedback.get_by_text("Generada con IA", exact=True)).to_be_visible()
            expect(feedback.get_by_role("button", name="Explicación con IA generada", exact=True)).to_be_disabled()
            expect(feedback.locator("strong").filter(has_text="valores límite")).to_be_visible()
            capturar("04-gemini-simulado")
            enlace = feedback.get_by_role("link", name="Abrir recurso")
            expect(enlace).to_have_attribute("href", __import__("re").compile(r"https?://"))
            enlace.focus()
            assert enlace.evaluate("el => el === document.activeElement")
            feedback.locator("#feedback-ai summary").focus()
            page.keyboard.press("Enter")
            expect(feedback.get_by_text("modelo-SIMULADO", exact=False)).to_be_visible()
            page.get_by_role("button", name="Volver a Mi ruta", exact=True).click()
            expect(page.get_by_role("tab", name="Mi ruta", exact=True)).to_have_attribute("aria-selected", "true")
            page.get_by_role("tab", name="Resultados", exact=True).click()
            # El control ya carece de conexión en interfaz.py. Documentarlo;
            # conectar navegación requeriría un cambio funcional fuera de alcance.
            expect(page.get_by_role("button", name="Volver al diagnóstico", exact=True)).to_be_visible()
            resultados.append("Limitación previa: Volver al diagnóstico existe pero no tiene callback conectado en interfaz.py.")
            page.get_by_role("button", name="Continuar con el siguiente tema", exact=True).click()
            expect(page.get_by_role("tab", name="Actividad", exact=True)).to_have_attribute("aria-selected", "true")
            resultados.append("Acciones: pedir, reintentar, recurso enfocable, detalles por teclado, Mi ruta y Continuar comprobados.")

            # Fixtures aislados para extremos de contenido, con el mismo renderer
            # y CSS. No pertenecen al progreso ni agregan estados a la aplicación.
            from ui.resultados import renderizar_retroalimentacion
            from ui.estilos import CSS
            extremos = {
                "05-sin-recurso-simulado": {"origen": "gemini", "acierto": "Completaste los criterios indicados.",
                    "mejora": "No hay criterios pendientes en este intento.", "pista": "Continúa con tu ruta."},
                "06-campos-vacios-simulados": {"acierto": None, "mejora": [], "pista": "   ", "recurso": {}},
                "07-texto-largo-html-simulado": {"origen": "local",
                    "acierto": ('Párrafo largo con caracteres especiales: ñ, <, >, &.\n\n' * 24)
                               + '<script>window.inyeccion = true</script><img src=x onerror="window.inyeccion=true">',
                    "mejora": "Comprueba `cero` y **valores negativos**.",
                    "pista": "TextoSinEspacios" * 30,
                    "recurso": {"titulo": "Referencia sin enlace", "fuente": "Fuente recibida"}},
            }
            page = browser.new_page()
            for nombre, datos in extremos.items():
                page.set_content('<!doctype html><html lang="es"><head><meta charset="UTF-8">'
                                 f'<style>{CSS}</style></head><body><div class="gradio-container">'
                                 '<main id="feedback-view">' + renderizar_retroalimentacion(datos)
                                 + '</main></div></body></html>')
                feedback = page.locator("#feedback-view")
                capturar(nombre)
                assert not page.locator("script, img, iframe").count()
                assert page.evaluate("window.inyeccion === undefined")
                if nombre != "07-texto-largo-html-simulado":
                    assert not feedback.locator(".feedback-resource").count()
                    assert feedback.locator(".feedback-main").evaluate(
                        "el => Math.abs(el.clientWidth - el.parentElement.clientWidth) <= 2")
            browser.close()
    finally:
        servidor.terminate()
        servidor.wait(timeout=20)
        registro.close()
        hash_final = hashlib.sha256(progreso.read_bytes()).hexdigest() if progreso.exists() else None
        assert hash_final == hash_previo, "El progreso personal cambió"
    (SALIDA / "verificacion.txt").write_text("SIMULACIÓN; SIN LLAMADAS A GEMINI\n" + "\n".join(resultados)
        + f"\nprogreso.json intacto: SHA256 {hash_previo}\n", encoding="utf-8")
    print("\n".join(resultados))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    servir() if args.serve else verificar()
