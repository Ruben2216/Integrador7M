"""
calificador.py — Módulo de calificación para el tema PostgreSQL (Integrante 3).

Responsabilidades:
  · Cargar el banco de ejercicios de PostgreSQL desde ejercicios_postgresql.json.
  · Ejecutar consultas SQL del estudiante contra una base SQLite3 en memoria.
  · Comparar resultados sin importar el orden de las filas.
  · Devolver un resultado uniforme por intento (serializable a JSON).
  · Entregar variantes de seguimiento sin repetir las ya usadas.

Funciones públicas:
  calificar_laboratorio(respuestas, tiempo, ...) -> dict
  calificar_seguimiento(respuestas, tiempo, variante_usada, ...) -> dict
  obtener_variante_seguimiento(variantes_usadas) -> tuple[str, list[dict]]
  obtener_ejercicios_laboratorio() -> list[dict]
  obtener_conceptos() -> list[str]

El módulo NO modifica app.py, recomendador.py ni archivos de otros integrantes.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Constantes configurables
# ─────────────────────────────────────────────────────────────────────────────

# Lista canónica de conceptos evaluados en PostgreSQL.
# El integrante 5 (pistas) puede importarla:  from calificador import CONCEPTOS_POSTGRESQL
CONCEPTOS_POSTGRESQL: list[str] = ["WHERE", "JOIN", "GROUP_BY", "INTEGRADORA"]

# Regla de acreditación del laboratorio (propuesta — el equipo debe aprobarla):
# Se requieren al menos MIN_EJERCICIOS_APROBADOS de 4 correctos,
# Y la integradora (PSQL-LAB04) DEBE estar aprobada.
MIN_EJERCICIOS_APROBADOS: int = 3
INTEGRADORA_OBLIGATORIA: bool = True

# Seguimiento: aprueba con al menos esta cantidad de respuestas correctas (de 5).
MIN_SEGUIMIENTO_CORRECTAS: int = 4

# Patrón para detectar sentencias peligrosas (DDL / DML destructivo).
_PATRON_PELIGROSO = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|REPLACE)\b",
    re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# Carga del banco de ejercicios
# ─────────────────────────────────────────────────────────────────────────────

_DIR = os.path.dirname(os.path.abspath(__file__))
_RUTA_BANCO = os.path.join(_DIR, "ejercicios_postgresql.json")


def _cargar_banco() -> dict:
    """Carga el archivo JSON del banco de ejercicios."""
    with open(_RUTA_BANCO, encoding="utf-8") as f:
        return json.load(f)


def obtener_ejercicios_laboratorio() -> list[dict]:
    """Devuelve la lista de los 4 ejercicios del laboratorio de PostgreSQL."""
    return _cargar_banco()["laboratorio"]


def obtener_conceptos() -> list[str]:
    """Devuelve la lista canónica de conceptos de PostgreSQL."""
    return list(CONCEPTOS_POSTGRESQL)


# ─────────────────────────────────────────────────────────────────────────────
# Variantes de seguimiento
# ─────────────────────────────────────────────────────────────────────────────

def obtener_variante_seguimiento(
    variantes_usadas: list[str] | None = None,
) -> tuple[str, list[dict]]:
    """
    Entrega la siguiente variante de seguimiento SIN repetir las ya usadas.

    Parámetros
    ----------
    variantes_usadas : list[str]
        Nombres de variantes ya utilizadas, p. ej. ["variante_1"].

    Retorna
    -------
    (nombre_variante, lista_de_preguntas)
        Si ya se usaron todas las variantes disponibles, lanza ValueError.
    """
    if variantes_usadas is None:
        variantes_usadas = []

    banco = _cargar_banco()
    seguimiento = banco["seguimiento"]
    disponibles = [k for k in sorted(seguimiento.keys()) if k not in variantes_usadas]

    if not disponibles:
        raise ValueError(
            "No hay variantes de seguimiento disponibles. "
            f"Ya se usaron: {variantes_usadas}"
        )

    nombre = disponibles[0]
    return nombre, seguimiento[nombre]


# ─────────────────────────────────────────────────────────────────────────────
# Motor de ejecución SQL seguro (SQLite3 en memoria)
# ─────────────────────────────────────────────────────────────────────────────

def _crear_base_temporal(esquema_sql: str) -> sqlite3.Connection:
    """
    Crea una base SQLite3 en memoria y ejecuta el esquema provisto.

    La base se reconstruye en cada calificación para evitar efectos
    secundarios entre ejercicios.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    # Ejecutar cada sentencia del esquema por separado
    for sentencia in esquema_sql.split(";"):
        sentencia = sentencia.strip()
        if sentencia:
            conn.execute(sentencia + ";")
    conn.commit()
    return conn


def _es_consulta_peligrosa(sql: str) -> bool:
    """Detecta sentencias DDL/DML destructivas (DROP, DELETE, UPDATE, etc.)."""
    # Eliminar comentarios de línea y de bloque para una inspección limpia
    limpio = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    limpio = re.sub(r"/\*.*?\*/", "", limpio, flags=re.DOTALL)
    return bool(_PATRON_PELIGROSO.search(limpio))


def _ejecutar_sql(sql: str, conn: sqlite3.Connection) -> tuple[list[str], list[tuple]]:
    """
    Ejecuta una consulta SQL de solo lectura en la conexión dada.

    Retorna
    -------
    (columnas, filas) donde columnas es la lista de nombres de columna
    y filas es la lista de tuplas de valores.

    Lanza ValueError si la consulta es vacía, peligrosa o inválida.
    """
    sql = sql.strip()
    if not sql:
        raise ValueError("La consulta está vacía.")

    if _es_consulta_peligrosa(sql):
        raise ValueError(
            "La consulta contiene sentencias no permitidas "
            "(DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE, REPLACE)."
        )

    try:
        cursor = conn.execute(sql)
        columnas = [desc[0] for desc in cursor.description] if cursor.description else []
        filas = cursor.fetchall()
        return columnas, filas
    except Exception as exc:
        raise ValueError(f"Error al ejecutar la consulta: {exc}") from exc


def _comparar_resultados(
    filas_estudiante: list[tuple],
    filas_esperadas: list[tuple],
) -> bool:
    """
    Compara dos conjuntos de filas SIN importar el orden.

    Los valores se normalizan a cadena para evitar diferencias de tipo
    entre int/float/str.
    """
    def normalizar(fila: tuple) -> tuple:
        partes = []
        for v in fila:
            if v is None:
                partes.append(None)
            elif isinstance(v, float):
                # Redondear para evitar problemas de precisión
                partes.append(round(v, 4))
            else:
                partes.append(v)
        return tuple(partes)

    set_est = sorted([normalizar(f) for f in filas_estudiante], key=str)
    set_esp = sorted([normalizar(f) for f in filas_esperadas], key=str)
    return set_est == set_esp


# ─────────────────────────────────────────────────────────────────────────────
# Calificación del laboratorio
# ─────────────────────────────────────────────────────────────────────────────

def calificar_laboratorio(
    respuestas: dict[str, str],
    tiempo: float,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Califica los ejercicios del laboratorio de PostgreSQL.

    Parámetros
    ----------
    respuestas : dict[str, str]
        Diccionario {id_ejercicio: consulta_sql_del_estudiante}.
        Ejemplo: {"PSQL-LAB01": "SELECT nombre, correo FROM clientes WHERE ciudad='Guadalajara';"}
    tiempo : float
        Tiempo total en segundos que tardó el estudiante (medido por la interfaz).

    Retorna
    -------
    dict serializable a JSON con el resultado del intento.
    """
    ejercicios = obtener_ejercicios_laboratorio()
    ejercicios_por_id = {ej["id"]: ej for ej in ejercicios}

    intento_id = str(uuid.uuid4())
    criterios_cumplidos: list[str] = []
    criterios_incumplidos: list[str] = []
    conceptos_con_errores: list[str] = []
    detalle_ejercicios: list[dict] = []
    ejercicios_correctos = 0

    for ej in ejercicios:
        ej_id = ej["id"]
        sql_estudiante = respuestas.get(ej_id, "")
        ej_resultado = {
            "id": ej_id,
            "concepto": ej["concepto"],
            "correcto": False,
            "criterios_cumplidos": [],
            "criterios_incumplidos": [],
            "error": None,
        }

        if not sql_estudiante or not sql_estudiante.strip():
            # Respuesta vacía → todo incumplido
            for crit in ej["criterios"]:
                ej_resultado["criterios_incumplidos"].append(crit["id"])
                criterios_incumplidos.append(crit["id"])
            ej_resultado["error"] = "Respuesta vacía."
            if ej["concepto"] not in conceptos_con_errores:
                conceptos_con_errores.append(ej["concepto"])
            detalle_ejercicios.append(ej_resultado)
            continue

        if _es_consulta_peligrosa(sql_estudiante):
            for crit in ej["criterios"]:
                ej_resultado["criterios_incumplidos"].append(crit["id"])
                criterios_incumplidos.append(crit["id"])
            ej_resultado["error"] = "Consulta contiene sentencias no permitidas."
            if ej["concepto"] not in conceptos_con_errores:
                conceptos_con_errores.append(ej["concepto"])
            detalle_ejercicios.append(ej_resultado)
            continue

        # Crear base fresca para este ejercicio
        try:
            conn = _crear_base_temporal(ej["esquema_sql"])
        except Exception as exc:
            for crit in ej["criterios"]:
                ej_resultado["criterios_incumplidos"].append(crit["id"])
                criterios_incumplidos.append(crit["id"])
            ej_resultado["error"] = f"Error al preparar la base de datos: {exc}"
            if ej["concepto"] not in conceptos_con_errores:
                conceptos_con_errores.append(ej["concepto"])
            detalle_ejercicios.append(ej_resultado)
            continue

        try:
            # Ejecutar la consulta del estudiante
            cols_est, filas_est = _ejecutar_sql(sql_estudiante, conn)

            # Ejecutar la respuesta esperada para obtener el resultado de referencia
            cols_esp, filas_esp = _ejecutar_sql(ej["respuesta_esperada_sql"], conn)

            # Verificar criterios
            ejercicio_correcto = True

            for crit in ej["criterios"]:
                cumplido = False

                if crit["verificacion"] == "resultado_coincide":
                    cumplido = _comparar_resultados(filas_est, filas_esp)

                elif crit["verificacion"] == "columnas_correctas":
                    # Verificar que las columnas son las mismas (sin importar alias)
                    cumplido = len(cols_est) == len(cols_esp)

                elif crit["verificacion"] == "contiene_nulos":
                    # Verificar que hay al menos un NULL en los resultados
                    cumplido = any(None in fila for fila in filas_est)

                elif crit["verificacion"] == "sin_nulos_en_agregados":
                    # Verificar que no hay NULLs en columnas numéricas (agregados)
                    # Las columnas de agregación son las que no son 'nombre'
                    if filas_est:
                        cumplido = all(
                            all(v is not None for v in fila[1:])
                            for fila in filas_est
                        )
                    else:
                        cumplido = False

                if cumplido:
                    ej_resultado["criterios_cumplidos"].append(crit["id"])
                    criterios_cumplidos.append(crit["id"])
                else:
                    ej_resultado["criterios_incumplidos"].append(crit["id"])
                    criterios_incumplidos.append(crit["id"])
                    ejercicio_correcto = False

            ej_resultado["correcto"] = ejercicio_correcto
            if ejercicio_correcto:
                ejercicios_correctos += 1
            else:
                if ej["concepto"] not in conceptos_con_errores:
                    conceptos_con_errores.append(ej["concepto"])

        except ValueError as exc:
            for crit in ej["criterios"]:
                ej_resultado["criterios_incumplidos"].append(crit["id"])
                criterios_incumplidos.append(crit["id"])
            ej_resultado["error"] = str(exc)
            if ej["concepto"] not in conceptos_con_errores:
                conceptos_con_errores.append(ej["concepto"])

        finally:
            conn.close()

        detalle_ejercicios.append(ej_resultado)

    # Determinar acreditación
    total_ejercicios = len(ejercicios)
    puntaje = round(ejercicios_correctos / total_ejercicios, 2) if total_ejercicios else 0.0

    # Verificar si la integradora está aprobada
    integradora_aprobada = any(
        d["id"] == "PSQL-LAB04" and d["correcto"] for d in detalle_ejercicios
    )

    if INTEGRADORA_OBLIGATORIA:
        acreditado = (
            ejercicios_correctos >= MIN_EJERCICIOS_APROBADOS
            and integradora_aprobada
        )
    else:
        acreditado = ejercicios_correctos >= MIN_EJERCICIOS_APROBADOS

    return {
        "intento": intento_id,
        "tema": "Bases_de_Datos_PostgreSQL",
        "tipo": "laboratorio",
        "puntaje": puntaje,
        "tiempo": tiempo,
        "ejercicios_correctos": ejercicios_correctos,
        "total_ejercicios": total_ejercicios,
        "criterios_cumplidos": criterios_cumplidos,
        "criterios_incumplidos": criterios_incumplidos,
        "conceptos_con_errores": conceptos_con_errores,
        "acreditado": acreditado,
        "detalle": detalle_ejercicios,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Calificación del seguimiento
# ─────────────────────────────────────────────────────────────────────────────

def calificar_seguimiento(
    respuestas: dict[str, str],
    tiempo: float,
    variante_usada: str = "variante_1",
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Califica la actividad de seguimiento (5 preguntas de opción múltiple).

    Parámetros
    ----------
    respuestas : dict[str, str]
        Diccionario {id_pregunta: respuesta_seleccionada}.
        Ejemplo: {"PSQL-SEG-V1-01": "SELECT * FROM productos WHERE precio > 100;"}
    tiempo : float
        Tiempo total en segundos.
    variante_usada : str
        Nombre de la variante que se está calificando (p. ej. "variante_1").

    Retorna
    -------
    dict serializable a JSON con el resultado del intento de seguimiento.
    """
    banco = _cargar_banco()
    preguntas = banco["seguimiento"].get(variante_usada, [])

    if not preguntas:
        raise ValueError(f"Variante '{variante_usada}' no encontrada en el banco.")

    intento_id = str(uuid.uuid4())
    correctas = 0
    criterios_cumplidos: list[str] = []
    criterios_incumplidos: list[str] = []
    conceptos_con_errores: list[str] = []
    detalle_preguntas: list[dict] = []

    for preg in preguntas:
        preg_id = preg["id"]
        respuesta_est = respuestas.get(preg_id, "")
        es_correcta = respuesta_est.strip() == preg["respuesta_correcta"].strip()

        detalle = {
            "id": preg_id,
            "concepto": preg["concepto"],
            "correcto": es_correcta,
        }

        if es_correcta:
            correctas += 1
            criterios_cumplidos.append(preg_id)
        else:
            criterios_incumplidos.append(preg_id)
            if preg["concepto"] not in conceptos_con_errores:
                conceptos_con_errores.append(preg["concepto"])

        detalle_preguntas.append(detalle)

    total = len(preguntas)
    puntaje = round(correctas / total, 2) if total else 0.0
    acreditado = correctas >= MIN_SEGUIMIENTO_CORRECTAS

    return {
        "intento": intento_id,
        "tema": "Bases_de_Datos_PostgreSQL",
        "tipo": "seguimiento",
        "puntaje": puntaje,
        "tiempo": tiempo,
        "correctas": correctas,
        "total_preguntas": total,
        "criterios_cumplidos": criterios_cumplidos,
        "criterios_incumplidos": criterios_incumplidos,
        "conceptos_con_errores": conceptos_con_errores,
        "acreditado": acreditado,
        "variante": variante_usada,
        "detalle": detalle_preguntas,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Ejecución directa: muestra un resumen del banco
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Banco de ejercicios de PostgreSQL ===\n")

    ejercicios = obtener_ejercicios_laboratorio()
    print(f"{'ID':<15} {'Concepto':<15} {'Dificultad':<15} Enunciado (resumen)")
    print("─" * 80)
    for ej in ejercicios:
        resumen = ej["enunciado"][:50] + "…" if len(ej["enunciado"]) > 50 else ej["enunciado"]
        print(f"{ej['id']:<15} {ej['concepto']:<15} {ej['dificultad']:<15} {resumen}")

    print(f"\nConceptos evaluados: {CONCEPTOS_POSTGRESQL}")
    print(f"Regla de acreditación: ≥ {MIN_EJERCICIOS_APROBADOS}/4 correctos", end="")
    if INTEGRADORA_OBLIGATORIA:
        print(" + integradora obligatoria")
    else:
        print()

    print(f"\nVariantes de seguimiento disponibles:")
    banco = _cargar_banco()
    for k, v in banco["seguimiento"].items():
        print(f"  {k}: {len(v)} preguntas")

