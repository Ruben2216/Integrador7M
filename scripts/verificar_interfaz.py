"""Recorrido visible de humo para la interfaz rediseñada.

Requiere Playwright disponible en PYTHONPATH y Chrome instalado. No usa el
progreso personal: app.py se inicia con --progress-file temporal.
"""
from pathlib import Path
import re

from playwright.sync_api import sync_playwright


URL = "http://127.0.0.1:7872"
ARTEFACTOS = Path("artefactos/redisenio")


def captura(page, nombre: str) -> None:
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTEFACTOS / nombre), full_page=True)


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(URL, wait_until="domcontentloaded")
        page.get_by_role("button", name="Iniciar simulación", exact=True).wait_for(timeout=20_000)
        assert "Tu recorrido empieza" in page.locator("body").inner_text()
        captura(page, "01-inicio.png")

        page.get_by_role("button", name="Iniciar simulación", exact=True).click()
        page.get_by_text("¿Qué quieres aprender?", exact=True).wait_for()
        captura(page, "02-diagnostico.png")
        page.get_by_role("button", name="Siguiente", exact=True).click()
        page.get_by_role("button", name="Siguiente", exact=True).click()
        page.get_by_role("button", name="Generar / actualizar mi ruta", exact=True).click()
        page.get_by_text("Mi ruta", exact=True).last.wait_for()
        page.wait_for_timeout(800)
        assert "Pasos pendientes" in page.locator("body").inner_text()
        captura(page, "03-mi-ruta.png")

        page.get_by_role("tab", name="Actividad", exact=True).click()
        page.get_by_role("radio", name="PostgreSQL · laboratorio", exact=True).check(force=True)
        page.get_by_label("Tu consulta SQL", exact=True).wait_for(timeout=10_000)
        page.get_by_label("Tu consulta SQL", exact=True).fill("SELECT nombre, correo FROM clientes WHERE ciudad = 'Guadalajara';")
        page.get_by_role("button", name="Siguiente", exact=True).click()
        page.get_by_role("button", name="Anterior", exact=True).click()
        assert "Guadalajara" in page.get_by_label("Tu consulta SQL", exact=True).input_value()
        captura(page, "04-actividad-postgresql.png")

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(350)
        captura(page, "05-actividad-movil.png")
        page.set_viewport_size({"width": 1440, "height": 1000})

        page.get_by_role("tab", name="Inicio", exact=True).click()
        page.get_by_role("button", name="Reiniciar simulación", exact=True).click()
        page.get_by_role("button", name="Cancelar", exact=True).wait_for()
        page.get_by_role("button", name="Cancelar", exact=True).click()
        assert "Reiniciar la simulación" not in page.locator("body").inner_text()
        print("OK: inicio, diagnóstico, ruta, laboratorio, conservación de respuesta y cancelación de reinicio")
        browser.close()


if __name__ == "__main__":
    main()
