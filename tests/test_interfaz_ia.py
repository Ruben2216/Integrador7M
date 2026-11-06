"""Lógica del botón «Pedir explicación con IA (Gemini)» en la pantalla de Resultados."""
import json

import pytest

import interfaz
import simulacion
from progreso import AlmacenProgreso


@pytest.fixture(scope="module")
def motor():
    from motor import Motor
    instancia = Motor()
    simulacion.configurar_motor(instancia)
    return instancia


@pytest.fixture
def app(motor, tmp_path, monkeypatch):
    """Interfaz construida en memoria (sin servidor) con Gemini 'configurado'."""
    monkeypatch.setattr(simulacion, "almacen", AlmacenProgreso(tmp_path / "progreso.json"))
    monkeypatch.setattr(interfaz, "GEMINI_ACTIVO", True)
    demo = interfaz.construir_interfaz(motor)
    fns = demo.fns.values() if isinstance(demo.fns, dict) else demo.fns
    eventos = {getattr(f, "name", None) or f.fn.__name__: f for f in fns}
    boton = next(b for b in demo.blocks.values()
                 if getattr(b, "value", None) == interfaz.TEXTO_BOTON_IA)
    return demo, eventos, boton


def _estado_con_lab_mvc(eventos, fallar=("M03-SQL",)):
    """Califica un laboratorio MVC por la interfaz y devuelve (estado, salida)."""
    with open("ejercicios_mvc_php.json", encoding="utf-8") as archivo:
        laboratorio = json.load(archivo)["laboratorio"]
    respuestas = []
    for ejercicio in laboratorio:
        for c in ejercicio["criterios"]:
            mala = next(o for o in c["opciones"] if o != c["respuesta_correcta"])
            respuestas.append(mala if c["id"] in fallar else c["respuesta_correcta"])
    estado = interfaz._estado_inicial(simulacion.motor)
    salida = eventos["calificar_lab_mvc"].fn(*respuestas, estado)
    return salida[0], salida


def test_texto_del_boton_y_deshabilitado_sin_intento(app):
    _, _, boton = app
    assert boton.value == "Pedir explicación con IA (Gemini)"
    assert boton.interactive is False


def test_clic_unico_y_circulo_inmediato(app):
    _, eventos, _ = app
    cargando = eventos["mostrar_cargando_ia"]
    assert cargando.trigger_mode == "once"  # ignora clics repetidos mientras procesa
    assert cargando.queue is False          # el círculo aparece al instante
    boton, circulo, texto = cargando.fn()
    assert boton["interactive"] is False and boton["value"] == "Generando explicación…"
    assert circulo["visible"] is True and texto == ""
    assert "animateTransform" in interfaz.CARGANDO_IA_HTML


def test_intento_calificado_habilita_el_boton(app):
    _, eventos, _ = app
    _, salida = _estado_con_lab_mvc(eventos)
    explicacion, boton, circulo = salida[-3:]
    assert explicacion == ""
    assert boton["interactive"] is True and boton["value"] == interfaz.TEXTO_BOTON_IA
    assert circulo["visible"] is False


def test_explicacion_de_gemini_bloquea_el_boton(app, monkeypatch):
    _, eventos, _ = app
    estado, _ = _estado_con_lab_mvc(eventos)
    monkeypatch.setattr(interfaz, "solicitar_explicacion", lambda r, f=None: {
        "origen": "gemini", "modelo": "gemini-3.5-flash", "acierto": "a", "mejora": "b",
        "pista": "c", "recurso": None})
    texto, boton, circulo = eventos["pedir_explicacion"].fn(estado)
    assert "Generada con Gemini (gemini-3.5-flash)" in texto
    assert boton["interactive"] is False and "generada" in boton["value"]
    assert circulo["visible"] is False


def test_si_gemini_falla_se_puede_reintentar(app, monkeypatch):
    _, eventos, _ = app
    estado, _ = _estado_con_lab_mvc(eventos)
    monkeypatch.setattr(interfaz, "solicitar_explicacion", lambda r, f=None: {
        "origen": "local", "motivo_respaldo": "Gemini está saturado en este momento (503)",
        "acierto": "a", "mejora": "b", "pista": "c", "recurso": None})
    texto, boton, circulo = eventos["pedir_explicacion"].fn(estado)
    assert "saturado" in texto
    assert boton["interactive"] is True and boton["value"].startswith("Reintentar")
    assert circulo["visible"] is False


def test_error_inesperado_no_deja_el_boton_bloqueado(app, monkeypatch):
    _, eventos, _ = app
    estado, _ = _estado_con_lab_mvc(eventos)

    def falla(*_):
        raise RuntimeError("boom")

    monkeypatch.setattr(interfaz, "solicitar_explicacion", falla)
    texto, boton, circulo = eventos["pedir_explicacion"].fn(estado)
    assert "No se pudo generar" in texto
    assert boton["interactive"] is True and circulo["visible"] is False


def test_practica_poo_no_habilita_el_boton(app):
    _, eventos, _ = app
    estado = interfaz._estado_inicial(simulacion.motor)
    salida = eventos["entregar_poo"].fn("r1", "r2", "", "", estado)
    assert salida[-2]["interactive"] is False
    texto, boton, _ = eventos["pedir_explicacion"].fn(salida[0])
    assert "POO" in texto and boton["interactive"] is False


def test_sin_gemini_configurado_el_boton_lo_indica(monkeypatch):
    monkeypatch.setattr(interfaz, "GEMINI_ACTIVO", False)
    boton = interfaz._boton_ia(True)
    assert boton["interactive"] is False and "no disponible" in boton["value"]


def test_reiniciar_vuelve_el_boton_al_inicio(app):
    _, eventos, _ = app
    salida = eventos["reiniciar_desde_interfaz"].fn()
    resultados, explicacion, boton, circulo = salida[-4:]
    assert "Aún no hay resultados" in resultados and explicacion == ""
    assert boton["interactive"] is False and boton["value"] == interfaz.TEXTO_BOTON_IA
    assert circulo["visible"] is False
