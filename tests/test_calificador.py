"""
tests/test_calificador.py — Pruebas automatizadas para el módulo calificador.py
Integrante 3 — PostgreSQL.

Ejecutar:
    pytest tests/test_calificador.py -v

Cobertura de pruebas:
  1. Laboratorio aprobado (4/4 correctos).
  2. Laboratorio reprobado (1/4 correctos, integradora incorrecta).
  3. Laboratorio reprobado (3/4 correctos, pero integradora incorrecta).
  4. Orden de filas irrelevante en la comparación de resultados.
  5. LEFT JOIN vs INNER JOIN: mismo esquema, resultado distinto.
  6. SQL inválido → puntaje 0 sin romper el programa.
  7. SQL peligroso (DROP, DELETE, UPDATE) → puntaje 0 sin romper el programa.
  8. Respuesta vacía → puntaje 0.
  9. Dos intentos de seguimiento con 3/5: errores de JOIN vs errores de WHERE
     dan MISMO puntaje pero DISTINTOS conceptos_con_errores.
  10. Variantes de seguimiento sin repetición.
  11. Identificadores de intento únicos (uuid4).
"""

import json
import os
import sys
import uuid

import pytest

# Asegurar que el directorio raíz del proyecto esté en el path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from calificador import (
    CONCEPTOS_POSTGRESQL,
    MIN_EJERCICIOS_APROBADOS,
    MIN_SEGUIMIENTO_CORRECTAS,
    calificar_laboratorio,
    calificar_seguimiento,
    obtener_ejercicios_laboratorio,
    obtener_variante_seguimiento,
    obtener_conceptos,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def ejercicios_lab():
    """Carga los ejercicios del laboratorio."""
    return obtener_ejercicios_laboratorio()


@pytest.fixture
def respuestas_correctas():
    """Respuestas SQL correctas para los 4 ejercicios del laboratorio."""
    return {
        "PSQL-LAB01": "SELECT nombre, correo FROM clientes WHERE ciudad = 'Guadalajara';",
        "PSQL-LAB02": "SELECT clientes.nombre, pedidos.total FROM clientes LEFT JOIN pedidos ON clientes.id = pedidos.cliente_id;",
        "PSQL-LAB03": "SELECT ciudad, COUNT(*) AS cantidad FROM clientes GROUP BY ciudad ORDER BY cantidad DESC;",
        "PSQL-LAB04": (
            "SELECT clientes.nombre, COUNT(pedidos.id) AS cantidad_pedidos, "
            "COALESCE(SUM(pedidos.total), 0) AS monto_total "
            "FROM clientes LEFT JOIN pedidos ON clientes.id = pedidos.cliente_id "
            "GROUP BY clientes.nombre ORDER BY monto_total DESC;"
        ),
    }


@pytest.fixture
def preguntas_seguimiento_v1():
    """Carga las preguntas de la variante 1 del seguimiento."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "ejercicios_postgresql.json"), encoding="utf-8") as f:
        banco = json.load(f)
    return banco["seguimiento"]["variante_1"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Laboratorio aprobado (4/4 correctos)
# ─────────────────────────────────────────────────────────────────────────────

class TestLaboratorioAprobado:
    """Pruebas para un laboratorio completamente correcto."""

    def test_laboratorio_4_de_4_aprobado(self, respuestas_correctas):
        """Con las 4 respuestas correctas, el laboratorio debe acreditar."""
        resultado = calificar_laboratorio(respuestas_correctas, tiempo=300.0)

        assert resultado["acreditado"] is True
        assert resultado["puntaje"] == 1.0
        assert resultado["ejercicios_correctos"] == 4
        assert resultado["total_ejercicios"] == 4
        assert resultado["conceptos_con_errores"] == []
        assert resultado["tema"] == "Bases_de_Datos_PostgreSQL"
        assert resultado["tipo"] == "laboratorio"

    def test_resultado_serializable_a_json(self, respuestas_correctas):
        """El resultado debe ser serializable a JSON sin errores."""
        resultado = calificar_laboratorio(respuestas_correctas, tiempo=300.0)
        # Esto lanza TypeError si algún valor no es serializable
        serializado = json.dumps(resultado, ensure_ascii=False)
        assert isinstance(serializado, str)

    def test_tiempo_se_registra(self, respuestas_correctas):
        """El tiempo recibido como parámetro se incluye en el resultado."""
        resultado = calificar_laboratorio(respuestas_correctas, tiempo=245.5)
        assert resultado["tiempo"] == 245.5


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Laboratorio reprobado (solo 1 correcto)
# ─────────────────────────────────────────────────────────────────────────────

class TestLaboratorioReprobado:
    """Pruebas para un laboratorio con pocas respuestas correctas."""

    def test_laboratorio_1_de_4_reprobado(self):
        """Con solo 1 respuesta correcta, el laboratorio NO acredita."""
        respuestas = {
            "PSQL-LAB01": "SELECT nombre, correo FROM clientes WHERE ciudad = 'Guadalajara';",
            "PSQL-LAB02": "SELECT * FROM clientes;",  # incorrecta
            "PSQL-LAB03": "SELECT * FROM clientes;",  # incorrecta
            "PSQL-LAB04": "SELECT * FROM clientes;",  # incorrecta
        }
        resultado = calificar_laboratorio(respuestas, tiempo=200.0)

        assert resultado["acreditado"] is False
        assert resultado["ejercicios_correctos"] == 1
        assert len(resultado["conceptos_con_errores"]) > 0

    def test_laboratorio_3_sin_integradora_reprobado(self, respuestas_correctas):
        """3 de 4 correctos PERO integradora incorrecta → NO acredita."""
        respuestas = dict(respuestas_correctas)
        respuestas["PSQL-LAB04"] = "SELECT * FROM clientes;"  # integradora incorrecta
        resultado = calificar_laboratorio(respuestas, tiempo=200.0)

        assert resultado["acreditado"] is False
        assert resultado["ejercicios_correctos"] == 3
        assert "INTEGRADORA" in resultado["conceptos_con_errores"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Orden de filas irrelevante
# ─────────────────────────────────────────────────────────────────────────────

class TestOrdenFilas:
    """El orden de las filas NO debe afectar la calificación."""

    def test_orden_distinto_es_correcto(self):
        """Una consulta con ORDER BY diferente sigue siendo correcta si las filas coinciden."""
        # LAB01: cambiar el ORDER BY no debería afectar el resultado
        # La consulta devuelve las mismas filas pero sin un ORDER BY específico
        respuestas = {
            "PSQL-LAB01": (
                "SELECT nombre, correo FROM clientes "
                "WHERE ciudad = 'Guadalajara' ORDER BY nombre DESC;"
            ),
            "PSQL-LAB02": (
                "SELECT clientes.nombre, pedidos.total "
                "FROM clientes LEFT JOIN pedidos ON clientes.id = pedidos.cliente_id "
                "ORDER BY clientes.nombre;"
            ),
            "PSQL-LAB03": "SELECT ciudad, COUNT(*) AS cnt FROM clientes GROUP BY ciudad ORDER BY cnt DESC;",
            "PSQL-LAB04": (
                "SELECT clientes.nombre, COUNT(pedidos.id) AS cp, "
                "COALESCE(SUM(pedidos.total), 0) AS mt "
                "FROM clientes LEFT JOIN pedidos ON clientes.id = pedidos.cliente_id "
                "GROUP BY clientes.nombre ORDER BY mt DESC;"
            ),
        }
        resultado = calificar_laboratorio(respuestas, tiempo=300.0)
        # LAB01 debe ser correcto porque las filas coinciden independientemente del orden
        lab01 = next(d for d in resultado["detalle"] if d["id"] == "PSQL-LAB01")
        assert lab01["correcto"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: LEFT JOIN vs INNER JOIN
# ─────────────────────────────────────────────────────────────────────────────

class TestLeftJoinVsInnerJoin:
    """Un INNER JOIN pierde clientes sin pedidos; LEFT JOIN los conserva."""

    def test_inner_join_falla_criterio_join(self):
        """INNER JOIN en LAB02 → el criterio de LEFT JOIN no se cumple."""
        respuestas = {
            "PSQL-LAB01": "SELECT nombre, correo FROM clientes WHERE ciudad = 'Guadalajara';",
            "PSQL-LAB02": (
                "SELECT clientes.nombre, pedidos.total "
                "FROM clientes INNER JOIN pedidos ON clientes.id = pedidos.cliente_id;"
            ),
            "PSQL-LAB03": "SELECT ciudad, COUNT(*) AS cantidad FROM clientes GROUP BY ciudad ORDER BY cantidad DESC;",
            "PSQL-LAB04": (
                "SELECT clientes.nombre, COUNT(pedidos.id) AS cantidad_pedidos, "
                "COALESCE(SUM(pedidos.total), 0) AS monto_total "
                "FROM clientes LEFT JOIN pedidos ON clientes.id = pedidos.cliente_id "
                "GROUP BY clientes.nombre ORDER BY monto_total DESC;"
            ),
        }
        resultado = calificar_laboratorio(respuestas, tiempo=250.0)

        lab02 = next(d for d in resultado["detalle"] if d["id"] == "PSQL-LAB02")
        assert lab02["correcto"] is False
        assert "C02-JOIN" in lab02["criterios_incumplidos"]
        assert "JOIN" in resultado["conceptos_con_errores"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: SQL inválido
# ─────────────────────────────────────────────────────────────────────────────

class TestSQLInvalido:
    """Consultas con errores de sintaxis deben dar puntaje 0 sin romper el programa."""

    def test_sql_con_error_sintaxis(self):
        """Una consulta con error de sintaxis no rompe el calificador."""
        respuestas = {
            "PSQL-LAB01": "SELECCT nombre correo FORM clientes WERE ciudad = 'Guadalajara';",
            "PSQL-LAB02": "esto no es SQL",
            "PSQL-LAB03": "SELECT *** FROM;",
            "PSQL-LAB04": "",
        }
        resultado = calificar_laboratorio(respuestas, tiempo=100.0)

        assert resultado["puntaje"] == 0.0
        assert resultado["acreditado"] is False
        assert resultado["ejercicios_correctos"] == 0
        # Verificar que todos los ejercicios tienen errores reportados
        for detalle in resultado["detalle"]:
            assert detalle["correcto"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: SQL peligroso (DROP, DELETE, UPDATE)
# ─────────────────────────────────────────────────────────────────────────────

class TestSQLPeligroso:
    """Consultas peligrosas (DDL/DML) deben dar puntaje 0 sin romper el programa."""

    @pytest.mark.parametrize("sql_peligroso", [
        "DROP TABLE clientes;",
        "DELETE FROM clientes;",
        "UPDATE clientes SET nombre = 'Hacked';",
        "INSERT INTO clientes VALUES (99, 'x', 'x', 'x');",
        "ALTER TABLE clientes ADD COLUMN hack TEXT;",
        "CREATE TABLE hack (id INT);",
        "TRUNCATE TABLE clientes;",
    ])
    def test_sql_peligroso_da_puntaje_cero(self, sql_peligroso):
        """Cada tipo de sentencia peligrosa da puntaje 0 sin errores."""
        respuestas = {
            "PSQL-LAB01": sql_peligroso,
            "PSQL-LAB02": "SELECT nombre FROM clientes;",
            "PSQL-LAB03": "SELECT nombre FROM clientes;",
            "PSQL-LAB04": "SELECT nombre FROM clientes;",
        }
        resultado = calificar_laboratorio(respuestas, tiempo=50.0)

        lab01 = next(d for d in resultado["detalle"] if d["id"] == "PSQL-LAB01")
        assert lab01["correcto"] is False
        assert lab01["error"] == "Consulta contiene sentencias no permitidas."


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Respuesta vacía
# ─────────────────────────────────────────────────────────────────────────────

class TestRespuestaVacia:
    """Respuestas vacías deben reportar error sin romper el programa."""

    def test_todas_vacias(self):
        """Todas las respuestas vacías → puntaje 0."""
        respuestas = {
            "PSQL-LAB01": "",
            "PSQL-LAB02": "",
            "PSQL-LAB03": "   ",
            "PSQL-LAB04": "",
        }
        resultado = calificar_laboratorio(respuestas, tiempo=10.0)

        assert resultado["puntaje"] == 0.0
        assert resultado["acreditado"] is False

    def test_respuestas_faltantes(self):
        """Si faltan IDs en el dict de respuestas, se tratan como vacías."""
        respuestas = {
            "PSQL-LAB01": "SELECT nombre, correo FROM clientes WHERE ciudad = 'Guadalajara';",
            # Faltan LAB02, LAB03, LAB04
        }
        resultado = calificar_laboratorio(respuestas, tiempo=60.0)

        assert resultado["ejercicios_correctos"] <= 1
        assert resultado["acreditado"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: PRUEBA CLAVE — Dos intentos de seguimiento con 3/5,
#          mismo puntaje, distintos conceptos_con_errores
# ─────────────────────────────────────────────────────────────────────────────

class TestSeguimientoDosIntentos:
    """
    Prueba clave: dos intentos con 3/5 correctas producen el MISMO puntaje
    pero DISTINTOS conceptos_con_errores (uno falla en JOIN, otro en WHERE).
    """

    def test_mismo_puntaje_distintos_errores(self, preguntas_seguimiento_v1):
        """
        Intento A: errores en las preguntas de JOIN (PSQL-SEG-V1-02, V1-05).
        Intento B: errores en las preguntas de WHERE (PSQL-SEG-V1-01, V1-04).
        Ambos tienen 3 de 5, pero conceptos_con_errores distintos.
        """
        # Intento A: responde MAL las dos preguntas de JOIN, bien lo demás
        respuestas_a = {}
        for preg in preguntas_seguimiento_v1:
            if preg["concepto"] == "JOIN":
                # Dar respuesta incorrecta
                respuestas_a[preg["id"]] = "RESPUESTA INCORRECTA"
            else:
                respuestas_a[preg["id"]] = preg["respuesta_correcta"]

        resultado_a = calificar_seguimiento(
            respuestas_a, tiempo=120.0, variante_usada="variante_1"
        )

        # Intento B: responde MAL las dos preguntas de WHERE, bien lo demás
        respuestas_b = {}
        for preg in preguntas_seguimiento_v1:
            if preg["concepto"] == "WHERE":
                respuestas_b[preg["id"]] = "RESPUESTA INCORRECTA"
            else:
                respuestas_b[preg["id"]] = preg["respuesta_correcta"]

        resultado_b = calificar_seguimiento(
            respuestas_b, tiempo=130.0, variante_usada="variante_1"
        )

        # MISMO puntaje (3/5 = 0.6 en ambos)
        assert resultado_a["puntaje"] == resultado_b["puntaje"]
        assert resultado_a["correctas"] == 3
        assert resultado_b["correctas"] == 3

        # DISTINTOS conceptos con errores
        assert resultado_a["conceptos_con_errores"] != resultado_b["conceptos_con_errores"]
        assert "JOIN" in resultado_a["conceptos_con_errores"]
        assert "JOIN" not in resultado_b["conceptos_con_errores"]
        assert "WHERE" in resultado_b["conceptos_con_errores"]
        assert "WHERE" not in resultado_a["conceptos_con_errores"]

    def test_seguimiento_no_acredita_con_3_de_5(self, preguntas_seguimiento_v1):
        """Con 3 de 5 correctas, el seguimiento NO debe acreditar (requiere 4)."""
        respuestas = {}
        for preg in preguntas_seguimiento_v1:
            if preg["concepto"] == "JOIN":
                respuestas[preg["id"]] = "RESPUESTA INCORRECTA"
            else:
                respuestas[preg["id"]] = preg["respuesta_correcta"]

        resultado = calificar_seguimiento(
            respuestas, tiempo=120.0, variante_usada="variante_1"
        )

        assert resultado["acreditado"] is False
        assert resultado["correctas"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: Seguimiento aprobado (5/5 y 4/5)
# ─────────────────────────────────────────────────────────────────────────────

class TestSeguimientoAprobado:
    """Pruebas para seguimiento con suficientes respuestas correctas."""

    def test_seguimiento_5_de_5_aprueba(self, preguntas_seguimiento_v1):
        """Con 5/5 correctas, el seguimiento acredita."""
        respuestas = {
            preg["id"]: preg["respuesta_correcta"]
            for preg in preguntas_seguimiento_v1
        }
        resultado = calificar_seguimiento(
            respuestas, tiempo=90.0, variante_usada="variante_1"
        )

        assert resultado["acreditado"] is True
        assert resultado["puntaje"] == 1.0
        assert resultado["correctas"] == 5

    def test_seguimiento_4_de_5_aprueba(self, preguntas_seguimiento_v1):
        """Con 4/5 correctas, el seguimiento acredita."""
        respuestas = {
            preg["id"]: preg["respuesta_correcta"]
            for preg in preguntas_seguimiento_v1
        }
        # Poner una incorrecta (la primera pregunta de GROUP_BY)
        id_a_fallar = next(
            preg["id"] for preg in preguntas_seguimiento_v1
            if preg["concepto"] == "GROUP_BY"
        )
        respuestas[id_a_fallar] = "RESPUESTA INCORRECTA"

        resultado = calificar_seguimiento(
            respuestas, tiempo=100.0, variante_usada="variante_1"
        )

        assert resultado["acreditado"] is True
        assert resultado["correctas"] == 4


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: Variantes sin repetición
# ─────────────────────────────────────────────────────────────────────────────

class TestVariantesSinRepeticion:
    """Las variantes de seguimiento no deben repetirse."""

    def test_tres_variantes_distintas(self):
        """Se pueden obtener 3 variantes distintas sin repetir."""
        usadas = []
        for _ in range(3):
            nombre, preguntas = obtener_variante_seguimiento(usadas)
            assert nombre not in usadas
            assert len(preguntas) == 5
            usadas.append(nombre)

        # Las tres deben ser distintas
        assert len(set(usadas)) == 3

    def test_error_al_agotar_variantes(self):
        """Si se agotaron todas las variantes, lanza ValueError."""
        with pytest.raises(ValueError, match="No hay variantes"):
            obtener_variante_seguimiento(
                ["variante_1", "variante_2", "variante_3"]
            )

    def test_variantes_tienen_ids_distintos(self):
        """Cada variante tiene IDs de pregunta distintos."""
        _, preguntas_v1 = obtener_variante_seguimiento([])
        _, preguntas_v2 = obtener_variante_seguimiento(["variante_1"])
        ids_v1 = {p["id"] for p in preguntas_v1}
        ids_v2 = {p["id"] for p in preguntas_v2}
        assert ids_v1.isdisjoint(ids_v2)


# ─────────────────────────────────────────────────────────────────────────────
# Test 11: Identificadores de intento únicos (uuid4)
# ─────────────────────────────────────────────────────────────────────────────

class TestIdentificadoresUnicos:
    """Cada llamada a calificar genera un ID de intento único (uuid4)."""

    def test_ids_laboratorio_unicos(self, respuestas_correctas):
        """Dos calificaciones seguidas del laboratorio tienen IDs distintos."""
        r1 = calificar_laboratorio(respuestas_correctas, tiempo=200.0)
        r2 = calificar_laboratorio(respuestas_correctas, tiempo=200.0)

        assert r1["intento"] != r2["intento"]
        # Verificar que son UUID válidos
        uuid.UUID(r1["intento"])
        uuid.UUID(r2["intento"])

    def test_ids_seguimiento_unicos(self, preguntas_seguimiento_v1):
        """Dos calificaciones seguidas del seguimiento tienen IDs distintos."""
        respuestas = {
            preg["id"]: preg["respuesta_correcta"]
            for preg in preguntas_seguimiento_v1
        }
        r1 = calificar_seguimiento(respuestas, tiempo=90.0, variante_usada="variante_1")
        r2 = calificar_seguimiento(respuestas, tiempo=90.0, variante_usada="variante_1")

        assert r1["intento"] != r2["intento"]
        uuid.UUID(r1["intento"])
        uuid.UUID(r2["intento"])

    def test_id_entre_laboratorio_y_seguimiento(self, respuestas_correctas, preguntas_seguimiento_v1):
        """El ID del laboratorio y del seguimiento también son distintos."""
        r_lab = calificar_laboratorio(respuestas_correctas, tiempo=200.0)
        resp_seg = {
            preg["id"]: preg["respuesta_correcta"]
            for preg in preguntas_seguimiento_v1
        }
        r_seg = calificar_seguimiento(resp_seg, tiempo=90.0, variante_usada="variante_1")

        assert r_lab["intento"] != r_seg["intento"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 12: Conceptos y estructura del banco
# ─────────────────────────────────────────────────────────────────────────────

class TestEstructuraBanco:
    """Verifica la estructura del banco de ejercicios."""

    def test_conceptos_postgresql_definidos(self):
        """La constante CONCEPTOS_POSTGRESQL contiene los conceptos esperados."""
        assert "WHERE" in CONCEPTOS_POSTGRESQL
        assert "JOIN" in CONCEPTOS_POSTGRESQL
        assert "GROUP_BY" in CONCEPTOS_POSTGRESQL
        assert "INTEGRADORA" in CONCEPTOS_POSTGRESQL

    def test_obtener_conceptos(self):
        """obtener_conceptos() devuelve la lista canónica."""
        conceptos = obtener_conceptos()
        assert conceptos == CONCEPTOS_POSTGRESQL

    def test_laboratorio_tiene_4_ejercicios(self):
        """El banco del laboratorio tiene exactamente 4 ejercicios."""
        ejercicios = obtener_ejercicios_laboratorio()
        assert len(ejercicios) == 4

    def test_ejercicios_tienen_campos_obligatorios(self):
        """Cada ejercicio del laboratorio tiene todos los campos requeridos."""
        campos = ["id", "tema", "tipo", "concepto", "dificultad", "enunciado",
                   "respuesta_esperada_sql", "criterios"]
        ejercicios = obtener_ejercicios_laboratorio()
        for ej in ejercicios:
            for campo in campos:
                assert campo in ej, f"Falta '{campo}' en ejercicio {ej.get('id', '?')}"

    def test_tema_usa_clave_grafo(self):
        """El campo 'tema' usa la clave con guion bajo del grafo, no el nombre legible."""
        ejercicios = obtener_ejercicios_laboratorio()
        for ej in ejercicios:
            assert ej["tema"] == "Bases_de_Datos_PostgreSQL"

    def test_catalogo_recursos_existe(self):
        """El catálogo de recursos JSON existe y contiene las llaves del grafo."""
        ruta = os.path.join(_ROOT, "catalogo_recursos.json")
        with open(ruta, encoding="utf-8") as f:
            catalogo = json.load(f)
        # Debe contener al menos las llaves del grafo
        assert "Recurso_Video_DB" in catalogo
        assert "Recurso_Practica_DB" in catalogo
        # Cada recurso tiene los campos requeridos
        for rid, rec in catalogo.items():
            assert "titulo" in rec
            assert "fuente" in rec
            assert "formato" in rec
            assert "concepto" in rec
            assert "enlace" in rec

