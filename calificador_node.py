"""Calificación determinista del banco de Backend con Node.js (Integrante 4)."""
from __future__ import annotations

import json
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
BANCO_NODE = BASE / "ejercicios_node.json"
MIN_PUNTOS_LABORATORIO = 4
MIN_SEGUIMIENTO_CORRECTAS = 4


def _banco() -> dict[str, Any]:
    with BANCO_NODE.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def obtener_ejercicios_laboratorio_node() -> list[dict[str, Any]]:
    return _banco()["laboratorio"]


def obtener_variantes_seguimiento_node() -> list[str]:
    return [f"node-variante-{indice}" for indice in (1, 2)]


def obtener_variante_seguimiento_node(
    variantes_usadas: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    banco = _banco()["seguimiento"]["variantes"]
    usadas = set(variantes_usadas or [])
    for indice, preguntas in enumerate(banco, start=1):
        nombre = f"node-variante-{indice}"
        if nombre not in usadas:
            return nombre, preguntas
    raise ValueError("Ya se usaron las dos variantes de seguimiento de Node.js.")


def preguntas_seguimiento_node(variante: str) -> list[dict[str, Any]]:
    try:
        indice = int(variante.rsplit("-", 1)[1]) - 1
        preguntas = _banco()["seguimiento"]["variantes"][indice]
    except (ValueError, IndexError, KeyError) as exc:
        raise ValueError(f"Variante de seguimiento Node.js desconocida: {variante}") from exc
    if variante not in obtener_variantes_seguimiento_node():
        raise ValueError(f"Variante de seguimiento Node.js desconocida: {variante}")
    return preguntas


def _normalizar(texto: Any) -> str:
    texto = str(texto or "").strip().lower()
    texto = "".join(
        caracter for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )
    return re.sub(r"\s+", " ", texto)


def _cumple_lab(ejercicio_id: str, respuesta: str) -> tuple[list[str], list[str]]:
    texto = _normalizar(respuesta)
    compacto = re.sub(r"\s+", "", texto)
    cumplidos: list[str] = []
    incumplidos: list[str] = []

    def criterio(identificador: str, correcto: bool) -> None:
        (cumplidos if correcto else incumplidos).append(identificador)

    if ejercicio_id == "node-lab-01":
        criterio("N01-HTTP-GET", bool(re.search(r"\bget\b", texto)))
        criterio("N01-HTTP-200", bool(re.search(r"\b200\b", texto)))
    elif ejercicio_id == "node-lab-02":
        ruta = bool(re.search(r"/libros/:(?:id|libroid)\b", texto))
        parametro = bool(re.search(r"req\.params(?:\.id|\[['\"]id['\"]\])", compacto))
        criterio("N02-ROUTE-PARAM", ruta and parametro)
    elif ejercicio_id == "node-lab-03":
        nombre_obligatorio = "nombre" in texto and any(
            palabra in texto for palabra in ("obligatorio", "requerido", "no vacio", "required", "not empty")
        )
        estado_error = bool(re.search(r"\b(400|422)\b", texto))
        no_persistir = any(
            frase in texto for frase in (
                "no crear", "sin crear", "no guardar", "sin guardar", "no persistir",
                "sin persistir", "no registrar", "sin registrar", "antes de guardar",
                "antes de persistir",
            )
        )
        criterio("N03-VALIDATE-BEFORE-SAVE", nombre_obligatorio and no_persistir)
        criterio("N03-HTTP-ERROR", estado_error)
    elif ejercicio_id == "node-lab-04":
        crear = (
            bool(re.search(r"\bpost\b", texto))
            and "/productos" in compacto
            and bool(re.search(r"\b201\b", texto))
        )
        consultar = (
            bool(re.search(r"\bget\b", texto))
            and "/productos" in compacto
            and bool(re.search(r"\b200\b", texto))
        )
        criterio("N04-POST-CREATE-201", crear)
        criterio("N04-GET-LIST-200", consultar)
    else:
        raise ValueError(f"Ejercicio Node.js desconocido: {ejercicio_id}")
    return cumplidos, incumplidos


def calificar_laboratorio_node(
    respuestas: dict[str, str], tiempo_segundos: float
) -> dict[str, Any]:
    ejercicios = obtener_ejercicios_laboratorio_node()
    detalle: list[dict[str, Any]] = []
    criterios_ok: list[str] = []
    criterios_no: list[str] = []
    conceptos_error: list[str] = []
    puntaje = 0

    for ejercicio in ejercicios:
        ej_id = ejercicio["id"]
        correctos, incorrectos = _cumple_lab(ej_id, respuestas.get(ej_id, ""))
        # LAB04 aporta dos puntos; los otros ejercicios aportan uno cada uno.
        puntos = len(correctos) if ej_id == "node-lab-04" else int(not incorrectos)
        puntaje += puntos
        criterios_ok.extend(correctos)
        criterios_no.extend(incorrectos)
        correcto = not incorrectos
        if not correcto and ejercicio["concepto"] not in conceptos_error:
            conceptos_error.append(ejercicio["concepto"])
        detalle.append({
            "id": ej_id,
            "concepto": ejercicio["concepto"],
            "correcto": correcto,
            "puntaje": puntos,
            "puntaje_maximo": ejercicio["rubrica"]["puntos"],
            "criterios_cumplidos": correctos,
            "criterios_incumplidos": incorrectos,
        })

    total = sum(ejercicio["rubrica"]["puntos"] for ejercicio in ejercicios)
    return {
        "intento": str(uuid.uuid4()),
        "tema": "Backend con Node.js",
        "tipo": "laboratorio",
        "puntaje": round(puntaje / total, 2) if total else 0.0,
        "puntaje_obtenido": puntaje,
        "puntaje_maximo": total,
        "tiempo": max(0.0, float(tiempo_segundos)),
        "ejercicios_correctos": sum(item["correcto"] for item in detalle),
        "total_ejercicios": len(ejercicios),
        "criterios_cumplidos": criterios_ok,
        "criterios_incumplidos": criterios_no,
        "conceptos_con_errores": conceptos_error,
        "acreditado": puntaje >= MIN_PUNTOS_LABORATORIO,
        "detalle": detalle,
    }


def calificar_seguimiento_node(
    respuestas: dict[str, str], tiempo_segundos: float, variante: str
) -> dict[str, Any]:
    preguntas = preguntas_seguimiento_node(variante)
    detalle: list[dict[str, Any]] = []
    criterios_ok: list[str] = []
    criterios_no: list[str] = []
    conceptos_error: list[str] = []
    correctas = 0
    for pregunta in preguntas:
        pregunta_id = pregunta["id"]
        correcto = _normalizar(respuestas.get(pregunta_id, "")) == _normalizar(pregunta["respuesta"])
        if correcto:
            correctas += 1
            criterios_ok.append(pregunta_id)
        else:
            criterios_no.append(pregunta_id)
            if pregunta["concepto"] not in conceptos_error:
                conceptos_error.append(pregunta["concepto"])
        detalle.append({
            "id": pregunta_id,
            "concepto": pregunta["concepto"],
            "correcto": correcto,
        })
    total = len(preguntas)
    return {
        "intento": str(uuid.uuid4()),
        "tema": "Backend con Node.js",
        "tipo": "seguimiento",
        "puntaje": round(correctas / total, 2) if total else 0.0,
        "tiempo": max(0.0, float(tiempo_segundos)),
        "correctas": correctas,
        "total_preguntas": total,
        "criterios_cumplidos": criterios_ok,
        "criterios_incumplidos": criterios_no,
        "conceptos_con_errores": conceptos_error,
        "acreditado": correctas >= MIN_SEGUIMIENTO_CORRECTAS,
        "variante": variante,
        "detalle": detalle,
    }
