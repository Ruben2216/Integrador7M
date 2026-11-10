"""Pruebas del Integrante 5: refuerzo por concepto, Gemini con respaldo local y tema MVC."""
import json
import time
from pathlib import Path

import pytest

import retroalimentacion as retro
from calificador import calificar_laboratorio, calificar_seguimiento, obtener_ejercicios_laboratorio
from calificador_mvc import (calificar_laboratorio_mvc, calificar_seguimiento_mvc,
                             obtener_ejercicios_laboratorio_mvc,
                             obtener_variante_seguimiento_mvc, variantes_seguimiento_mvc)
from integracion_calificador import normalizar_resultado_calificador
from progreso import AlmacenProgreso
from retroalimentacion import (ConfigGemini, ErrorGemini, generar_retroalimentacion,
                               solicitar_explicacion)
from ui.resultados import renderizar_retroalimentacion

BASE = Path(__file__).resolve().parent.parent


def _json(nombre):
    with (BASE / nombre).open(encoding="utf-8") as archivo:
        return json.load(archivo)


def _seguimiento_psql(fallar_ids=(), fallar_concepto=None, variante="variante_1"):
    """Responde la variante; falla las preguntas indicadas (por id o por concepto)."""
    preguntas = _json("ejercicios_postgresql.json")["seguimiento"][variante]
    respuestas = {}
    for p in preguntas:
        incorrecta = next(o for o in p["opciones"] if o != p["respuesta_correcta"])
        falla = p["id"] in fallar_ids or p["concepto"] == fallar_concepto
        respuestas[p["id"]] = incorrecta if falla else p["respuesta_correcta"]
    return calificar_seguimiento(respuestas, 150.0, variante)


def _lab_psql(**cambios):
    respuestas = {e["id"]: e["respuesta_esperada_sql"] for e in obtener_ejercicios_laboratorio()}
    respuestas.update(cambios)
    return calificar_laboratorio(respuestas, 300.0)


def _lab_mvc(fallar=()):
    respuestas = {}
    for ejercicio in obtener_ejercicios_laboratorio_mvc():
        for c in ejercicio["criterios"]:
            incorrecta = next(o for o in c["opciones"] if o != c["respuesta_correcta"])
            respuestas[c["id"]] = incorrecta if c["id"] in fallar else c["respuesta_correcta"]
    return calificar_laboratorio_mvc(respuestas, 200.0)


def _seguimiento_mvc(variante, fallar_conceptos=()):
    preguntas = _json("ejercicios_mvc_php.json")["seguimiento"][variante]
    respuestas = {}
    for p in preguntas:
        incorrecta = next(o for o in p["opciones"] if o != p["respuesta_correcta"])
        respuestas[p["id"]] = incorrecta if p["concepto"] in fallar_conceptos else p["respuesta_correcta"]
    return calificar_seguimiento_mvc(respuestas, 100.0, variante)


# ── Plan B: retroalimentación local ─────────────────────────────────────────

def test_join_y_where_con_la_misma_nota_dan_salidas_distintas():
    con_join = _seguimiento_psql(fallar_concepto="JOIN")
    con_where = _seguimiento_psql(fallar_concepto="WHERE")
    assert con_join["correctas"] == con_where["correctas"] == 3

    r_join = generar_retroalimentacion(con_join)
    r_where = generar_retroalimentacion(con_where)
    assert r_join["concepto"] == "JOIN" and r_where["concepto"] == "WHERE"
    assert r_join["pista"] != r_where["pista"]
    assert r_join["mejora"] != r_where["mejora"]
    assert r_join["recurso"]["id"] != r_where["recurso"]["id"]
    assert r_join["recurso"]["concepto"] == "JOIN"
    assert r_where["recurso"]["concepto"] == "WHERE"


def test_pista_de_join_indica_conservar_filas_de_clientes():
    resultado = _lab_psql(**{
        "PSQL-LAB02": "SELECT clientes.nombre, pedidos.total FROM clientes "
                      "INNER JOIN pedidos ON clientes.id = pedidos.cliente_id;",
    })
    salida = generar_retroalimentacion(resultado)
    assert salida["concepto"] == "JOIN"
    assert "conservar las filas de la tabla de clientes" in salida["pista"]
    assert "LEFT JOIN" in salida["recurso"]["titulo"]


def test_devuelve_acierto_mejora_pista_y_recurso_del_catalogo():
    salida = generar_retroalimentacion(_seguimiento_psql(fallar_concepto="JOIN"))
    catalogo = _json("catalogo_recursos.json")
    for campo in ("acierto", "mejora", "pista"):
        assert isinstance(salida[campo], str) and salida[campo].strip()
    recurso = salida["recurso"]
    assert recurso["id"] in catalogo
    assert recurso["enlace"] == catalogo[recurso["id"]]["enlace"]
    assert salida["origen"] == "local" and salida["motivo_respaldo"] is None


def test_prioriza_el_concepto_con_mas_fallos():
    # variante_1: 01 WHERE, 02 JOIN, 03 GROUP_BY, 04 WHERE, 05 JOIN
    resultado = _seguimiento_psql(fallar_ids={"PSQL-SEG-V1-01", "PSQL-SEG-V1-02", "PSQL-SEG-V1-05"})
    salida = generar_retroalimentacion(resultado)
    assert salida["fallos_por_concepto"] == {"WHERE": 1, "JOIN": 2}
    assert salida["concepto"] == "JOIN"


def test_desempate_reproducible_por_orden_de_la_rubrica():
    resultado = _seguimiento_psql(fallar_ids={"PSQL-SEG-V1-02", "PSQL-SEG-V1-04"})  # 1 JOIN, 1 WHERE
    primeras = [generar_retroalimentacion(resultado)["concepto"] for _ in range(3)]
    assert primeras == ["WHERE", "WHERE", "WHERE"]  # WHERE va antes que JOIN en la rúbrica


def test_en_laboratorio_cuenta_criterios_incumplidos():
    # LAB01 falla 1 criterio (WHERE); LAB04 sin COALESCE falla 2 (INTEGRADORA).
    resultado = _lab_psql(**{
        "PSQL-LAB01": "SELECT nombre, correo FROM clientes;",
        "PSQL-LAB04": "SELECT clientes.nombre, COUNT(pedidos.id), SUM(pedidos.total) FROM clientes "
                      "LEFT JOIN pedidos ON clientes.id = pedidos.cliente_id GROUP BY clientes.nombre;",
    })
    salida = generar_retroalimentacion(resultado)
    assert salida["fallos_por_concepto"]["INTEGRADORA"] > salida["fallos_por_concepto"]["WHERE"]
    assert salida["concepto"] == "INTEGRADORA"
    assert "COALESCE" in salida["pista"]


def test_consulta_que_no_se_ejecuta_explica_el_error():
    resultado = _lab_psql(**{"PSQL-LAB02": "SELEC nombre FROM clientes"})
    salida = generar_retroalimentacion(resultado)
    assert salida["concepto"] == "JOIN"
    assert "PSQL-LAB02 no se pudo calificar" in salida["mejora"]
    assert salida["pista"] and salida["recurso"]["concepto"] == "JOIN"


def test_intento_perfecto_felicita_sin_concepto_pendiente():
    salida = generar_retroalimentacion(_lab_psql())
    assert salida["concepto"] is None
    assert "todo correctamente" in salida["acierto"]
    assert salida["recurso"] is not None


def test_acepta_el_resultado_normalizado_de_progreso():
    bruto = _seguimiento_psql(fallar_concepto="JOIN")
    normalizado = normalizar_resultado_calificador(bruto)
    a, b = generar_retroalimentacion(bruto), generar_retroalimentacion(normalizado)
    assert (a["concepto"], a["pista"], a["recurso"]["id"]) == (b["concepto"], b["pista"], b["recurso"]["id"])


def test_formato_preferido_elige_recurso_del_mismo_concepto():
    resultado = _lab_mvc(fallar={"M03-SQL"})
    por_defecto = generar_retroalimentacion(resultado)
    texto = generar_retroalimentacion(resultado, "Texto")
    assert por_defecto["recurso"]["id"] == "Recurso_Practica_PHP"
    assert texto["recurso"]["formato"] in ("Lectura", "Referencia")
    assert texto["recurso"]["concepto"] == por_defecto["recurso"]["concepto"] == "CORRECCION_CAPA"


def test_practica_poo_sin_calificacion_recibe_orientacion_general():
    salida = generar_retroalimentacion({"tipo": "poo", "respondidos": 4, "total": 4,
                                        "acreditado": False, "detalle": []})
    assert salida["tema"] == "Programación Orientada a Objetos"
    assert salida["recurso"]["concepto"] == "Programación Orientada a Objetos"


# ── Plan A: Gemini con respaldo ─────────────────────────────────────────────

def _respuesta_gemini(texto, motivo="STOP"):
    return {"candidates": [{"content": {"parts": [{"text": texto}]}, "finishReason": motivo}]}


VALIDA = json.dumps({"acierto": "Bien con WHERE.", "mejora": "Revisa el JOIN.",
                     "pista": "Piensa qué tabla debe conservar todas sus filas."})


class TransporteFalso:
    def __init__(self, respuesta=None, error=None, demora=0.0):
        self.respuesta, self.error, self.demora, self.llamadas = respuesta, error, demora, []

    def __call__(self, url, cabeceras, cuerpo, timeout):
        self.llamadas.append((url, cabeceras, cuerpo, timeout))
        if self.demora:
            time.sleep(self.demora)
        if self.error:
            raise self.error
        return self.respuesta


@pytest.fixture(autouse=True)
def _limpiar_cache():
    retro._CACHE_GEMINI.clear()
    yield
    retro._CACHE_GEMINI.clear()


def test_sin_clave_usa_respaldo_local_sin_llamar_a_gemini():
    transporte = TransporteFalso(_respuesta_gemini(VALIDA))
    salida = solicitar_explicacion(_seguimiento_psql(fallar_concepto="JOIN"),
                                   config=ConfigGemini(api_key=""), transporte=transporte)
    assert salida["origen"] == "local"
    assert "GEMINI_API_KEY" in salida["motivo_respaldo"]
    assert salida["pista"] and salida["recurso"]
    assert transporte.llamadas == []


def test_gemini_desactivado_sigue_dando_pista_y_recurso_coherentes():
    resultado = _seguimiento_psql(fallar_concepto="JOIN")
    transporte = TransporteFalso(_respuesta_gemini(VALIDA))
    salida = solicitar_explicacion(resultado, config=ConfigGemini(api_key="x", desactivado=True),
                                   transporte=transporte)
    assert transporte.llamadas == []
    assert salida["origen"] == "local" and salida["concepto"] == "JOIN"
    assert salida["pista"] == generar_retroalimentacion(resultado)["pista"]


def test_gemini_responde_con_el_mismo_formato_y_recurso_del_catalogo():
    resultado = _lab_psql(**{"PSQL-LAB02": "SELECT nombre FROM clientes;"})
    transporte = TransporteFalso(_respuesta_gemini(VALIDA))
    salida = solicitar_explicacion(resultado, config=ConfigGemini(api_key="clave-prueba"),
                                   transporte=transporte)
    local = generar_retroalimentacion(resultado)
    assert salida["origen"] == "gemini" and salida["motivo_respaldo"] is None
    assert salida["pista"] == "Piensa qué tabla debe conservar todas sus filas."
    assert salida["recurso"] == local["recurso"] and salida["concepto"] == local["concepto"]
    assert set(local) <= set(salida) and salida["modelo"] == "gemini-3.5-flash"

    (url, cabeceras, cuerpo, _), = transporte.llamadas  # una sola solicitud por tema
    assert "gemini" in url and ":generateContent" in url
    assert cabeceras["x-goog-api-key"] == "clave-prueba"
    prompt = cuerpo["contents"][0]["parts"][0]["text"]
    for ejercicio in obtener_ejercicios_laboratorio():  # agrupa los cuatro ejercicios
        assert ejercicio["id"] in prompt
    assert "C02-JOIN (NO cumplido)" in prompt and "C01-WHERE (cumplido)" in prompt


def test_timeout_activa_respaldo_sin_esperar_a_gemini():
    transporte = TransporteFalso(_respuesta_gemini(VALIDA), demora=2.0)
    inicio = time.monotonic()
    salida = solicitar_explicacion(_seguimiento_psql(fallar_concepto="WHERE"),
                                   config=ConfigGemini(api_key="x", timeout=0.2),
                                   transporte=transporte)
    assert time.monotonic() - inicio < 1.5
    assert salida["origen"] == "local" and "tardó" in salida["motivo_respaldo"]
    assert salida["concepto"] == "WHERE"


@pytest.mark.parametrize("respuesta", [
    _respuesta_gemini(json.dumps({"acierto": "a", "mejora": "b"})),          # falta pista
    _respuesta_gemini(json.dumps({"acierto": "a", "mejora": "b", "pista": " "})),
    _respuesta_gemini(VALIDA, motivo="MAX_TOKENS"),                         # cortada
    _respuesta_gemini("esto no es json"),
    _respuesta_gemini(json.dumps({"acierto": "a" * 2000, "mejora": "b", "pista": "c"})),
    {"candidates": []},
    {"promptFeedback": {"blockReason": "SAFETY"}},
])
def test_respuesta_incompleta_activa_respaldo(respuesta):
    salida = solicitar_explicacion(_seguimiento_psql(fallar_concepto="JOIN"),
                                   config=ConfigGemini(api_key="x"),
                                   transporte=TransporteFalso(respuesta))
    assert salida["origen"] == "local" and salida["motivo_respaldo"]
    assert salida["concepto"] == "JOIN" and salida["recurso"]


@pytest.mark.parametrize("error", [ErrorGemini("la API key de Gemini no es válida (403)"),
                                   ConnectionError("sin red"), RuntimeError("inesperado")])
def test_fallo_de_la_llamada_activa_respaldo(error):
    salida = solicitar_explicacion(_seguimiento_psql(fallar_concepto="JOIN"),
                                   config=ConfigGemini(api_key="x"),
                                   transporte=TransporteFalso(error=error))
    assert salida["origen"] == "local" and salida["motivo_respaldo"]


class TransportePorModelo(TransporteFalso):
    """Responde distinto según el modelo de la URL."""

    def __init__(self, por_modelo):
        super().__init__()
        self.por_modelo = por_modelo

    def __call__(self, url, cabeceras, cuerpo, timeout):
        self.llamadas.append(url)
        modelo = url.split("/models/")[1].split(":")[0]
        accion = self.por_modelo[modelo]
        if isinstance(accion, Exception):
            raise accion
        return accion


def test_modelo_saturado_pasa_al_siguiente_modelo():
    transporte = TransportePorModelo({
        "modelo-a": ErrorGemini("Gemini respondió con error HTTP 503"),
        "modelo-b": _respuesta_gemini(VALIDA),
    })
    salida = solicitar_explicacion(_seguimiento_psql(fallar_concepto="JOIN"),
                                   config=ConfigGemini(api_key="x", modelo="modelo-a, modelo-b"),
                                   transporte=transporte)
    assert salida["origen"] == "gemini" and salida["modelo"] == "modelo-b"
    assert len(transporte.llamadas) == 2


def test_clave_invalida_no_prueba_otros_modelos():
    transporte = TransportePorModelo({
        "modelo-a": ErrorGemini("la API key de Gemini no es válida (400)", reintentable=False),
        "modelo-b": _respuesta_gemini(VALIDA),
    })
    salida = solicitar_explicacion(_seguimiento_psql(fallar_concepto="JOIN"),
                                   config=ConfigGemini(api_key="x", modelo="modelo-a,modelo-b"),
                                   transporte=transporte)
    assert salida["origen"] == "local" and "API key" in salida["motivo_respaldo"]
    assert len(transporte.llamadas) == 1


def test_todos_los_modelos_fallan_reporta_cada_motivo():
    transporte = TransportePorModelo({
        "modelo-a": ErrorGemini("Gemini respondió con error HTTP 503"),
        "modelo-b": ErrorGemini("el modelo configurado en GEMINI_MODELO no existe (404)"),
    })
    salida = solicitar_explicacion(_seguimiento_psql(fallar_concepto="JOIN"),
                                   config=ConfigGemini(api_key="x", modelo="modelo-a,modelo-b"),
                                   transporte=transporte)
    assert salida["origen"] == "local"
    assert "modelo-a" in salida["motivo_respaldo"] and "modelo-b" in salida["motivo_respaldo"]


def test_errores_http_se_explican_en_lenguaje_claro():
    import io
    import urllib.error

    def error(codigo, mensaje):
        cuerpo = io.BytesIO(json.dumps({"error": {"message": mensaje}}).encode())
        return urllib.error.HTTPError("https://x", codigo, "error", {}, cuerpo)

    mensaje, reintentar = retro._analizar_error_http(
        error(400, "API key not valid. Please pass a valid API key."))
    assert "API key" in mensaje and reintentar is False
    mensaje, reintentar = retro._analizar_error_http(
        error(403, "Gemini API has not been used in project 123 before or it is disabled."))
    assert "API key" not in mensaje and reintentar is True
    assert "GEMINI_MODELO" in retro._analizar_error_http(error(404, "models/x is not found"))[0]
    assert "límite gratuito" in retro._analizar_error_http(error(429, "Resource exhausted"))[0]
    assert "saturado" in retro._analizar_error_http(error(503, "high demand"))[0]


def test_modelo_colgado_deja_tiempo_para_el_siguiente():
    class Colgado(TransportePorModelo):
        def __call__(self, url, cabeceras, cuerpo, timeout):
            if "modelo-a" in url:
                self.llamadas.append(url)
                time.sleep(3)
            return super().__call__(url, cabeceras, cuerpo, timeout)

    transporte = Colgado({"modelo-a": _respuesta_gemini(VALIDA), "modelo-b": _respuesta_gemini(VALIDA)})
    inicio = time.monotonic()
    salida = solicitar_explicacion(_seguimiento_psql(fallar_concepto="JOIN"),
                                   config=ConfigGemini(api_key="x", modelo="modelo-a,modelo-b",
                                                       timeout=2.0),
                                   transporte=transporte)
    assert salida["origen"] == "gemini" and salida["modelo"] == "modelo-b"
    assert time.monotonic() - inicio < 2.5


def test_misma_explicacion_no_se_pide_dos_veces():
    resultado = _seguimiento_psql(fallar_concepto="JOIN")
    transporte = TransporteFalso(_respuesta_gemini(VALIDA))
    config = ConfigGemini(api_key="x")
    primera = solicitar_explicacion(resultado, config=config, transporte=transporte)
    segunda = solicitar_explicacion(resultado, config=config, transporte=transporte)
    assert primera == segunda and len(transporte.llamadas) == 1


def test_config_lee_archivo_env_sin_pisar_variables(tmp_path, monkeypatch):
    archivo = tmp_path / ".env"
    archivo.write_text("GEMINI_API_KEY='desde-archivo'\nGEMINI_TIMEOUT=7\n# comentario\n",
                       encoding="utf-8")
    for var in ("GEMINI_API_KEY", "GEMINI_TIMEOUT", "GEMINI_MODELO", "GEMINI_DESACTIVADO"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(retro, "RUTA_ENV", archivo)
    config = retro.cargar_config()
    assert config.api_key == "desde-archivo" and config.timeout == 7 and config.disponible
    monkeypatch.setenv("GEMINI_DESACTIVADO", "1")
    assert retro.cargar_config().disponible is False


def test_pantalla_de_resultados_muestra_ambos_casos_igual():
    resultado = _seguimiento_psql(fallar_concepto="JOIN")
    local = renderizar_retroalimentacion(generar_retroalimentacion(resultado))
    gemini = renderizar_retroalimentacion(solicitar_explicacion(
        resultado, config=ConfigGemini(api_key="x"),
        transporte=TransporteFalso(_respuesta_gemini(VALIDA))))
    for texto in (local, gemini):
        assert "Lo que hiciste bien" in texto and "Qué puedes reforzar" in texto
        assert "Tu siguiente paso" in texto and "Material recomendado" in texto and 'href="https://' in texto
    assert "Basada en la rúbrica" in local and "Generada con IA" in gemini


# ── Contenido y calificación del tema MVC en PHP ────────────────────────────

def test_banco_mvc_cumple_el_formato_comun():
    banco = _json("ejercicios_mvc_php.json")
    lab = banco["laboratorio"]
    assert len(lab) == 4
    assert [e["dificultad"] for e in lab] == ["Principiante", "Intermedio", "Avanzado", "Integrador"]
    assert {e["concepto"] for e in lab} == set(banco["conceptos"])
    for e in lab:
        assert e["tema"] == "Patron_MVC_en_PHP" and e["tipo"] == "laboratorio"
        assert e["enunciado"] and e["criterio_evaluacion"] and e["criterios"]
        for c in e["criterios"]:
            assert c["descripcion"] and c["respuesta_correcta"] in c["opciones"]
    variantes = banco["seguimiento"]
    assert len(variantes) >= 2
    ids = [p["id"] for preguntas in variantes.values() for p in preguntas]
    assert len(ids) == len(set(ids))
    for preguntas in variantes.values():
        assert len(preguntas) == 5
        assert {p["concepto"] for p in preguntas} == set(banco["conceptos"])
        for p in preguntas:
            assert p["respuesta_correcta"] in p["opciones"] and p["dificultad"]


def test_recursos_reales_para_cada_concepto_y_rubrica_coherente():
    catalogo = _json("catalogo_recursos.json")
    rubrica = _json("rubrica_retroalimentacion.json")["temas"]
    for recurso in catalogo.values():
        assert {"titulo", "fuente", "formato", "concepto", "enlace"} <= set(recurso)
        assert recurso["enlace"].startswith("https://")
    for concepto in _json("ejercicios_mvc_php.json")["conceptos"]:
        assert any(r["concepto"] == concepto for r in catalogo.values())
        assert concepto in rubrica["Patron_MVC_en_PHP"]["conceptos"]
    for tema in rubrica.values():
        for texto in list(tema["conceptos"].values()) + [tema["general"]]:
            assert texto["recurso"] in catalogo
    for nodo in _json("grafo_conocimiento.json").values():
        assert all(rid in catalogo for rid in nodo["recursos"])
    criterios_mvc = {c["id"] for e in obtener_ejercicios_laboratorio_mvc() for c in e["criterios"]}
    assert criterios_mvc == set(rubrica["Patron_MVC_en_PHP"]["criterios"])


def test_laboratorio_mvc_reglas_de_acreditacion():
    assert _lab_mvc()["acreditado"] is True
    tres_sin_integradora = _lab_mvc(fallar={"M04-EXITO"})
    assert tres_sin_integradora["ejercicios_correctos"] == 3
    assert tres_sin_integradora["acreditado"] is False
    dos = _lab_mvc(fallar={"M01-VISTA", "M02-PASO1"})
    assert dos["acreditado"] is False
    assert dos["conceptos_con_errores"] == ["RESPONSABILIDADES_CAPA", "FLUJO_PETICION"]
    vacio = calificar_laboratorio_mvc({}, 0)
    assert vacio["ejercicios_correctos"] == 0 and vacio["detalle"][0]["error"] == "Respuesta vacía."


def test_seguimiento_mvc_misma_nota_distinto_refuerzo():
    a = _seguimiento_mvc("mvc_variante_1", {"RESPONSABILIDADES_CAPA"})
    b = _seguimiento_mvc("mvc_variante_1", {"FLUJO_PETICION", "CORRECCION_CAPA"})
    assert a["correctas"] == b["correctas"] == 3 and not a["acreditado"]
    ra, rb = generar_retroalimentacion(a), generar_retroalimentacion(b)
    assert ra["concepto"] == "RESPONSABILIDADES_CAPA"
    assert rb["concepto"] == "FLUJO_PETICION"  # empate 1-1 → orden de la rúbrica
    assert ra["pista"] != rb["pista"] and ra["recurso"]["id"] != rb["recurso"]["id"]
    assert _seguimiento_mvc("mvc_variante_2", {"INTEGRADORA_MVC"})["acreditado"] is True


def test_variantes_mvc_no_se_repiten_ni_chocan_con_postgresql():
    usadas = ["variante_1", "variante_2"]  # de PostgreSQL
    nombre, _ = obtener_variante_seguimiento_mvc(usadas)
    assert nombre == "mvc_variante_1"
    nombre2, _ = obtener_variante_seguimiento_mvc(usadas + [nombre])
    assert nombre2 == "mvc_variante_2"
    with pytest.raises(ValueError):
        obtener_variante_seguimiento_mvc(variantes_seguimiento_mvc())


def test_mvc_aprobado_aislado_se_guarda_sin_acreditar_el_tema(tmp_path):
    almacen = AlmacenProgreso(tmp_path / "progreso.json")
    almacen.iniciar("Patrón MVC en PHP", "Texto")
    estado = almacen.guardar_intento(normalizar_resultado_calificador(_lab_mvc()))
    assert "Patrón MVC en PHP" not in estado["temas_acreditados"]
    reabierto = AlmacenProgreso(tmp_path / "progreso.json").cargar()
    assert reabierto["intentos"][0]["tema"] == "Patrón MVC en PHP"


def test_motor_marca_meta_mvc_completada_al_acreditar():
    from motor import Motor
    motor = Motor()
    pendiente = motor.ruta_directa(["Lógica de Programación", "Programación Orientada a Objetos"],
                                   "Patrón MVC en PHP", "Principiante")
    assert pendiente["siguiente_tema"] == "Patrón MVC en PHP"
    completa = motor.ruta_directa(["Lógica de Programación", "Programación Orientada a Objetos",
                                   "Patrón MVC en PHP"], "Patrón MVC en PHP", "Principiante")
    assert completa["estado_meta"] == "Meta completada" and completa["ruta_pendiente"] == []
