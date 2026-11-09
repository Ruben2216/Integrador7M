"""Persistencia local de una simulación de aprendizaje (sin login ni BD)."""
from __future__ import annotations

import json
import math
from numbers import Real
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

VERSION = 2
ETAPAS = ("basico", "intermedio", "avanzado", "integradora")
NOMBRES_ETAPAS = {"basico": "Básico", "intermedio": "Intermedio",
                  "avanzado": "Avanzado", "integradora": "Práctica integradora"}
NIVELES = ("Principiante", "Intermedio", "Avanzado")
FORMATOS = ("Visual", "Texto", "Práctico")
TEMAS = (
    "Lógica de Programación", "Programación Orientada a Objetos",
    "Bases de Datos PostgreSQL", "Backend con Node.js", "Patrón MVC en PHP",
)


class ErrorProgreso(RuntimeError):
    """El archivo de progreso existe pero no es válido o no puede actualizarse."""


def estado_inicial():
    return {
        "version": VERSION,
        "simulacion_activa": False,
        "meta": "Backend con Node.js",
        "formato_preferido": "Visual",
        "nivel": "Principiante",
        "tema_actual": "Lógica de Programación",
        "temas_acreditados": {},
        "intentos": [],
        "perfil": {"tiempo_interaccion_segundos": 120, "tasa_errores": 50},
        "actualizado_en": None,
    }


class AlmacenProgreso:
    def __init__(self, ruta="progreso.json"):
        self.ruta = Path(ruta)

    def cargar(self):
        if not self.ruta.exists():
            return estado_inicial()
        try:
            with self.ruta.open(encoding="utf-8") as archivo:
                estado = json.load(archivo)
            self._validar(estado)
            if estado["version"] == 1:
                # La migración se guarda solo durante la próxima escritura normal.
                estado["version"] = VERSION
                for acreditacion in estado["temas_acreditados"].values():
                    acreditacion["legado"] = True
            return estado
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ErrorProgreso(
                f"No se pudo leer {self.ruta}. Se conserva intacto; corrige o respalda el archivo antes de continuar. ({exc})"
            ) from exc

    @staticmethod
    def _validar(estado):
        if not isinstance(estado, dict) or estado.get("version") not in (1, VERSION):
            raise ValueError("formato o versión no reconocidos")
        if not isinstance(estado.get("intentos"), list) or not isinstance(estado.get("temas_acreditados"), dict):
            raise ValueError("estructura de intentos/acreditaciones inválida")
        if estado.get("meta") not in TEMAS or estado.get("formato_preferido") not in FORMATOS:
            raise ValueError("meta o formato preferido inválido")

    def guardar(self, estado):
        self._validar(estado)
        estado["version"] = VERSION
        temporal = None
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.ruta.parent,
                                             prefix=self.ruta.name + ".", suffix=".tmp", delete=False) as f:
                temporal = f.name
                json.dump(estado, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporal, self.ruta)
        except OSError as exc:
            if temporal and os.path.exists(temporal):
                try:
                    os.unlink(temporal)
                except OSError:
                    pass
            raise ErrorProgreso(f"No se pudo guardar {self.ruta}; el último archivo válido se conserva. ({exc})") from exc
        return estado

    def iniciar(self, meta, formato, nivel="Principiante"):
        if meta not in TEMAS or formato not in FORMATOS or nivel not in NIVELES:
            raise ValueError("Meta, formato o nivel inválido")
        estado = self.cargar()
        estado.update(simulacion_activa=True, meta=meta, formato_preferido=formato, nivel=nivel)
        estado["actualizado_en"] = datetime.now(timezone.utc).isoformat()
        return self.guardar(estado)

    def cambiar_meta(self, meta):
        estado = self.cargar()
        if meta not in TEMAS:
            raise ValueError("Meta inválida")
        estado.update(meta=meta, simulacion_activa=True,
                      actualizado_en=datetime.now(timezone.utc).isoformat())
        return self.guardar(estado)

    def guardar_intento(self, resultado):
        """Guarda un intento; solo cuatro etapas aprobadas acreditan temas nuevos."""
        requeridos = ("id", "tema", "tipo_actividad", "puntaje", "tiempo_segundos",
                      "conceptos_con_error", "aprobado")
        if not isinstance(resultado, dict) or any(k not in resultado for k in requeridos):
            raise ValueError(f"Resultado incompleto; requiere {', '.join(requeridos)}")
        if not isinstance(resultado["id"], (str, int)) or not str(resultado["id"]).strip():
            raise ValueError("El ID del intento debe ser texto o número y no puede estar vacío")
        if resultado["tema"] not in TEMAS:
            raise ValueError("Tema inválido")
        if not isinstance(resultado["tipo_actividad"], str) or not resultado["tipo_actividad"].strip():
            raise ValueError("El tipo de actividad debe ser texto no vacío")
        for campo in ("puntaje", "tiempo_segundos"):
            valor = resultado[campo]
            if isinstance(valor, bool) or not isinstance(valor, Real) or not math.isfinite(valor):
                raise ValueError(f"{campo} debe ser un número finito")
        if resultado["puntaje"] < 0:
            raise ValueError("El puntaje no puede ser negativo")
        if resultado["tiempo_segundos"] < 0:
            raise ValueError("El tiempo no puede ser negativo")
        if not isinstance(resultado["conceptos_con_error"], (list, tuple)) or any(
            not isinstance(concepto, str) for concepto in resultado["conceptos_con_error"]
        ):
            raise ValueError("conceptos_con_error debe ser una lista de textos")
        if not isinstance(resultado["aprobado"], bool):
            raise ValueError("aprobado debe ser booleano y venir del calificador")
        etapa = resultado.get("etapa")
        if etapa is not None and etapa not in (*ETAPAS, "diagnostico"):
            raise ValueError("Etapa de aprendizaje desconocida")
        estado = self.cargar()
        if any(i["id"] == str(resultado["id"]) for i in estado["intentos"]):
            return estado
        if etapa in ETAPAS:
            anterior = ETAPAS.index(etapa)
            aprobadas = etapas_aprobadas(estado, resultado["tema"])
            if any(paso not in aprobadas for paso in ETAPAS[:anterior]):
                raise ValueError("Primero aprueba las etapas anteriores del tema")
        intento = dict(resultado)
        intento["id"] = str(intento["id"])
        intento["conceptos_con_error"] = list(intento["conceptos_con_error"] or [])
        intento["fecha"] = intento.get("fecha") or datetime.now(timezone.utc).isoformat()
        estado["intentos"].append(intento)
        if etapa == "integradora" and intento["aprobado"] and all(
            paso in etapas_aprobadas(estado, intento["tema"]) for paso in ETAPAS
        ):
            estado["temas_acreditados"].setdefault(intento["tema"], {
                "origen": "ruta por niveles", "intento_id": intento["id"],
                "fecha": intento["fecha"], "legado": False,
            })
        estado["simulacion_activa"] = True
        estado["actualizado_en"] = datetime.now(timezone.utc).isoformat()
        return self.guardar(estado)

    def reiniciar(self):
        nuevo = estado_inicial()
        nuevo["actualizado_en"] = datetime.now(timezone.utc).isoformat()
        return self.guardar(nuevo)


def temas_acreditados(estado):
    return list(estado["temas_acreditados"])


def etapas_aprobadas(estado, tema):
    """Las acreditaciones heredadas no inventan etapas completadas."""
    return {intento["etapa"] for intento in estado.get("intentos", [])
            if intento.get("tema") == tema and intento.get("etapa") in ETAPAS
            and intento.get("aprobado") is True}


def siguiente_etapa(estado, tema):
    if tema in estado.get("temas_acreditados", {}):
        return None
    aprobadas = etapas_aprobadas(estado, tema)
    return next((etapa for etapa in ETAPAS if etapa not in aprobadas), None)
