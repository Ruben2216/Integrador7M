"""
retroalimentacion.py — Refuerzo por concepto y retroalimentación (Integrante 5).

Recibe el resultado verificado de un intento (salida de calificador.py o
calificador_mvc.py, o su versión normalizada para progreso.json) y devuelve
SIEMPRE el mismo formato:

    {
        "origen": "local" | "gemini",
        "motivo_respaldo": None | "por qué no se usó Gemini",
        "tema": "Bases de Datos PostgreSQL",
        "concepto": "JOIN",                    # concepto que conviene reforzar
        "concepto_nombre": "Uniones con JOIN",
        "fallos_por_concepto": {"JOIN": 2},
        "acierto": "...",                      # un criterio cumplido
        "mejora": "...",                       # un punto por mejorar
        "pista": "...",
        "recurso": {"id", "titulo", "fuente", "formato", "concepto", "enlace"},
    }

Plan B (local, sin internet): generar_retroalimentacion(resultado)
    1. Cuenta los criterios incumplidos de cada concepto.
    2. Refuerza el concepto con MÁS fallos. Empate: gana el que aparece primero
       en la rúbrica (orden fijo → resultado reproducible).
    3. Usa el texto del primer criterio incumplido de ese concepto (más
       específico); si no existe, el texto del concepto.
    4. Elige el recurso del catálogo etiquetado con ese concepto, priorizando
       el formato preferido del estudiante.

Plan A (Gemini Flash): solicitar_explicacion(resultado)
    Una sola solicitud por tema evaluado con los ejercicios, la rúbrica y los
    resultados verificados. Gemini solo redacta acierto/mejora/pista; el
    concepto y el recurso los decide el sistema (vienen del catálogo). Si
    Gemini no está configurado, falla, tarda más del tiempo de espera o
    responde incompleto, se devuelve el Plan B con el motivo.

Configuración (variables de entorno o archivo .env en la raíz del proyecto):
    GEMINI_API_KEY      clave de Google AI Studio (sin ella se usa el Plan B)
    GEMINI_MODELO       modelos separados por comas, en orden de preferencia
                        (por defecto gemini-3.5-flash,gemini-3.6-flash,gemini-flash-lite-latest)
    GEMINI_TIMEOUT      segundos de espera máximos en total (por defecto 20)
    GEMINI_DESACTIVADO  1 para forzar el Plan B aunque haya clave
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from recomendador import NODO_A_TEMA, TEMA_A_NODO

BASE = Path(__file__).resolve().parent
RUTA_RUBRICA = BASE / "rubrica_retroalimentacion.json"
RUTA_CATALOGO = BASE / "catalogo_recursos.json"
RUTA_GRAFO = BASE / "grafo_conocimiento.json"
RUTA_ENV = BASE / ".env"
BANCOS = {
    "Bases_de_Datos_PostgreSQL": BASE / "ejercicios_postgresql.json",
    "Patron_MVC_en_PHP": BASE / "ejercicios_mvc_php.json",
    "Logica_de_Programacion": BASE / "ejercicios_logica.json",
}

# Formato preferido del estudiante -> formatos del catálogo que le convienen.
FORMATO_A_CATALOGO = {
    "Visual": ("Video", "Tutorial"),
    "Texto": ("Lectura", "Referencia"),
    "Práctico": ("Práctica", "Practica"),
}

# Se prueban en orden: si uno está saturado (503) o no existe (404), se usa el siguiente.
MODELO_POR_DEFECTO = "gemini-3.5-flash,gemini-3.6-flash,gemini-flash-lite-latest"
TIMEOUT_POR_DEFECTO = 20.0
# Un modelo colgado no puede consumir más de esta fracción del tiempo total,
# para que quede tiempo de probar el siguiente.
FRACCION_POR_MODELO = 0.6
LONGITUD_MAXIMA_CAMPO = 700
URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"


# ─────────────────────────────────────────────────────────────────────────────
# Carga de datos
# ─────────────────────────────────────────────────────────────────────────────

def _leer_json(ruta: Path) -> Any:
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo)


@lru_cache(maxsize=1)
def _rubrica() -> dict:
    return _leer_json(RUTA_RUBRICA)["temas"]


def _catalogo() -> dict[str, dict]:
    return _leer_json(RUTA_CATALOGO)


def _grafo() -> dict:
    return _leer_json(RUTA_GRAFO)


def _banco(nodo: str) -> dict | None:
    ruta = BANCOS.get(nodo)
    return _leer_json(ruta) if ruta and ruta.exists() else None


# ─────────────────────────────────────────────────────────────────────────────
# Lectura del resultado (acepta la salida cruda del calificador o la normalizada)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _Intento:
    id: str
    nodo: str
    tipo: str
    aciertos: int | None
    total: int | None
    acreditado: bool
    detalle: list[dict]
    conceptos_con_error: list[str]
    criterios_cumplidos: list[str]
    respuestas: dict


def _nodo_de_tema(tema: Any) -> str:
    tema = str(tema or "")
    if tema in NODO_A_TEMA:
        return tema
    return TEMA_A_NODO.get(tema, tema)


def _leer_intento(resultado: dict) -> _Intento:
    if not isinstance(resultado, dict):
        raise ValueError("El resultado del intento debe ser un diccionario")

    if resultado.get("tipo") == "poo":
        nodo, tipo = "Programacion_Orientada_a_Objetos", "practica"
        aciertos, total = resultado.get("respondidos"), resultado.get("total")
    else:
        nodo = _nodo_de_tema(resultado.get("tema"))
        tipo = str(resultado.get("tipo") or resultado.get("tipo_actividad") or "").lower()
        tipo = ("laboratorio" if "laboratorio" in tipo
                else "seguimiento" if "seguimiento" in tipo else tipo or "actividad")
        aciertos = resultado.get("ejercicios_correctos", resultado.get("correctas"))
        total = resultado.get("total_ejercicios", resultado.get("total_preguntas"))
        if aciertos is None and isinstance(resultado.get("puntaje"), int):
            aciertos, total = resultado["puntaje"], resultado.get("puntaje_maximo")

    conceptos = resultado.get("conceptos_con_errores", resultado.get("conceptos_con_error")) or []
    cumplidos = resultado.get("criterios_cumplidos") or []
    return _Intento(
        id=str(resultado.get("intento", resultado.get("id", ""))),
        nodo=nodo,
        tipo=tipo,
        aciertos=aciertos if isinstance(aciertos, int) else None,
        total=total if isinstance(total, int) else None,
        acreditado=bool(resultado.get("acreditado", resultado.get("aprobado", False))),
        detalle=[d for d in (resultado.get("detalle") or []) if isinstance(d, dict)],
        conceptos_con_error=[str(c) for c in conceptos],
        criterios_cumplidos=list(cumplidos) if isinstance(cumplidos, (list, tuple)) else [],
        respuestas=resultado.get("respuestas") or {},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Plan B — retroalimentación local basada en la rúbrica
# ─────────────────────────────────────────────────────────────────────────────

def contar_fallos(intento: _Intento) -> Counter:
    """Fallos por concepto: criterios incumplidos (laboratorio) o preguntas falladas."""
    fallos: Counter = Counter()
    for item in intento.detalle:
        if item.get("correcto"):
            continue
        concepto = item.get("concepto")
        if concepto:
            fallos[concepto] += len(item.get("criterios_incumplidos") or []) or 1
    for concepto in intento.conceptos_con_error:  # por si no llegó el detalle
        if concepto not in fallos:
            fallos[concepto] += 1
    return fallos


def elegir_concepto(fallos: Counter, orden_rubrica: list[str]) -> str | None:
    """Más fallos primero; empate → orden de la rúbrica; después orden alfabético."""
    if not fallos:
        return None
    def clave(concepto: str):
        posicion = orden_rubrica.index(concepto) if concepto in orden_rubrica else len(orden_rubrica)
        return (-fallos[concepto], posicion, concepto)
    return sorted(fallos, key=clave)[0]


def _criterio_incumplido(intento: _Intento, concepto: str,
                         textos_criterios: dict) -> tuple[str | None, dict | None]:
    """
    Primer criterio incumplido del concepto con texto en la rúbrica. Se prefiere
    uno específico; los marcados "generico" (p. ej. «el resultado coincide»)
    solo se usan si no falló otro. Si el ejercicio no se pudo ejecutar (vacío o
    con error), se devuelve ese ejercicio para explicar el error.
    """
    genericos = []
    for item in intento.detalle:
        if item.get("concepto") != concepto or item.get("correcto"):
            continue
        if item.get("error"):
            return None, item
        for criterio in item.get("criterios_incumplidos") or []:
            if criterio not in textos_criterios:
                continue
            if textos_criterios[criterio].get("generico"):
                genericos.append(criterio)
            else:
                return criterio, None
    return (genericos[0] if genericos else None), None


def _elegir_acierto(intento: _Intento, rubrica_tema: dict, conceptos_rubrica: dict) -> str:
    conceptos_ok = [d.get("concepto") for d in intento.detalle if d.get("correcto")]
    conceptos_mal = {d.get("concepto") for d in intento.detalle if not d.get("correcto")}
    conceptos_mal |= set(intento.conceptos_con_error)
    for concepto in conceptos_rubrica:  # orden fijo de la rúbrica
        if concepto in conceptos_ok and concepto not in conceptos_mal:
            return conceptos_rubrica[concepto]["acierto"]
    for concepto in conceptos_ok:
        if concepto in conceptos_rubrica:
            return conceptos_rubrica[concepto]["acierto"]
    descripciones = _descripciones_criterios(intento.nodo)
    for criterio in intento.criterios_cumplidos:
        if criterio in descripciones:
            return f"Cumpliste este criterio: {descripciones[criterio]}."
    if intento.tipo == "practica" and intento.aciertos:
        return rubrica_tema.get("general", {}).get("acierto_total", "Entregaste la actividad.")
    return ("Completaste el intento y ya tienes un diagnóstico claro: "
            "ahora sabes exactamente qué concepto trabajar.")


@lru_cache(maxsize=8)
def _descripciones_criterios(nodo: str) -> dict[str, str]:
    banco = _banco(nodo)
    if not banco:
        return {}
    descripciones = {}
    for ejercicio in banco.get("laboratorio", []):
        for criterio in ejercicio.get("criterios", []):
            descripciones[criterio["id"]] = criterio["descripcion"].rstrip(".").lower()
    return descripciones


def elegir_recurso(nodo: str, concepto: str | None, formato_preferido: str | None = None,
                   recurso_rubrica: str | None = None) -> dict | None:
    """Recurso del catálogo para el concepto; prioriza el formato preferido."""
    catalogo = _catalogo()
    candidatos: list[str] = []
    if recurso_rubrica in catalogo:
        candidatos.append(recurso_rubrica)
    if concepto:
        candidatos += [rid for rid, r in catalogo.items()
                       if r.get("concepto") == concepto and rid not in candidatos]
    if not candidatos:  # respaldo: recursos del tema en el grafo
        candidatos = [rid for rid in _grafo().get(nodo, {}).get("recursos", []) if rid in catalogo]
    if not candidatos:
        return None
    preferidos = FORMATO_A_CATALOGO.get(formato_preferido or "", ())
    elegido = next((rid for rid in candidatos if catalogo[rid].get("formato") in preferidos),
                   candidatos[0])
    return {"id": elegido, **catalogo[elegido]}


def generar_retroalimentacion(resultado: dict, formato_preferido: str | None = None) -> dict:
    """Plan B: retroalimentación local, determinista y sin red."""
    intento = _leer_intento(resultado)
    rubrica_tema = _rubrica().get(intento.nodo, {"conceptos": {}, "criterios": {}, "general": {}})
    conceptos_rubrica: dict = rubrica_tema.get("conceptos", {})
    textos_criterios: dict = rubrica_tema.get("criterios", {})
    general: dict = rubrica_tema.get("general", {})

    fallos = contar_fallos(intento)
    concepto = elegir_concepto(fallos, list(conceptos_rubrica))
    texto_concepto = conceptos_rubrica.get(concepto, {}) if concepto else {}

    if concepto is None and intento.tipo != "practica":
        acierto = general.get("acierto_total", "Resolviste todo correctamente.")
        mejora = general.get("mejora_total", "No hay criterios pendientes en este intento.")
        pista = general.get("pista_avance", "Continúa con el siguiente tema de tu ruta.")
        recurso = elegir_recurso(intento.nodo, None, formato_preferido, general.get("recurso"))
    elif concepto is None:  # práctica abierta sin calificación automática
        acierto = _elegir_acierto(intento, rubrica_tema, conceptos_rubrica)
        mejora = general.get("mejora_total", "Revisa tus respuestas con la lista de revisión.")
        pista = general.get("pista_avance", "Contrasta cada respuesta con su criterio.")
        recurso = elegir_recurso(intento.nodo, None, formato_preferido, general.get("recurso"))
    else:
        criterio, item_con_error = _criterio_incumplido(intento, concepto, textos_criterios)
        especifico = textos_criterios.get(criterio, {}) if criterio else {}
        nombre = texto_concepto.get("nombre", concepto)
        acierto = _elegir_acierto(intento, rubrica_tema, conceptos_rubrica)
        mejora = especifico.get("mejora") or texto_concepto.get("mejora") or (
            f"Hay errores en el concepto {nombre}.")
        if item_con_error:
            error = str(item_con_error["error"]).rstrip(".")
            mejora = (f"El ejercicio {item_con_error.get('id')} no se pudo calificar ({error}). "
                      f"{mejora}")
        pista = especifico.get("pista") or texto_concepto.get("pista") or (
            f"Repasa {nombre} con el recurso sugerido y vuelve a intentarlo.")
        recurso = elegir_recurso(intento.nodo, concepto, formato_preferido,
                                 texto_concepto.get("recurso") or general.get("recurso"))

    return {
        "origen": "local",
        "motivo_respaldo": None,
        "intento": intento.id,
        "tema": NODO_A_TEMA.get(intento.nodo, intento.nodo),
        "concepto": concepto,
        "concepto_nombre": texto_concepto.get("nombre", concepto) if concepto else None,
        "fallos_por_concepto": dict(fallos),
        "acierto": acierto,
        "mejora": mejora,
        "pista": pista,
        "recurso": recurso,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Plan A — Gemini Flash con respaldo local
# ─────────────────────────────────────────────────────────────────────────────

class ErrorGemini(RuntimeError):
    """La llamada a Gemini no produjo una explicación utilizable."""

    def __init__(self, mensaje: str, reintentable: bool = True):
        super().__init__(mensaje)
        # False cuando probar otro modelo no ayudaría (p. ej. API key inválida).
        self.reintentable = reintentable


@dataclass
class ConfigGemini:
    api_key: str = ""
    modelo: str = MODELO_POR_DEFECTO  # uno o varios separados por comas, en orden
    timeout: float = TIMEOUT_POR_DEFECTO  # tiempo máximo TOTAL, sumando los modelos
    desactivado: bool = False

    @property
    def disponible(self) -> bool:
        return bool(self.api_key) and not self.desactivado

    @property
    def modelos(self) -> list[str]:
        return [m.strip() for m in self.modelo.split(",") if m.strip()] or [MODELO_POR_DEFECTO]


def _cargar_archivo_env(ruta: Path | None = None) -> None:
    """Lee CLAVE=valor de .env sin sobrescribir variables ya definidas."""
    ruta = ruta or RUTA_ENV
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip().removeprefix("export ").strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


def cargar_config() -> ConfigGemini:
    _cargar_archivo_env()
    try:
        timeout = float(os.environ.get("GEMINI_TIMEOUT", TIMEOUT_POR_DEFECTO))
    except ValueError:
        timeout = TIMEOUT_POR_DEFECTO
    return ConfigGemini(
        api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        modelo=os.environ.get("GEMINI_MODELO", "").strip() or MODELO_POR_DEFECTO,
        timeout=timeout if timeout > 0 else TIMEOUT_POR_DEFECTO,
        desactivado=os.environ.get("GEMINI_DESACTIVADO", "").strip().lower()
        in {"1", "true", "si", "sí", "yes"},
    )


def estado_gemini(config: ConfigGemini | None = None) -> str:
    config = config or cargar_config()
    if config.desactivado:
        return "Gemini desactivado (GEMINI_DESACTIVADO=1): se usa la retroalimentación local."
    if not config.api_key:
        return "Gemini no configurado (falta GEMINI_API_KEY): se usa la retroalimentación local."
    return (f"Gemini configurado · modelos {', '.join(config.modelos)} · "
            f"espera máxima {config.timeout:g} s.")


INSTRUCCIONES_SISTEMA = (
    "Eres un tutor de programación que da retroalimentación breve a un estudiante "
    "universitario hispanohablante. Te basas SOLO en los resultados verificados que "
    "recibes; no inventes errores ni aciertos. No escribas la solución completa ni "
    "código terminado: orienta. Habla de tú, con tono claro y motivador."
)


def construir_prompt(resultado: dict, local: dict) -> str:
    """Una solicitud por tema evaluado: ejercicios + rúbrica + resultados verificados."""
    intento = _leer_intento(resultado)
    banco = _banco(intento.nodo) or {}
    rubrica_tema = _rubrica().get(intento.nodo, {})
    textos_criterios = rubrica_tema.get("criterios", {})
    detalle = {d.get("id"): d for d in intento.detalle}

    if intento.tipo == "laboratorio":
        items = banco.get("laboratorio", [])
    elif intento.tipo == "seguimiento":
        variante = resultado.get("variante")
        items = banco.get("seguimiento", {}).get(variante, []) if variante else []
    else:
        items = []

    lineas = [
        f"Tema evaluado: {local['tema']} ({intento.tipo}).",
        f"Puntaje: {intento.aciertos}/{intento.total}. "
        f"Acreditado: {'sí' if intento.acreditado else 'no'}.",
        "",
        "Ejercicios con su rúbrica y resultado verificado por el calificador:",
    ]
    for item in items or intento.detalle:
        resultado_item = detalle.get(item.get("id"), item)
        estado = "CORRECTO" if resultado_item.get("correcto") else "INCORRECTO"
        lineas.append(f"- {item.get('id')} [{item.get('concepto')}, {item.get('dificultad', '-')}] "
                      f"{estado}: {item.get('enunciado', '')}")
        cumplidos = set(resultado_item.get("criterios_cumplidos") or [])
        for criterio in item.get("criterios", []):
            marca = "cumplido" if criterio["id"] in cumplidos else "NO cumplido"
            lineas.append(f"    · {criterio['id']} ({marca}): {criterio['descripcion']}")
            if intento.respuestas.get(criterio["id"]):
                lineas.append(f"      respuesta elegida: {str(intento.respuestas[criterio['id']])[:200]}")
        if resultado_item.get("error"):
            lineas.append(f"    · Error reportado: {resultado_item['error']}")
        respuesta = intento.respuestas.get(item.get("id"))
        if respuesta:
            lineas.append(f"    · Respuesta del estudiante: {str(respuesta)[:400]}")

    concepto = local.get("concepto")
    if concepto:
        conceptos = rubrica_tema.get("conceptos", {})
        lineas += [
            "",
            f"Concepto que el sistema decidió reforzar (más fallos): {concepto} — "
            f"{local.get('concepto_nombre')} · fallos por concepto: {local['fallos_por_concepto']}.",
            f"Rúbrica de ese concepto → mejora: {conceptos.get(concepto, {}).get('mejora', '-')} "
            f"| pista: {conceptos.get(concepto, {}).get('pista', '-')}",
        ]
        especificos = [f"{cid}: {t['pista']}" for cid, t in textos_criterios.items()
                       if cid in {c for d in intento.detalle for c in d.get("criterios_incumplidos") or []}]
        if especificos:
            lineas.append("Pistas de la rúbrica para los criterios incumplidos: " + " | ".join(especificos))
    else:
        lineas += ["", "No hay conceptos con error: felicita y sugiere cómo consolidar."]
    if local.get("recurso"):
        lineas.append(f"Recurso que se mostrará al estudiante: {local['recurso']['titulo']} "
                      f"({local['recurso']['formato']}).")
    lineas += [
        "",
        "Responde SOLO un objeto JSON con tres campos de texto en español:",
        '  "acierto": 1 oración sobre algo que el estudiante hizo bien según los criterios cumplidos;',
        '  "mejora": 1-2 oraciones sobre el concepto a reforzar, explicando el error observado;',
        '  "pista": 1-2 oraciones que orienten la corrección sin dar la respuesta completa.',
    ]
    return "\n".join(lineas)


def _cuerpo_solicitud(prompt: str) -> dict:
    return {
        "systemInstruction": {"parts": [{"text": INSTRUCCIONES_SISTEMA}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "acierto": {"type": "STRING"},
                    "mejora": {"type": "STRING"},
                    "pista": {"type": "STRING"},
                },
                "required": ["acierto", "mejora", "pista"],
            },
        },
    }


Transporte = Callable[[str, dict, dict, float], dict]


def _contexto_ssl() -> ssl.SSLContext:
    """
    Usa los certificados de certifi (viene con gradio/httpx). El Python de
    python.org en macOS no trae certificados configurados y sin esto toda
    llamada HTTPS falla con CERTIFICATE_VERIFY_FAILED.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _analizar_error_http(exc: urllib.error.HTTPError) -> tuple[str, bool]:
    """(mensaje claro, ¿conviene probar otro modelo?)."""
    try:
        detalle = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
    except Exception:
        detalle = ""
    if exc.code in (400, 401, 403) and "api key" in detalle.lower():
        # La misma clave fallaría con cualquier modelo: no se reintenta.
        return (f"la API key de Gemini no es válida ({exc.code}); revisa GEMINI_API_KEY en .env",
                False)
    mensajes = {
        400: "Gemini rechazó la solicitud (400)",
        401: "Gemini rechazó la autenticación (401)",
        403: "Gemini rechazó el acceso a este modelo (403)",
        404: "el modelo ya no existe (404); revisa GEMINI_MODELO",
        429: "se alcanzó el límite gratuito de Gemini (429); espera un minuto",
        503: "Gemini está saturado en este momento (503)",
    }
    return mensajes.get(exc.code, f"Gemini respondió con error HTTP {exc.code}"), True


def transporte_http(url: str, cabeceras: dict, cuerpo: dict, timeout: float) -> dict:
    """POST JSON con la biblioteca estándar (no requiere instalar nada extra)."""
    solicitud = urllib.request.Request(
        url, data=json.dumps(cuerpo).encode("utf-8"), headers=cabeceras, method="POST",
    )
    try:
        with urllib.request.urlopen(solicitud, timeout=timeout,
                                    context=_contexto_ssl()) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        mensaje, reintentable = _analizar_error_http(exc)
        raise ErrorGemini(mensaje, reintentable=reintentable) from exc
    except urllib.error.URLError as exc:
        raise ErrorGemini(f"no hay conexión con Gemini ({exc.reason})") from exc
    except TimeoutError as exc:
        raise ErrorGemini("Gemini superó el tiempo de espera") from exc
    except json.JSONDecodeError as exc:
        raise ErrorGemini("Gemini devolvió una respuesta que no es JSON") from exc


def _extraer_campos(respuesta: dict) -> dict[str, str]:
    try:
        candidato = respuesta["candidates"][0]
        texto = "".join(p.get("text", "") for p in candidato["content"]["parts"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        bloqueo = (respuesta or {}).get("promptFeedback", {}).get("blockReason")
        raise ErrorGemini(f"respuesta de Gemini sin contenido{f' ({bloqueo})' if bloqueo else ''}") from exc
    if candidato.get("finishReason") not in (None, "STOP"):
        raise ErrorGemini(f"respuesta de Gemini incompleta ({candidato.get('finishReason')})")
    if texto.startswith("```"):
        texto = texto.strip("`").removeprefix("json").strip()
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErrorGemini("respuesta de Gemini incompleta (JSON inválido)") from exc
    campos = {}
    for clave in ("acierto", "mejora", "pista"):
        valor = datos.get(clave) if isinstance(datos, dict) else None
        if not isinstance(valor, str) or not valor.strip():
            raise ErrorGemini(f"respuesta de Gemini incompleta (falta «{clave}»)")
        if len(valor) > LONGITUD_MAXIMA_CAMPO:
            raise ErrorGemini(f"respuesta de Gemini demasiado larga en «{clave}»")
        campos[clave] = valor.strip()
    return campos


_CACHE_GEMINI: dict[str, dict] = {}


def solicitar_explicacion(resultado: dict, formato_preferido: str | None = None, *,
                          config: ConfigGemini | None = None,
                          transporte: Transporte | None = None) -> dict:
    """Plan A con respaldo: nunca lanza excepción; siempre devuelve una retroalimentación."""
    local = generar_retroalimentacion(resultado, formato_preferido)
    config = config or cargar_config()
    if not config.disponible:
        return {**local, "motivo_respaldo": estado_gemini(config)}

    clave_cache = f"{local['intento']}|{config.modelo}|{formato_preferido}"
    if local["intento"] and clave_cache in _CACHE_GEMINI:
        return _CACHE_GEMINI[clave_cache]

    cabeceras = {"Content-Type": "application/json", "x-goog-api-key": config.api_key}
    cuerpo = _cuerpo_solicitud(construir_prompt(resultado, local))
    llamar = transporte or transporte_http

    # Los modelos se prueban en orden dentro de un mismo tiempo máximo total.
    limite = time.monotonic() + config.timeout
    motivos: list[str] = []
    campos = modelo_usado = None
    for modelo in config.modelos:
        restante = limite - time.monotonic()
        if restante <= 0.5:
            break
        espera = min(restante, config.timeout * FRACCION_POR_MODELO) \
            if len(config.modelos) > 1 else restante
        ejecutor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            futuro = ejecutor.submit(llamar, URL_GEMINI.format(modelo=modelo),
                                     cabeceras, cuerpo, espera)
            campos = _extraer_campos(futuro.result(timeout=espera))
            modelo_usado = modelo
            break
        except concurrent.futures.TimeoutError:
            motivos.append(f"{modelo}: Gemini tardó más de {round(espera, 1):g} s"
                           if len(config.modelos) > 1 else
                           f"Gemini tardó más de {config.timeout:g} s")
        except ErrorGemini as exc:
            motivos.append(f"{modelo}: {exc}" if len(config.modelos) > 1 else str(exc))
            if not exc.reintentable:
                break
        except Exception as exc:  # cualquier fallo inesperado pasa al siguiente modelo
            motivos.append(f"fallo inesperado al llamar a Gemini ({type(exc).__name__})")
        finally:
            ejecutor.shutdown(wait=False, cancel_futures=True)

    if campos is None:
        return {**local, "motivo_respaldo": "; ".join(motivos) or
                f"Gemini tardó más de {config.timeout:g} s"}

    explicacion = {**local, **campos, "origen": "gemini", "motivo_respaldo": None,
                   "modelo": modelo_usado}
    if local["intento"]:
        _CACHE_GEMINI[clave_cache] = explicacion
    return explicacion


# ─────────────────────────────────────────────────────────────────────────────
# Prueba manual: python retroalimentacion.py  [--gemini]
# ─────────────────────────────────────────────────────────────────────────────

def _intentos_ficticios_postgresql() -> tuple[dict, dict]:
    """Dos intentos reales de seguimiento con 3 de 5: uno falla JOIN y otro WHERE."""
    from calificador import calificar_seguimiento
    preguntas = _leer_json(BANCOS["Bases_de_Datos_PostgreSQL"])["seguimiento"]["variante_1"]

    def responder(fallar: str) -> dict:
        respuestas = {}
        for p in preguntas:
            incorrecta = next(o for o in p["opciones"] if o != p["respuesta_correcta"])
            respuestas[p["id"]] = incorrecta if p["concepto"] == fallar else p["respuesta_correcta"]
        return calificar_seguimiento(respuestas, 180.0, "variante_1")

    return responder("JOIN"), responder("WHERE")


def _imprimir(titulo: str, retro: dict) -> None:
    print(f"\n=== {titulo} ===")
    print(f"Origen: {retro['origen']}" + (f" (respaldo: {retro['motivo_respaldo']})"
                                          if retro.get("motivo_respaldo") else ""))
    print(f"Concepto a reforzar: {retro['concepto']}  fallos: {retro['fallos_por_concepto']}")
    print(f"Acierto: {retro['acierto']}\nMejora:  {retro['mejora']}\nPista:   {retro['pista']}")
    if retro.get("recurso"):
        print(f"Recurso: {retro['recurso']['titulo']} → {retro['recurso']['enlace']}")


if __name__ == "__main__":
    import sys

    con_join, con_where = _intentos_ficticios_postgresql()
    print(estado_gemini())
    for nombre, intento in (("3/5 con errores en JOIN", con_join),
                            ("3/5 con errores en WHERE", con_where)):
        _imprimir(f"Plan B · {nombre}", generar_retroalimentacion(intento))
        if "--gemini" in sys.argv:
            _imprimir(f"Plan A · {nombre}", solicitar_explicacion(intento))
