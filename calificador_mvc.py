"""
calificador_mvc.py — Calificación del tema
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from calificador import (INTEGRADORA_OBLIGATORIA, MIN_EJERCICIOS_APROBADOS,
                         MIN_SEGUIMIENTO_CORRECTAS)

TEMA_MVC = "Patron_MVC_en_PHP"
RUTA_BANCO_MVC = Path(__file__).resolve().parent / "ejercicios_mvc_php.json"
ID_INTEGRADORA = "MVC-LAB04"


def _cargar_banco() -> dict:
    with RUTA_BANCO_MVC.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def obtener_ejercicios_laboratorio_mvc() -> list[dict]:
    return _cargar_banco()["laboratorio"]


def obtener_conceptos_mvc() -> dict[str, str]:
    """Clave del concepto -> nombre legible."""
    return dict(_cargar_banco()["conceptos"])


def variantes_seguimiento_mvc() -> list[str]:
    return sorted(_cargar_banco()["seguimiento"])


def obtener_variante_seguimiento_mvc(
    variantes_usadas: list[str] | None = None,
) -> tuple[str, list[dict]]:
    """Siguiente variante de MVC sin repetir las usadas (ValueError si se agotan)."""
    usadas = set(variantes_usadas or [])
    seguimiento = _cargar_banco()["seguimiento"]
    disponibles = [nombre for nombre in sorted(seguimiento) if nombre not in usadas]
    if not disponibles:
        raise ValueError(
            "No hay variantes de seguimiento de MVC disponibles. "
            f"Ya se usaron: {sorted(usadas & set(seguimiento))}"
        )
    return disponibles[0], seguimiento[disponibles[0]]


def _limpio(valor: Any) -> str:
    return str(valor or "").strip()


def calificar_laboratorio_mvc(respuestas: dict[str, str], tiempo: float,
                              **_: Any) -> dict[str, Any]:
    """
    respuestas: {id_criterio: opción elegida}, p. ej. {"M01-MODELO": "Modelo", ...}
    """
    respuestas = respuestas or {}
    criterios_cumplidos: list[str] = []
    criterios_incumplidos: list[str] = []
    conceptos_con_errores: list[str] = []
    detalle: list[dict] = []
    correctos = 0

    ejercicios = obtener_ejercicios_laboratorio_mvc()
    for ejercicio in ejercicios:
        item = {"id": ejercicio["id"], "concepto": ejercicio["concepto"], "correcto": False,
                "criterios_cumplidos": [], "criterios_incumplidos": [], "error": None}
        sin_respuesta = 0
        for criterio in ejercicio["criterios"]:
            elegida = _limpio(respuestas.get(criterio["id"]))
            if not elegida:
                sin_respuesta += 1
            if elegida == criterio["respuesta_correcta"].strip():
                item["criterios_cumplidos"].append(criterio["id"])
                criterios_cumplidos.append(criterio["id"])
            else:
                item["criterios_incumplidos"].append(criterio["id"])
                criterios_incumplidos.append(criterio["id"])
        if sin_respuesta == len(ejercicio["criterios"]):
            item["error"] = "Respuesta vacía."
        item["correcto"] = not item["criterios_incumplidos"]
        if item["correcto"]:
            correctos += 1
        elif ejercicio["concepto"] not in conceptos_con_errores:
            conceptos_con_errores.append(ejercicio["concepto"])
        detalle.append(item)

    total = len(ejercicios)
    integradora_ok = any(d["id"] == ID_INTEGRADORA and d["correcto"] for d in detalle)
    acreditado = correctos >= MIN_EJERCICIOS_APROBADOS and (
        integradora_ok or not INTEGRADORA_OBLIGATORIA
    )
    return {
        "intento": str(uuid.uuid4()),
        "tema": TEMA_MVC,
        "tipo": "laboratorio",
        "puntaje": round(correctos / total, 2) if total else 0.0,
        "tiempo": tiempo,
        "ejercicios_correctos": correctos,
        "total_ejercicios": total,
        "criterios_cumplidos": criterios_cumplidos,
        "criterios_incumplidos": criterios_incumplidos,
        "conceptos_con_errores": conceptos_con_errores,
        "acreditado": acreditado,
        "detalle": detalle,
    }


def calificar_seguimiento_mvc(respuestas: dict[str, str], tiempo: float,
                              variante_usada: str = "mvc_variante_1",
                              **_: Any) -> dict[str, Any]:
    """respuestas: {id_pregunta: opción elegida}. Aprueba con 4 de 5."""
    preguntas = _cargar_banco()["seguimiento"].get(variante_usada)
    if not preguntas:
        raise ValueError(f"Variante '{variante_usada}' no encontrada en el banco de MVC.")
    respuestas = respuestas or {}
    correctas = 0
    cumplidos: list[str] = []
    incumplidos: list[str] = []
    conceptos_con_errores: list[str] = []
    detalle: list[dict] = []
    for pregunta in preguntas:
        ok = _limpio(respuestas.get(pregunta["id"])) == pregunta["respuesta_correcta"].strip()
        detalle.append({"id": pregunta["id"], "concepto": pregunta["concepto"], "correcto": ok})
        if ok:
            correctas += 1
            cumplidos.append(pregunta["id"])
        else:
            incumplidos.append(pregunta["id"])
            if pregunta["concepto"] not in conceptos_con_errores:
                conceptos_con_errores.append(pregunta["concepto"])
    total = len(preguntas)
    return {
        "intento": str(uuid.uuid4()),
        "tema": TEMA_MVC,
        "tipo": "seguimiento",
        "puntaje": round(correctas / total, 2) if total else 0.0,
        "tiempo": tiempo,
        "correctas": correctas,
        "total_preguntas": total,
        "criterios_cumplidos": cumplidos,
        "criterios_incumplidos": incumplidos,
        "conceptos_con_errores": conceptos_con_errores,
        "acreditado": correctas >= MIN_SEGUIMIENTO_CORRECTAS,
        "variante": variante_usada,
        "detalle": detalle,
    }
