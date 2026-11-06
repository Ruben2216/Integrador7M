"""Genera resultados ficticios para mostrar el flujo antes del calificador real."""


def construir_resultado_demo(id_intento, tema, tipo, puntaje, minutos, conceptos):
    puntaje = int(puntaje)
    minutos = float(minutos)
    if conceptos is None:
        conceptos = ""
    if not isinstance(conceptos, str):
        raise ValueError("Los conceptos de error de demostración deben ser texto")
    conceptos = [x.strip() for x in conceptos.split(",") if x.strip()]
    return {
        "id": str(id_intento or "").strip(),
        "tema": tema,
        "tipo_actividad": tipo,
        "puntaje": puntaje,
        "tiempo_segundos": int(minutos * 60),
        "conceptos_con_error": conceptos,
        # Regla exclusiva de demostración. El calificador real debe enviar aprobado.
        "aprobado": puntaje >= 4,
        "criterios_cumplidos": f"{puntaje} de 5; criterio de demostración: 4 de 5",
    }


def construir_retroalimentacion_demo():
    return {
        "comentario": "Salida ficticia del adaptador local de demostración.",
        "pista": "Revisa los conceptos que aparecen como error antes del siguiente intento.",
    }
