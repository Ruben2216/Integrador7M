"""
Generador del conjunto de telemetría simulada.

Produce un CSV con registros sintéticos de la interacción de estudiantes con una
plataforma de aprendizaje. La etiqueta `Recurso_Recomendado_ID` se construye a
partir de un puntaje de refuerzo que combina la tasa de errores, el nivel previo y
el tiempo de interacción, más ruido gaussiano. El formato del recurso coincide con
el formato preferido en la mayoría de los casos y difiere en una fracción de ellos.

Los datos NO corresponden a estudiantes reales.

Uso:  python generar_datos.py
"""
import numpy as np
import pandas as pd

NIVELES = ["Principiante", "Intermedio", "Avanzado"]
P_NIVEL = [0.33, 0.36, 0.31]

FORMATOS = ["Visual", "Texto", "Práctico"]
P_FORMATO = [0.33, 0.25, 0.42]

# Tema -> (probabilidad, abreviatura usada en el identificador del recurso)
TEMAS = {
    "Lógica de Programación": (0.28, "LÓGI"),
    "Programación Orientada a Objetos": (0.16, "PROG"),
    "Bases de Datos PostgreSQL": (0.22, "BASE"),
    "Backend con Node.js": (0.24, "BACK"),
    "Patrón MVC en PHP": (0.10, "PATR"),
}

MEDIA_ERRORES = {"Principiante": 55, "Intermedio": 47, "Avanzado": 40}   # por nivel
DESV_ERRORES = 25
AJUSTE_NIVEL = {"Principiante": 8, "Intermedio": 0, "Avanzado": -8}      # puntos de puntaje
PESO_TIEMPO = 0.05                  # puntos de puntaje por segundo respecto de 150 s
UMBRAL_REFUERZO = 60
RUIDO_PUNTAJE = 7.0
PROB_FORMATO_DISTINTO = 0.15
PROPORCION_NULOS = 0.05


def generar(n=100, semilla=42):
    rng = np.random.default_rng(semilla)
    nivel = rng.choice(NIVELES, n, p=P_NIVEL)
    formato = rng.choice(FORMATOS, n, p=P_FORMATO)
    temas = list(TEMAS)
    tema = rng.choice(temas, n, p=[TEMAS[t][0] for t in temas])

    errores = np.clip(
        np.array([rng.normal(MEDIA_ERRORES[x], DESV_ERRORES) for x in nivel]),
        0.5, 99.5).round(2)

    tiempo = rng.integers(10, 300, n).astype(float)
    tiempo[rng.choice(n, int(PROPORCION_NULOS * n), replace=False)] = np.nan

    tiempo_ref = np.where(np.isnan(tiempo), 150, tiempo)
    puntaje = (errores
               + np.array([AJUSTE_NIVEL[x] for x in nivel])
               - PESO_TIEMPO * (tiempo_ref - 150)
               + rng.normal(0, RUIDO_PUNTAJE, n))
    tipo = np.where(puntaje > UMBRAL_REFUERZO, "Refuerzo", "Avanzado")

    formato_recurso = [
        f if rng.random() > PROB_FORMATO_DISTINTO
        else rng.choice([x for x in FORMATOS if x != f])
        for f in formato
    ]
    recurso = [f"{t}_{f}_{TEMAS[tm][1]}" for t, f, tm in zip(tipo, formato_recurso, tema)]

    return pd.DataFrame({
        "ID_Estudiante": range(1, n + 1),
        "Nivel_Previo": nivel,
        "Formato_Preferido": formato,
        "Tema_Actual": tema,
        "Tiempo_Interaccion_Segundos": tiempo,
        "Tasa_Errores": errores,
        "Recurso_Recomendado_ID": recurso,
    })


if __name__ == "__main__":
    generar().to_csv("telemetria_estudiantes_simulada.csv", index=False)
