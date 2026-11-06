"""Adaptador único entre calificador.py y el formato persistente del integrante 4."""
import json
from pathlib import Path

from calificador import (calificar_laboratorio as calificar_laboratorio_integrante3,
                         calificar_seguimiento as calificar_seguimiento_integrante3)
from recomendador import NODO_A_TEMA

BASE = Path(__file__).resolve().parent
BANCO = BASE / "ejercicios_postgresql.json"


def variantes_seguimiento():
    with BANCO.open(encoding="utf-8") as archivo:
        return sorted(json.load(archivo)["seguimiento"])


def preguntas_seguimiento(variante):
    with BANCO.open(encoding="utf-8") as archivo:
        banco = json.load(archivo)
    try:
        return banco["seguimiento"][variante]
    except KeyError as exc:
        raise ValueError(f"Variante de seguimiento desconocida: {variante}") from exc


def normalizar_resultado_calificador(resultado):
    """Mapea una salida real de calificador al contrato de AlmacenProgreso."""
    if not isinstance(resultado, dict):
        raise ValueError("El calificador debe devolver un diccionario")
    requeridos = ("intento", "tema", "tipo", "puntaje", "tiempo",
                 "conceptos_con_errores", "acreditado")
    faltan = [campo for campo in requeridos if campo not in resultado]
    if faltan:
        raise ValueError(f"Salida del calificador incompleta: faltan {', '.join(faltan)}")

    tema = NODO_A_TEMA.get(resultado["tema"], resultado["tema"])
    tipo = resultado["tipo"]
    if tipo == "laboratorio":
        tipo_actividad = "Diagnóstico (laboratorio)"
    elif tipo == "seguimiento":
        tipo_actividad = "Actividad de seguimiento"
    else:
        raise ValueError(f"Tipo de actividad del calificador desconocido: {tipo}")
    if "puntaje_obtenido" in resultado and "puntaje_maximo" in resultado:
        # Algunos laboratorios (como Node.js) ponderan criterios: no todos los
        # ejercicios valen lo mismo. Conserva esa escala sin afectar PostgreSQL.
        aciertos = resultado["puntaje_obtenido"]
        total = resultado["puntaje_maximo"]
    elif tipo == "laboratorio":
        aciertos = resultado.get("ejercicios_correctos")
        total = resultado.get("total_ejercicios")
    elif tipo == "seguimiento":
        aciertos = resultado.get("correctas")
        total = resultado.get("total_preguntas")
    if not isinstance(aciertos, int) or not isinstance(total, int) or total <= 0:
        raise ValueError("El calificador debe informar conteo de aciertos y total")

    normalizado = {
        "id": str(resultado["intento"]),
        "tema": tema,
        "tipo_actividad": tipo_actividad,
        "puntaje": aciertos,
        "puntaje_maximo": total,
        "puntaje_proporcion": resultado["puntaje"],
        "tiempo_segundos": resultado["tiempo"],
        "conceptos_con_error": resultado["conceptos_con_errores"],
        "aprobado": resultado["acreditado"],
        "criterios_cumplidos": resultado.get("criterios_cumplidos", []),
        "criterios_incumplidos": resultado.get("criterios_incumplidos", []),
        "detalle": resultado.get("detalle", []),
    }
    if "variante" in resultado:
        normalizado["variante"] = resultado["variante"]
    return normalizado


def calificar_laboratorio(respuestas, tiempo_segundos):
    bruto = calificar_laboratorio_integrante3(respuestas, tiempo_segundos)
    return normalizar_resultado_calificador(bruto)


def calificar_seguimiento_real(respuestas, tiempo_segundos, variante):
    bruto = calificar_seguimiento_integrante3(respuestas, tiempo_segundos, variante)
    return normalizar_resultado_calificador(bruto)
