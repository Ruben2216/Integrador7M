import json

import pytest

from calificador import (calificar_laboratorio, calificar_seguimiento,
                         obtener_ejercicios_laboratorio)
from integracion_calificador import normalizar_resultado_calificador
from motor import Motor
from progreso import AlmacenProgreso, ErrorProgreso, estado_inicial
from recomendador import NODO_A_TEMA, TEMA_A_NODO


def test_adapter_mapea_todos_los_temas_del_motor():
    for nodo, tema in NODO_A_TEMA.items():
        adaptado = normalizar_resultado_calificador({
            "intento": f"id-{nodo}", "tema": nodo, "tipo": "seguimiento",
            "puntaje": 0.6, "tiempo": 90, "correctas": 3,
            "total_preguntas": 5, "conceptos_con_errores": ["JOIN"],
            "acreditado": False,
        })
        assert adaptado["tema"] == tema
        assert adaptado["id"] == f"id-{nodo}"


def test_seguimiento_real_de_tres_de_cinco_queda_pendiente():
    with open("ejercicios_postgresql.json", encoding="utf-8") as archivo:
        preguntas = json.load(archivo)["seguimiento"]["variante_1"]
    respuestas = {}
    for idx, pregunta in enumerate(preguntas):
        correcta = pregunta["respuesta_correcta"]
        respuestas[pregunta["id"]] = correcta if idx < 3 else next(
            opcion for opcion in pregunta["opciones"] if opcion != correcta
        )
    bruto = calificar_seguimiento(respuestas, 123, "variante_1")
    adaptado = normalizar_resultado_calificador(bruto)
    assert bruto["correctas"] == 3 and bruto["total_preguntas"] == 5
    assert adaptado["puntaje"] == 3 and adaptado["puntaje_maximo"] == 5
    assert adaptado["puntaje_proporcion"] == 0.6
    assert adaptado["aprobado"] is False
    assert adaptado["tipo_actividad"] == "Actividad de seguimiento"


def test_laboratorio_real_acredita_con_integradora_obligatoria():
    ejercicios = obtener_ejercicios_laboratorio()
    respuestas = {ej["id"]: ej["respuesta_esperada_sql"] for ej in ejercicios}
    bruto = calificar_laboratorio(respuestas, 200)
    adaptado = normalizar_resultado_calificador(bruto)
    assert bruto["ejercicios_correctos"] == 4
    assert bruto["acreditado"] is True
    assert adaptado["puntaje"] == 4 and adaptado["puntaje_maximo"] == 4
    assert adaptado["tipo_actividad"] == "Diagnóstico (laboratorio)"


def test_laboratorio_no_acredita_si_falla_integradora():
    ejercicios = obtener_ejercicios_laboratorio()
    respuestas = {ej["id"]: ej["respuesta_esperada_sql"] for ej in ejercicios}
    respuestas["PSQL-LAB04"] = "SELECT 1;"
    bruto = calificar_laboratorio(respuestas, 200)
    assert bruto["ejercicios_correctos"] == 3
    assert bruto["detalle"][-1]["correcto"] is False
    assert bruto["acreditado"] is False


def test_persistencia_deduplica_y_rechaza_datos_invalidos(tmp_path):
    store = AlmacenProgreso(tmp_path / "progress.json")
    store.iniciar("Backend con Node.js", "Visual")
    attempt = {
        "id": "same-id", "tema": "Bases de Datos PostgreSQL",
        "tipo_actividad": "Actividad de seguimiento", "puntaje": 3,
        "puntaje_maximo": 5, "tiempo_segundos": 120,
        "conceptos_con_error": ["JOIN"], "aprobado": False,
    }
    once = store.guardar_intento(attempt)
    twice = store.guardar_intento(attempt)
    assert len(once["intentos"]) == len(twice["intentos"]) == 1
    before = (tmp_path / "progress.json").read_bytes()
    with pytest.raises(ValueError):
        store.guardar_intento({**attempt, "id": "bad", "aprobado": "false"})
    assert (tmp_path / "progress.json").read_bytes() == before


def test_reprobado_posterior_conserva_acreditacion(tmp_path):
    store = AlmacenProgreso(tmp_path / "progress.json")
    store.iniciar("Backend con Node.js", "Visual")
    previo = store.cargar()
    previo["temas_acreditados"]["Bases de Datos PostgreSQL"] = {
        "origen": "diagnóstico", "intento_id": "anterior", "legado": True}
    store.guardar(previo)
    passed = {
        "id": "pass", "tema": "Bases de Datos PostgreSQL",
        "tipo_actividad": "Actividad de seguimiento", "puntaje": 4,
        "puntaje_maximo": 5, "tiempo_segundos": 100,
        "conceptos_con_error": [], "aprobado": True,
    }
    failed = {**passed, "id": "fail", "puntaje": 2, "aprobado": False}
    store.guardar_intento(passed)
    state = store.guardar_intento(failed)
    assert len(state["intentos"]) == 2
    assert state["temas_acreditados"]["Bases de Datos PostgreSQL"]["origen"] == "diagnóstico"


def test_error_de_escritura_no_reemplaza_ultimo_estado(tmp_path, monkeypatch):
    store = AlmacenProgreso(tmp_path / "progress.json")
    store.iniciar("Backend con Node.js", "Visual")
    path = tmp_path / "progress.json"
    before = path.read_bytes()

    def fail_replace(*_args):
        raise OSError("write failure test")

    monkeypatch.setattr("progreso.os.replace", fail_replace)
    with pytest.raises(ErrorProgreso):
        store.iniciar("Patrón MVC en PHP", "Texto")
    assert path.read_bytes() == before


def test_motor_real_recalcula_nodejs_desde_progreso():
    motor = Motor()
    done = ["Lógica de Programación", "Programación Orientada a Objetos"]
    blocked = motor.ruta_directa(done, "Backend con Node.js", "Principiante")
    assert blocked["siguiente_tema"] == "Bases de Datos PostgreSQL"
    unlocked = motor.ruta_directa(done + ["Bases de Datos PostgreSQL"],
                                  "Backend con Node.js", "Principiante")
    assert unlocked["ruta_pendiente"] == ["Backend con Node.js"]
    assert unlocked["siguiente_tema"] == "Backend con Node.js"


def test_motor_devuelve_meta_completada():
    motor = Motor()
    done = list(TEMA_A_NODO)
    result = motor.ruta_directa(done, "Backend con Node.js", "Principiante")
    assert result["estado_meta"] == "Meta completada"
    assert result["ruta_pendiente"] == []
