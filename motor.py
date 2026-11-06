"""
motor.py — API interna del motor de recomendación (Integrante 1).

Responsabilidades:
  · Cargar el Recomendador (árbol, grafo, A*) una sola vez al arrancar.
  · Recibir del exterior: meta, formato preferido, temas acreditados y,
    opcionalmente, datos del último intento (nivel, tiempo, errores, fallos,
    abandono).
  · Mantener compatibilidad exacta con el preprocesamiento de recomendador.py.
  · Ejecutar A* al iniciar el diagnóstico, al acreditar un tema, al cambiar
    la meta y al recuperar una simulación.
  · Coordinar árbol + grafo: si el árbol dice «Avanzar» pero faltan
    prerrequisitos, esos quedan pendientes; la recomendación sigue siendo
    coherente con el estado del grafo.
  · Resolver el cierre: cuando la meta ya está en «completados», devuelve
    estado «Meta completada» y ruta_pendiente = [].

Interfaz pública
────────────────
  motor = Motor()                       # carga una vez
  resultado = motor.consultar(...)      # invocación por evento
  resultado = motor.acreditar(tema, ...)# al aprobar un tema
  resultado = motor.cambiar_meta(meta, ...)
  resultado = motor.recuperar(snapshot) # al reanudar simulación guardada
"""

from __future__ import annotations

import os
from typing import Any

from recomendador import (
    NODO_A_TEMA,
    TEMA_A_NODO,
    Recomendador,
    desbloqueados,
    ruta_a_estrella,
)

# Rutas por defecto (relativas al directorio del proyecto)
_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DEFAULT = os.path.join(_DIR, "telemetria_estudiantes_simulada.csv")
JSON_DEFAULT = os.path.join(_DIR, "grafo_conocimiento.json")


# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------
class Motor:
    """
    Motor de recomendación: punto de entrada único para la aplicación.

    Parámetros
    ----------
    ruta_csv : str
        Ruta al CSV de telemetría simulada.
    ruta_json : str
        Ruta al JSON del grafo de conocimiento.
    max_depth : int
        Profundidad máxima del árbol de decisión.
    """

    def __init__(
        self,
        ruta_csv: str = CSV_DEFAULT,
        ruta_json: str = JSON_DEFAULT,
        max_depth: int = 4,
    ):
        self._rec = Recomendador(ruta_csv, ruta_json, max_depth)
        print(
            f"[Motor] Cargado: {len(self._rec.grafo)} temas en el grafo, "
            f"{len(self._rec.df)} registros de telemetría."
        )

    # ------------------------------------------------------------------
    # Propiedades de solo lectura expuestas a la interfaz
    # ------------------------------------------------------------------
    @property
    def temas(self) -> list[str]:
        """Lista de temas legibles (en el mismo orden que el grafo)."""
        return list(TEMA_A_NODO.keys())

    @property
    def grafo(self):
        return self._rec.grafo

    # ------------------------------------------------------------------
    # Método principal: consultar / calcular ruta
    # ------------------------------------------------------------------
    def consultar(
        self,
        nivel: str,
        formato: str,
        tema: str,
        tiempo: float,
        errores: float,
        completados: list[str] = (),
        meta: str = "Backend con Node.js",
        fallos: int = 0,
        abandono: bool = False,
    ) -> dict[str, Any]:
        """
        Calcula la recomendación completa y la ruta A* actualizada.

        Siempre se llama cuando:
          · El estudiante inicia el diagnóstico inicial.
          · El estudiante cambia de meta.
          · Se recupera una simulación guardada.

        Devuelve un dict con las mismas claves de Recomendador.recomendar()
        más las claves adicionales:
          · estado_meta   : «Meta completada» | «En progreso»
          · ruta_pendiente: pasos que aún faltan hacia la meta
          · siguiente_tema: próximo tema disponible (o None si meta completa)
          · bloqueados    : temas que no se pueden estudiar aún
        """
        comp_nodos = {TEMA_A_NODO[c] for c in completados if c in TEMA_A_NODO}
        meta_nodo = TEMA_A_NODO.get(meta)

        # ── Cierre de ruta ──────────────────────────────────────────────
        if meta_nodo and meta_nodo in comp_nodos:
            return self._resultado_meta_completada(meta, comp_nodos, meta_nodo)

        # ── Recomendación normal ─────────────────────────────────────────
        resultado = self._rec.recomendar(
            nivel=nivel,
            formato=formato,
            tema=tema,
            tiempo=tiempo,
            errores=errores,
            completados=list(completados),
            meta=meta,
            fallos=fallos,
            abandono=abandono,
        )

        # ── Coherencia árbol ↔ grafo ─────────────────────────────────────
        # Si el árbol dice «Avanzar» pero el tema actual tiene prerrequisitos
        # pendientes, la acción real sigue siendo «Estudiar prerrequisito».
        nodo_actual = TEMA_A_NODO.get(tema)
        if nodo_actual and nodo_actual not in comp_nodos:
            faltan_pre = [
                p
                for p in self._rec.grafo[nodo_actual]["prerrequisitos"]
                if p not in comp_nodos
            ]
            if faltan_pre and resultado["tipo_arbol"] == "Avanzado":
                resultado["accion"] = "Estudiar prerrequisito"
                resultado["motivos"].append(
                    "Árbol sugiere avanzar, pero quedan prerrequisitos: "
                    + ", ".join(NODO_A_TEMA[p] for p in faltan_pre)
                    + ". La ruta sigue el grafo."
                )

        # ── Metadatos de ruta ────────────────────────────────────────────
        ruta = resultado.get("ruta", [])
        desb = desbloqueados(self._rec.grafo, comp_nodos)
        bloqueados = [
            NODO_A_TEMA[n]
            for n in self._rec.grafo
            if n not in comp_nodos and n not in desb
        ]
        siguiente = ruta[0] if ruta else None

        resultado["estado_meta"] = "En progreso"
        resultado["ruta_pendiente"] = ruta
        resultado["siguiente_tema"] = siguiente
        resultado["bloqueados"] = bloqueados
        return resultado

    # ------------------------------------------------------------------
    # Evento: el estudiante acreditó un tema
    # ------------------------------------------------------------------
    def acreditar(
        self,
        tema_acreditado: str,
        nivel: str,
        formato: str,
        completados: list[str],
        meta: str = "Backend con Node.js",
        tiempo: float = 150.0,
        errores: float = 20.0,
    ) -> dict[str, Any]:
        """
        Llama A* con la lista de completados actualizada (ya incluye tema_acreditado).
        Se invoca cada vez que el estudiante aprueba un tema.
        """
        nuevos_completados = list(set(completados) | {tema_acreditado})
        return self.consultar(
            nivel=nivel,
            formato=formato,
            tema=tema_acreditado,
            tiempo=tiempo,
            errores=errores,
            completados=nuevos_completados,
            meta=meta,
            fallos=0,
            abandono=False,
        )

    # ------------------------------------------------------------------
    # Evento: el estudiante cambió de meta
    # ------------------------------------------------------------------
    def cambiar_meta(
        self,
        nueva_meta: str,
        nivel: str,
        formato: str,
        tema: str,
        tiempo: float,
        errores: float,
        completados: list[str] = (),
        fallos: int = 0,
        abandono: bool = False,
    ) -> dict[str, Any]:
        """Recalcula la ruta A* con la nueva meta."""
        return self.consultar(
            nivel=nivel,
            formato=formato,
            tema=tema,
            tiempo=tiempo,
            errores=errores,
            completados=list(completados),
            meta=nueva_meta,
            fallos=fallos,
            abandono=abandono,
        )

    # ------------------------------------------------------------------
    # Evento: recuperar simulación guardada
    # ------------------------------------------------------------------
    def recuperar(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """
        Restaura el estado desde un snapshot (dict serializable).

        El snapshot debe contener al menos:
            nivel, formato, tema, tiempo, errores,
            completados, meta, fallos, abandono
        """
        return self.consultar(**snapshot)

    # ------------------------------------------------------------------
    # Ruta directa (sin árbol): solo A* desde el estado actual
    # ------------------------------------------------------------------
    def ruta_directa(
        self,
        completados: list[str],
        meta: str,
        nivel: str,
    ) -> dict[str, Any]:
        """
        Devuelve la ruta A* pura sin pasar por el árbol.
        Útil para actualizar el widget de ruta sin reclasificar al estudiante.
        """
        comp_nodos = {TEMA_A_NODO[c] for c in completados if c in TEMA_A_NODO}
        meta_nodo = TEMA_A_NODO.get(meta)

        if meta_nodo and meta_nodo in comp_nodos:
            return {
                "estado_meta": "Meta completada",
                "ruta_pendiente": [],
                "siguiente_tema": None,
                "bloqueados": [],
                "costo_ruta": 0.0,
                "estados_explorados": 0,
            }

        ruta, costo, explorados = ruta_a_estrella(
            self._rec.grafo, comp_nodos, meta_nodo, nivel
        )
        desb = desbloqueados(self._rec.grafo, comp_nodos)
        bloqueados = [
            NODO_A_TEMA[n]
            for n in self._rec.grafo
            if n not in comp_nodos and n not in desb
        ]
        ruta_legible = [NODO_A_TEMA[n] for n in (ruta or [])]
        return {
            "estado_meta": "En progreso",
            "ruta_pendiente": ruta_legible,
            "siguiente_tema": ruta_legible[0] if ruta_legible else None,
            "bloqueados": bloqueados,
            "costo_ruta": costo,
            "estados_explorados": explorados,
        }

    # ------------------------------------------------------------------
    # Verificar bloqueo de Node.js
    # ------------------------------------------------------------------
    def verificar_bloqueo_nodejs(self, completados: list[str]) -> dict[str, Any]:
        """
        Comprueba si Backend con Node.js sigue bloqueado.
        Node.js requiere POO **y** PostgreSQL.

        Devuelve:
            bloqueado  : bool
            requisitos_faltantes : list[str]
            mensaje    : str legible
        """
        comp_nodos = {TEMA_A_NODO[c] for c in completados if c in TEMA_A_NODO}
        nodo_node = "Backend_con_Nodejs"
        req = self._rec.grafo[nodo_node]["prerrequisitos"]
        faltantes = [NODO_A_TEMA[r] for r in req if r not in comp_nodos]
        bloqueado = len(faltantes) > 0
        if bloqueado:
            msg = (
                f"Backend con Node.js está BLOQUEADO. "
                f"Faltan: {', '.join(faltantes)}."
            )
        else:
            msg = "Backend con Node.js está DESBLOQUEADO."
        return {"bloqueado": bloqueado, "requisitos_faltantes": faltantes, "mensaje": msg}

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _resultado_meta_completada(
        self, meta: str, comp_nodos: set, meta_nodo: str
    ) -> dict[str, Any]:
        """Resultado estándar cuando la meta ya está completada."""
        desb = desbloqueados(self._rec.grafo, comp_nodos)
        return {
            "estado_meta": "Meta completada",
            "ruta_pendiente": [],
            "siguiente_tema": None,
            "bloqueados": [],
            "desbloqueados": [NODO_A_TEMA[n] for n in desb],
            "meta": meta,
            "tipo_apoyo": "Avanzado",
            "accion": "Meta completada",
            "motivos": [f"El estudiante ya acreditó «{meta}». ¡Felicidades!"],
            "reglas": [],
            "recursos": [],
            "ruta_detalle": [],
            "ruta": [],
            "costo_ruta": 0.0,
            "estados_explorados": 0,
            "confianza": 1.0,
            "tema_recomendado": meta,
        }

