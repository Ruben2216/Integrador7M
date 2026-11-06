"""Pruebas de la capa de interfaz: estado, ruta y conexión con calificadores.

No levantan Gradio: verifican los contratos que la UI usa para no acreditar por
selección, mantener la idempotencia de intentos y respetar el grafo real.
"""
import json
from pathlib import Path

import pytest

from calificador import obtener_ejercicios_laboratorio, calificar_seguimiento
from calificador_node import obtener_ejercicios_laboratorio_node
from integracion_calificador import normalizar_resultado_calificador
from motor import Motor
from progreso import AlmacenProgreso, estado_inicial, temas_acreditados
from ui import aplicacion


@pytest.fixture(scope="module")
def motor():
    return Motor()


@pytest.fixture()
def almacen(tmp_path, monkeypatch):
    store = AlmacenProgreso(tmp_path / "progreso.json")
    monkeypatch.setattr(aplicacion.simulacion, "almacen", store)
    return store


def _perfil(**cambios):
    perfil = {
        "nivel": "Principiante",
        "formato": "Visual",
        "tema": "Bases de Datos PostgreSQL",
        "tiempo": 90,
        "errores": 25,
        "meta": "Backend con Node.js",
        "fallos": 1,
        "abandono": False,
    }
    perfil.update(cambios)
    return perfil


def test_guardar_perfil_no_acredita_el_tema_seleccionado(almacen, motor):
    guardado = aplicacion._persistir_perfil(_perfil())
    assert guardado["simulacion_activa"] is True
    assert guardado["tema_actual"] == "Bases de Datos PostgreSQL"
    assert temas_acreditados(guardado) == []
    # La meta elegida tampoco acredita nada por sí sola.
    assert guardado["meta"] == "Backend con Node.js"


def test_guardar_perfil_conserva_acreditaciones_verificadas(almacen, motor):
    resultado = {
        "id": "intento-logica-1",
        "tema": "Lógica de Programación",
        "tipo_actividad": "Seguimiento",
        "puntaje": 4,
        "tiempo_segundos": 60,
        "conceptos_con_error": [],
        "aprobado": True,
    }
    almacen.guardar_intento(resultado)
    guardado = aplicacion._persistir_perfil(_perfil(tema="Backend con Node.js"))
    assert temas_acreditados(guardado) == ["Lógica de Programación"]


def test_estado_del_tema_respeta_prerrequisitos_reales(motor):
    assert aplicacion._estado_del_tema(motor, "Bases de Datos PostgreSQL", []) == (
        "Bloqueado",
        ["Lógica de Programación"],
    )
    assert aplicacion._estado_del_tema(
        motor, "Bases de Datos PostgreSQL", ["Lógica de Programación"]
    ) == ("Disponible", [])
    estado, faltantes = aplicacion._estado_del_tema(motor, "Backend con Node.js", [])
    assert estado == "Bloqueado"
    assert set(faltantes) == {
        "Programación Orientada a Objetos",
        "Bases de Datos PostgreSQL",
    }
    assert aplicacion._estado_del_tema(motor, "Lógica de Programación", []) == (
        "Disponible",
        [],
    )


def test_temas_pertinentes_de_la_meta_incluyen_ancestros(motor):
    relevantes = aplicacion._temas_pertinentes(motor, "Backend con Node.js")
    assert relevantes == [
        "Lógica de Programación",
        "Programación Orientada a Objetos",
        "Bases de Datos PostgreSQL",
        "Backend con Node.js",
    ]


def test_info_actividad_distingue_conectada_de_no_disponible():
    assert aplicacion._info_actividad("Bases de Datos PostgreSQL")["clave"] == "pg_lab"
    assert aplicacion._info_actividad("Backend con Node.js")["clave"] == "node_lab"
    assert aplicacion._info_actividad("Programación Orientada a Objetos")["clave"] == "poo"
    assert aplicacion._info_actividad("Lógica de Programación")["clave"] == "logica_lab"
    assert aplicacion._info_actividad("Patrón MVC en PHP")["clave"] == "mvc_lab"


def test_bancos_reales_tienen_la_forma_que_espera_la_interfaz():
    laboratorio = obtener_ejercicios_laboratorio()
    assert len(laboratorio) >= 4
    assert any(ej["id"] == "PSQL-LAB04" for ej in laboratorio)
    for ejercicio in laboratorio:
        assert {"id", "enunciado", "esquema_sql", "concepto"} <= set(ejercicio)
    node = obtener_ejercicios_laboratorio_node()
    assert len(node) == 4
    poo = json.loads(Path("ejercicios_poo.json").read_text(encoding="utf-8"))
    assert len(poo["ejercicios"]) == 4


def test_calificador_real_tres_de_cinco_no_acredita():
    banco = json.loads(Path("ejercicios_postgresql.json").read_text(encoding="utf-8"))
    preguntas = banco["seguimiento"]["variante_1"]
    respuestas = {
        pregunta["id"]: pregunta["respuesta_correcta"]
        for pregunta in preguntas[:3]
    }
    bruto = calificar_seguimiento(respuestas, 30, variante_usada="variante_1")
    assert bruto["correctas"] == 3
    assert bruto["acreditado"] is False
    normalizado = normalizar_resultado_calificador(bruto)
    assert normalizado["aprobado"] is False
    assert normalizado["tema"] == "Bases de Datos PostgreSQL"


def test_persistencia_es_idempotente_por_id_de_intento(almacen):
    resultado = {
        "id": "mismo-intento",
        "tema": "Bases de Datos PostgreSQL",
        "tipo_actividad": "Seguimiento",
        "puntaje": 4,
        "tiempo_segundos": 40,
        "conceptos_con_error": [],
        "aprobado": True,
    }
    almacen.guardar_intento(resultado)
    almacen.guardar_intento(dict(resultado))
    guardado = almacen.cargar()
    assert len(guardado["intentos"]) == 1
    assert temas_acreditados(guardado) == ["Bases de Datos PostgreSQL"]


def test_variante_de_seguimiento_evita_las_usadas():
    primera = aplicacion.obtener_variante_seguimiento([])[0]
    segunda = aplicacion.obtener_variante_seguimiento([primera])[0]
    assert segunda != primera
    assert primera and segunda
