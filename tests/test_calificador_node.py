import json

from calificador_node import (
    calificar_laboratorio_node,
    calificar_seguimiento_node,
    obtener_ejercicios_laboratorio_node,
    obtener_variante_seguimiento_node,
)
from integracion_calificador import normalizar_resultado_calificador
from progreso import AlmacenProgreso


RESPUESTAS_LAB_COMPLETAS = {
    "node-lab-01": "GET /salud responde 200",
    "node-lab-02": "GET /libros/:id; leer con req.params.id",
    "node-lab-03": "Validar que nombre sea obligatorio antes de guardar; responder 400 y no crear",
    "node-lab-04": "POST /productos devuelve 201; GET /productos devuelve 200",
}


def test_laboratorio_node_puntua_cinco_y_expone_criterios():
    result = calificar_laboratorio_node(RESPUESTAS_LAB_COMPLETAS, 42)
    assert result["puntaje_obtenido"] == 5
    assert result["puntaje_maximo"] == 5
    assert result["acreditado"] is True
    assert len(result["detalle"]) == 4
    assert result["criterios_cumplidos"]
    normalized = normalizar_resultado_calificador(result)
    assert normalized["tema"] == "Backend con Node.js"
    assert normalized["tipo_actividad"] == "Diagnóstico (laboratorio)"
    assert normalized["puntaje"] == 5
    assert normalized["puntaje_maximo"] == 5


def test_laboratorio_node_pendiente_si_no_alcanza_cuatro_puntos():
    answers = dict(RESPUESTAS_LAB_COMPLETAS)
    answers["node-lab-04"] = ""
    result = calificar_laboratorio_node(answers, 12)
    assert result["puntaje_obtenido"] == 3
    assert result["acreditado"] is False
    assert "API CRUD" in result["conceptos_con_errores"]


def test_laboratorio_node_vacio_no_acredita():
    result = calificar_laboratorio_node({}, 0)
    assert result["puntaje_obtenido"] == 0
    assert result["acreditado"] is False
    assert len(result["criterios_incumplidos"]) == 7


def test_seguimiento_node_umbral_tres_y_cuatro_de_cinco():
    variant, questions = obtener_variante_seguimiento_node([])
    answers = {q["id"]: q["respuesta"] for q in questions}
    passed = calificar_seguimiento_node(answers, 30, variant)
    assert passed["correctas"] == 5 and passed["acreditado"] is True

    answers[questions[3]["id"]] = "incorrecto"
    answers[questions[4]["id"]] = "incorrecto"
    failed = calificar_seguimiento_node(answers, 30, variant)
    assert failed["correctas"] == 3 and failed["acreditado"] is False
    assert len(failed["conceptos_con_errores"]) == 2


def test_variantes_node_equivalentes_y_no_reutilizadas():
    first, first_questions = obtener_variante_seguimiento_node([])
    second, second_questions = obtener_variante_seguimiento_node([first])
    assert first != second
    assert len(first_questions) == len(second_questions) == 5
    assert {q["concepto"] for q in first_questions} == {q["concepto"] for q in second_questions}


def test_aprobacion_laboratorio_node_se_guarda_con_origen_diagnostico(tmp_path):
    store = AlmacenProgreso(tmp_path / "progress.json")
    store.iniciar("Backend con Node.js", "Práctico")
    result = normalizar_resultado_calificador(
        calificar_laboratorio_node(RESPUESTAS_LAB_COMPLETAS, 60)
    )
    state = store.guardar_intento(result)
    assert state["temas_acreditados"]["Backend con Node.js"]["origen"] == "diagnóstico"
    assert state["intentos"][0]["puntaje"] == 5
    assert state["intentos"][0]["puntaje_maximo"] == 5


def test_recursos_node_de_banco_estan_en_catalogo_y_grafo():
    with open("ejercicios_node.json", encoding="utf-8") as f:
        bank = json.load(f)
    with open("catalogo_recursos.json", encoding="utf-8") as f:
        catalog = json.load(f)
    with open("grafo_conocimiento.json", encoding="utf-8") as f:
        graph = json.load(f)
    node = graph["Backend_con_Nodejs"]
    assert len(bank["recursos"]) == 3
    assert all(resource["enlace"].startswith("https://") for resource in bank["recursos"])
    for key in node["recursos"]:
        assert key in catalog
        assert catalog[key]["enlace"].startswith("https://")
    assert "Recurso_Lectura_Node_Express" in node["recursos"]
    assert "Recurso_Referencia_Node_Errors" in node["recursos"]
