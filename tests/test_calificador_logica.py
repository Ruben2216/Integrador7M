"""Pruebas unitarias para calificador_logica.py y su integración con el sistema."""
import pytest

from calificador_logica import (
    calificar_laboratorio_logica,
    calificar_seguimiento_logica,
    obtener_conceptos_logica,
    obtener_ejercicios_laboratorio_logica,
    obtener_variante_seguimiento_logica,
    variantes_seguimiento_logica,
)
from integracion_calificador import normalizar_resultado_calificador
from retroalimentacion import generar_retroalimentacion


def test_obtener_ejercicios_laboratorio_logica():
    ejercicios = obtener_ejercicios_laboratorio_logica()
    assert len(ejercicios) == 4
    ids = [e["id"] for e in ejercicios]
    assert ids == ["LOG-LAB01", "LOG-LAB02", "LOG-LAB03", "LOG-LAB04"]
    for e in ejercicios:
        assert "concepto" in e
        assert "criterios" in e
        assert len(e["criterios"]) >= 2
        for c in e["criterios"]:
            assert "pregunta" in c
            assert "opciones" in c
            assert len(c["opciones"]) >= 3
            assert "respuesta_correcta" in c
            assert c["respuesta_correcta"] in c["opciones"]


def test_obtener_conceptos_logica():
    conceptos = obtener_conceptos_logica()
    assert "CONDICIONES" in conceptos
    assert "CICLOS" in conceptos
    assert "CORRECCION_LOGICA" in conceptos
    assert "INTEGRADOR_LOGICA" in conceptos


def test_calificar_laboratorio_logica_perfecto():
    ejercicios = obtener_ejercicios_laboratorio_logica()
    respuestas_correctas = {}
    for e in ejercicios:
        for c in e["criterios"]:
            respuestas_correctas[c["id"]] = c["respuesta_correcta"]

    res = calificar_laboratorio_logica(respuestas_correctas, tiempo=45.0)
    assert res["acreditado"] is True
    assert res["ejercicios_correctos"] == 4
    assert res["total_ejercicios"] == 4
    assert res["puntaje"] == 1.0
    assert len(res["criterios_cumplidos"]) == len(respuestas_correctas)
    assert len(res["conceptos_con_errores"]) == 0

    # Normalización para persistencia (progreso.json)
    norm = normalizar_resultado_calificador(res)
    assert norm["aprobado"] is True
    assert norm["tema"] == "Lógica de Programación"


def test_calificar_laboratorio_logica_integradora_obligatoria():
    ejercicios = obtener_ejercicios_laboratorio_logica()
    respuestas = {}
    for e in ejercicios:
        for c in e["criterios"]:
            # Fallar en la integradora LOG-LAB04
            if e["id"] == "LOG-LAB04":
                respuestas[c["id"]] = "Opción incorrecta"
            else:
                respuestas[c["id"]] = c["respuesta_correcta"]

    res = calificar_laboratorio_logica(respuestas, tiempo=50.0)
    # Acierta 3 de 4, pero falla la integradora -> NO acredita
    assert res["ejercicios_correctos"] == 3
    assert res["acreditado"] is False
    assert "INTEGRADOR_LOGICA" in res["conceptos_con_errores"]


def test_variantes_seguimiento_logica():
    variantes = variantes_seguimiento_logica()
    assert len(variantes) >= 3

    v1, preguntas1 = obtener_variante_seguimiento_logica([])
    assert v1 == "logica_variante_1"
    assert len(preguntas1) == 5

    v2, preguntas2 = obtener_variante_seguimiento_logica([v1])
    assert v2 == "logica_variante_2"

    v3, preguntas3 = obtener_variante_seguimiento_logica([v1, v2])
    assert v3 == "logica_variante_3"

    with pytest.raises(ValueError, match="No hay variantes"):
        obtener_variante_seguimiento_logica([v1, v2, v3])


def test_calificar_seguimiento_logica_aprobado_y_reprobado():
    _, preguntas = obtener_variante_seguimiento_logica([])
    respuestas_4_de_5 = {}
    # Responder 4 correctas y 1 incorrecta
    for i, p in enumerate(preguntas):
        if i == 0:
            incorrectas = [opt for opt in p["opciones"] if opt != p["respuesta_correcta"]]
            respuestas_4_de_5[p["id"]] = incorrectas[0]
        else:
            respuestas_4_de_5[p["id"]] = p["respuesta_correcta"]

    res = calificar_seguimiento_logica(respuestas_4_de_5, tiempo=30.0, variante_usada="logica_variante_1")
    assert res["correctas"] == 4
    assert res["total_preguntas"] == 5
    assert res["acreditado"] is True

    # 3 de 5 reprueba
    incorrectas = [opt for opt in preguntas[1]["opciones"] if opt != preguntas[1]["respuesta_correcta"]]
    respuestas_4_de_5[preguntas[1]["id"]] = incorrectas[0]
    res_3 = calificar_seguimiento_logica(respuestas_4_de_5, tiempo=35.0, variante_usada="logica_variante_1")
    assert res_3["correctas"] == 3
    assert res_3["acreditado"] is False


def test_retroalimentacion_local_logica():
    ejercicios = obtener_ejercicios_laboratorio_logica()
    respuestas = {}
    for e in ejercicios:
        for c in e["criterios"]:
            if e["concepto"] == "CICLOS":
                respuestas[c["id"]] = "Opción errónea"
            else:
                respuestas[c["id"]] = c["respuesta_correcta"]

    resultado = calificar_laboratorio_logica(respuestas, tiempo=40.0)
    retro = generar_retroalimentacion(resultado, formato_preferido="Visual")
    assert retro["origen"] == "local"
    assert retro["tema"] == "Lógica de Programación"
    assert retro["concepto"] == "CICLOS"
    assert "range" in retro["pista"].lower()
    assert retro["recurso"] is not None

