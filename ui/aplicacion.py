"""Montaje funcional de la interfaz y conexión con los módulos reales.

Responsabilidades de este módulo:
  · Leer el estado persistido y coordinar los calificadores reales.
  · Preparar bancos y variantes existentes.
  · Conectar componentes Gradio con callbacks.
La decisión de aprobación sigue en los calificadores; A* sigue en ``motor``.
"""
from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from typing import Any
from uuid import uuid4

import gradio as gr

from calificador import (
    calificar_laboratorio,
    calificar_seguimiento,
    obtener_ejercicios_laboratorio,
    obtener_variante_seguimiento,
)
from calificador_node import (
    calificar_laboratorio_node,
    calificar_seguimiento_node,
    obtener_ejercicios_laboratorio_node,
    obtener_variante_seguimiento_node,
)
from integracion_calificador import normalizar_resultado_calificador
from progreso import ErrorProgreso, temas_acreditados
from recomendador import FORMATOS, NIVELES, NODO_A_TEMA, TEMA_A_NODO
import simulacion
from ui import vistas

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUTA_CATALOGO = os.path.join(_DIR, "catalogo_recursos.json")
_RUTA_POO = os.path.join(_DIR, "ejercicios_poo.json")
_RUTA_PG = os.path.join(_DIR, "ejercicios_postgresql.json")


# ── Carga y estado ──────────────────────────────────────────────────────────
def _cargar_json(ruta: str) -> dict[str, Any]:
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def _cargar_catalogo() -> dict[str, dict[str, Any]]:
    return _cargar_json(_RUTA_CATALOGO)


def _estado_inicial(motor: Any) -> dict[str, Any]:
    """Lee el archivo local sin reemplazarlo si está corrupto."""
    error_progreso = None
    try:
        guardado = simulacion.almacen.cargar()
    except ErrorProgreso as exc:
        from progreso import estado_inicial as crear_estado_vacio

        guardado = crear_estado_vacio()
        error_progreso = str(exc)
    perfil_guardado = guardado.get("perfil", {})
    perfil = {
        "nivel": guardado["nivel"],
        "formato": guardado["formato_preferido"],
        "tema": guardado.get("tema_actual", motor.temas[0]),
        "tiempo": perfil_guardado.get("tiempo_interaccion_segundos", 120),
        "errores": perfil_guardado.get("tasa_errores", 50),
        "meta": guardado["meta"],
        "fallos": perfil_guardado.get("fallos", 0),
        "abandono": perfil_guardado.get("abandono", False),
    }
    completados = temas_acreditados(guardado)
    variantes = [i["variante"] for i in guardado["intentos"] if i.get("variante")]
    return {
        "perfil": perfil,
        "completados": completados,
        "recomendacion": motor.consultar(**perfil, completados=completados),
        "variantes_usadas": variantes,
        "simulacion_activa": guardado["simulacion_activa"],
        "intentos": guardado["intentos"],
        "error_progreso": error_progreso,
        "actividad": None,
        "resultado": None,
        "resultado_origen": None,
    }


def _actualizar_recomendacion(motor: Any, estado: dict[str, Any]) -> None:
    estado["recomendacion"] = motor.consultar(
        **estado["perfil"], completados=estado["completados"]
    )


def _persistir_perfil(perfil: dict[str, Any]) -> dict[str, Any]:
    """Guarda sólo preferencias; nunca convierte selecciones en acreditaciones."""
    store = simulacion.almacen
    guardado = store.cargar()
    if guardado["simulacion_activa"]:
        guardado.update(
            meta=perfil["meta"],
            formato_preferido=perfil["formato"],
            nivel=perfil["nivel"],
        )
    else:
        guardado = store.iniciar(perfil["meta"], perfil["formato"], perfil["nivel"])
    guardado["simulacion_activa"] = True
    guardado["tema_actual"] = perfil["tema"]
    guardado["perfil"].update({
        "tiempo_interaccion_segundos": perfil["tiempo"],
        "tasa_errores": perfil["errores"],
        "fallos": perfil["fallos"],
        "abandono": perfil["abandono"],
    })
    return store.guardar(guardado)


def _recargar(motor: Any) -> dict[str, Any]:
    estado = _estado_inicial(motor)
    _actualizar_recomendacion(motor, estado)
    return estado


# ── Consultas al grafo y al catálogo ────────────────────────────────────────
def _estado_del_tema(motor: Any, tema: str, completados: list[str]) -> tuple[str, list[str]]:
    nodo = TEMA_A_NODO[tema]
    if tema in completados:
        return "Acreditado", []
    faltantes = [
        NODO_A_TEMA[pre] for pre in motor.grafo[nodo]["prerrequisitos"]
        if NODO_A_TEMA[pre] not in completados
    ]
    return ("Bloqueado", faltantes) if faltantes else ("Disponible", [])


def _estados_temas(motor: Any, completados: list[str]) -> dict[str, tuple[str, list[str]]]:
    return {tema: _estado_del_tema(motor, tema, completados) for tema in motor.temas}


def _temas_pertinentes(motor: Any, meta: str) -> list[str]:
    """Ancestros de la meta (incluida ella) en el grafo, en orden legible."""
    nodo_meta = TEMA_A_NODO[meta]
    relevantes: set[str] = set()
    pendientes = [nodo_meta]
    while pendientes:
        nodo = pendientes.pop()
        if nodo in relevantes:
            continue
        relevantes.add(nodo)
        pendientes.extend(motor.grafo[nodo]["prerrequisitos"])
    return [tema for tema in motor.temas if TEMA_A_NODO[tema] in relevantes]


def _recursos(motor: Any, catalogo: dict[str, dict[str, Any]], tema: str) -> str:
    nodo = TEMA_A_NODO[tema]
    return vistas.recursos_html(catalogo, motor.grafo[nodo]["recursos"])


# ── Información de actividades conectadas ──────────────────────────────────
def _info_actividad(tema: str) -> dict[str, str | None]:
    mapa = {
        "Programación Orientada a Objetos": {
            "clave": "poo",
            "etiqueta": "Práctica de POO · 4 retos · Revisión",
            "detalle": "Práctica abierta: se entrega para revisión; no acredita automáticamente.",
        },
        "Bases de Datos PostgreSQL": {
            "clave": "pg_lab",
            "etiqueta": "Laboratorio (4 ejercicios) o seguimiento (5 preguntas)",
            "detalle": "Calificación automática con el calificador real de PostgreSQL.",
        },
        "Backend con Node.js": {
            "clave": "node_lab",
            "etiqueta": "Laboratorio (5 puntos) o seguimiento (5 preguntas)",
            "detalle": "Calificación automática con el calificador real de Node.js.",
        },
        "Lógica de Programación": {
            "clave": "logica_lab",
            "etiqueta": "Laboratorio (4 ejercicios) o seguimiento (5 preguntas)",
            "detalle": "Calificación automática con el calificador real de Lógica de Programación.",
        },
        "Patrón MVC en PHP": {
            "clave": "mvc_lab",
            "etiqueta": "Laboratorio (4 ejercicios) o seguimiento (5 preguntas)",
            "detalle": "Calificación automática con el calificador real de MVC.",
        },
    }
    return mapa.get(tema, {"clave": None, "etiqueta": "Evaluación no disponible", "detalle": "Sin actividad conectada."})


def _descripciones_criterios(ejercicios_pg: list[dict], banco_pg: dict, ejercicios_node: list[dict]) -> dict[str, str]:
    descripciones: dict[str, str] = {}
    for ejercicio in ejercicios_pg:
        for criterio in ejercicio.get("criterios", []):
            descripciones[criterio["id"]] = criterio["descripcion"]
    node_lab = {
        "N01-HTTP-GET": "Usa GET para consultar el estado del servicio.",
        "N01-HTTP-200": "Responde 200 cuando el servicio está disponible.",
        "N02-ROUTE-PARAM": "Define /libros/:id y lee el identificador desde req.params.id.",
        "N03-VALIDATE-BEFORE-SAVE": "Valida el nombre obligatorio antes de persistir.",
        "N03-HTTP-ERROR": "Responde 400 o 422 con un error descriptivo.",
        "N04-POST-CREATE-201": "POST /productos crea el registro y responde 201.",
        "N04-GET-LIST-200": "GET /productos lista los registros y responde 200.",
    }
    descripciones.update(node_lab)
    for variante, preguntas in banco_pg.get("seguimiento", {}).items():
        for pregunta in preguntas:
            descripciones[pregunta["id"]] = f"{pregunta['concepto']}: {pregunta['enunciado']}"
            descripciones[pregunta["id"]] = f"Concepto evaluado: {pregunta['concepto']}"
    for ejercicio in ejercicios_node:
        for criterio in ejercicio.get("rubrica", {}).get("criterios", []):
            descripciones.setdefault(criterio, criterio)
    return descripciones


# ── Grafo ───────────────────────────────────────────────────────────────────
def _dibujar_grafo(motor: Any, completados: list[str], seleccionado: str | None):
    import matplotlib.pyplot as plt
    import networkx as nx
    from matplotlib.patches import Patch

    grafo = nx.DiGraph()
    grafo.add_nodes_from(motor.grafo)
    grafo.add_edges_from(motor._rec.aristas)
    for capa, generacion in enumerate(nx.topological_generations(grafo)):
        for nodo in generacion:
            grafo.nodes[nodo]["capa"] = capa
    posicion = nx.multipartite_layout(grafo, subset_key="capa")
    colores, bordes = [], []
    for nodo in grafo.nodes:
        tema = NODO_A_TEMA[nodo]
        estado, _ = _estado_del_tema(motor, tema, completados)
        colores.append(
            "#4ADE80" if estado == "Acreditado"
            else "#7DD3FC" if estado == "Disponible"
            else "#64748B"
        )
        bordes.append("#5EEAD4" if nodo == TEMA_A_NODO.get(seleccionado) else "#2B3A50")
    fig, ax = plt.subplots(figsize=(7.4, 4.4), dpi=110)
    fig.patch.set_facecolor("#131E30")
    ax.set_facecolor("#131E30")
    nx.draw_networkx_edges(
        grafo, posicion, ax=ax, arrows=True, arrowsize=17,
        edge_color="#5D7088", width=1.4, node_size=4300,
    )
    nx.draw_networkx_nodes(
        grafo, posicion, ax=ax, node_color=colores, edgecolors=bordes,
        linewidths=2.4, node_size=4300,
    )
    etiquetas = {nodo: NODO_A_TEMA[nodo].replace(" ", "\n", 2) for nodo in grafo.nodes}
    nx.draw_networkx_labels(
        grafo, posicion, labels=etiquetas, ax=ax, font_size=7.5,
        font_color="#08111F", font_weight="bold",
    )
    ax.legend(
        handles=[
            Patch(color="#4ADE80", label="Acreditado"),
            Patch(color="#7DD3FC", label="Disponible"),
            Patch(color="#64748B", label="Bloqueado"),
        ],
        loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.14),
        labelcolor="#B8C5D6",
    )
    ax.set_title("Grafo de conocimiento · borde turquesa: tema seleccionado", color="#B8C5D6", fontsize=9)
    ax.set_axis_off()
    fig.tight_layout()
    return fig


# ── Montaje ─────────────────────────────────────────────────────────────────
def construir_interfaz(motor: Any) -> gr.Blocks:
    catalogo = _cargar_catalogo()
    banco_poo = _cargar_json(_RUTA_POO)
    banco_pg = _cargar_json(_RUTA_PG)
    ejercicios_pg = obtener_ejercicios_laboratorio()
    ejercicios_node = obtener_ejercicios_laboratorio_node()
    descripciones = _descripciones_criterios(ejercicios_pg, banco_pg, ejercicios_node)
    inicial = _estado_inicial(motor)

    actividades: dict[str, dict[str, Any]] = {
        "poo": {
            "tema": "Programación Orientada a Objetos",
            "tipo": "poo",
            "modo": "poo",
            "titulo": "Práctica de POO · 4 retos",
            "cantidad": len(banco_poo["ejercicios"]),
            "etiqueta": "Programación Orientada a Objetos · Práctica · 4 retos · Revisión docente",
        },
        "pg_lab": {
            "tema": "Bases de Datos PostgreSQL",
            "tipo": "laboratorio",
            "modo": "sql",
            "titulo": "Laboratorio PostgreSQL · 4 ejercicios",
            "cantidad": len(ejercicios_pg),
            "etiqueta": "Bases de Datos PostgreSQL · Laboratorio · 4 ejercicios · Calificación automática",
        },
        "pg_seg": {
            "tema": "Bases de Datos PostgreSQL",
            "tipo": "seguimiento",
            "modo": "choice",
            "titulo": "Seguimiento PostgreSQL · 5 preguntas",
            "cantidad": 5,
            "etiqueta": "Bases de Datos PostgreSQL · Seguimiento · 5 preguntas · Calificación automática",
        },
        "node_lab": {
            "tema": "Backend con Node.js",
            "tipo": "laboratorio",
            "modo": "texto",
            "titulo": "Laboratorio Node.js · 4 ejercicios / 5 puntos",
            "cantidad": len(ejercicios_node),
            "etiqueta": "Backend con Node.js · Laboratorio · 4 ejercicios / 5 puntos · Calificación automática",
        },
        "node_seg": {
            "tema": "Backend con Node.js",
            "tipo": "seguimiento",
            "modo": "node_choice",
            "titulo": "Seguimiento Node.js · 5 preguntas",
            "cantidad": 5,
            "etiqueta": "Backend con Node.js · Seguimiento · 5 preguntas · Calificación automática",
        },
    }
    opciones_catalogo = [(info["etiqueta"], clave) for clave, info in actividades.items()]

    # ── Helpers de presentación ────────────────────────────────────────────
    def metricas(actual: dict[str, Any]) -> dict[str, Any]:
        rec = actual["recomendacion"]
        meta = actual["perfil"]["meta"]
        relevantes = _temas_pertinentes(motor, meta)
        hechos = [t for t in relevantes if t in actual["completados"]]
        siguiente = rec.get("siguiente_tema")
        info_siguiente = _info_actividad(siguiente) if siguiente else None
        return {
            "meta": meta,
            "relevantes": relevantes,
            "acreditados_meta": hechos,
            "total_meta": len(relevantes),
            "siguiente": siguiente,
            "estado_meta": rec.get("estado_meta", "En progreso"),
            "info_siguiente": info_siguiente,
            "estados": _estados_temas(motor, actual["completados"]),
        }

    def home_render(actual: dict[str, Any]):
        m = metricas(actual)
        actividad = m["info_siguiente"]["etiqueta"] if m["info_siguiente"] else None
        html = vistas.inicio_html(
            simulacion_activa=actual["simulacion_activa"],
            error_progreso=actual.get("error_progreso"),
            meta=m["meta"],
            acreditados_meta=m["acreditados_meta"],
            total_meta=m["total_meta"],
            completados_todos=actual["completados"],
            siguiente=m["siguiente"],
            estado_meta=m["estado_meta"],
            actividad_siguiente=actividad,
            intentos=len(actual["intentos"]),
        )
        boton = gr.update(
            value="Continuar aprendizaje" if actual["simulacion_activa"] else "Iniciar simulación"
        )
        elegir = gr.update(
            visible=actual["simulacion_activa"] and m["estado_meta"] == "Meta completada"
        )
        return html, boton, elegir

    def perfil_updates(perfil: dict[str, Any]):
        return [
            gr.update(value=perfil["nivel"]),
            gr.update(value=perfil["formato"]),
            gr.update(value=perfil["tema"]),
            gr.update(value=perfil["tiempo"]),
            gr.update(value=perfil["errores"]),
            gr.update(value=perfil["meta"]),
            gr.update(value=perfil["fallos"]),
            gr.update(value=perfil["abandono"]),
        ]

    def render_meta_detalle(meta: str, actual: dict[str, Any]) -> str:
        nodo = TEMA_A_NODO[meta]
        prerequisitos = [NODO_A_TEMA[n] for n in motor.grafo[nodo]["prerrequisitos"]]
        pendientes = [t for t in prerequisitos if t not in actual["completados"]]
        return vistas.meta_detalle_html(
            meta, prerequisitos, pendientes, _recursos(motor, catalogo, meta)
        )

    def disponibilidad(tema: str, actual: dict[str, Any]) -> str:
        estado, faltantes = _estado_del_tema(motor, tema, actual["completados"])
        info = _info_actividad(tema)
        return vistas.disponibilidad_html(
            tema, estado, faltantes, info["etiqueta"] or "", info["detalle"] or ""
        )

    def detalle_ui(actual: dict[str, Any], tema: str) -> str:
        estado, faltantes = _estado_del_tema(motor, tema, actual["completados"])
        nodo = TEMA_A_NODO[tema]
        prerequisitos = [NODO_A_TEMA[n] for n in motor.grafo[nodo]["prerrequisitos"]]
        info = _info_actividad(tema)
        siguiente = actual["recomendacion"].get("siguiente_tema")
        return vistas.tema_detalle_html(
            tema, estado, prerequisitos, faltantes,
            _recursos(motor, catalogo, tema),
            info["etiqueta"] or "", info["detalle"] or "",
            es_siguiente=tema == siguiente,
        )

    def ruta_render(actual: dict[str, Any], seleccionado: str | None = None):
        m = metricas(actual)
        rec = actual["recomendacion"]
        next_theme = m["siguiente"]
        estados = m["estados"]
        cabecera = vistas.ruta_cabecera_html(
            m["meta"], len(m["acreditados_meta"]), m["total_meta"],
            m["estado_meta"], actual["completados"],
        )
        if next_theme:
            estado_next, faltantes_next = estados[next_theme]
            info_next = _info_actividad(next_theme)
            explicacion = (
                "El motor A* lo coloca como el primer paso disponible para tu meta."
                if estado_next != "Bloqueado"
                else "La ruta lo señala, pero todavía tiene prerrequisitos pendientes."
            )
            siguiente = vistas.siguiente_paso_html(
                next_theme, explicacion, info_next["etiqueta"],
                _recursos(motor, catalogo, next_theme),
                faltantes_next if estado_next == "Bloqueado" else (),
            )
        else:
            siguiente = vistas.siguiente_paso_html(None, "", None, "")
        lista = vistas.lista_pasos_html(
            motor.temas, estados, next_theme, rec.get("ruta_pendiente", [])
        )
        if seleccionado in motor.temas:
            tema_sel = seleccionado
        elif next_theme in motor.temas:
            tema_sel = next_theme
        elif m["meta"] in motor.temas:
            tema_sel = m["meta"]
        else:
            tema_sel = motor.temas[0]
        detalle = detalle_ui(actual, tema_sel)
        figura = _dibujar_grafo(motor, actual["completados"], tema_sel)
        return cabecera, siguiente, lista, figura, detalle, gr.update(value=tema_sel), ""

    def diag_render(paso: int, tema_valor: str, actual: dict[str, Any]):
        paso = max(1, min(3, int(paso)))
        titulos = {
            1: "¿Qué quieres aprender?",
            2: "¿Cómo prefieres estudiar?",
            3: "¿Qué conocimientos quieres evaluar?",
        }
        encabezado = f"<span class='step-label'>Paso {paso} de 3</span><h2>{titulos[paso]}</h2>"
        return (
            paso,
            gr.update(visible=paso == 1),
            gr.update(visible=paso == 2),
            gr.update(visible=paso == 3),
            encabezado,
            gr.update(visible=paso > 1),
            gr.update(visible=paso < 3),
            vistas.acreditaciones_html(actual["completados"]),
            disponibilidad(tema_valor, actual),
        )

    def opciones_node(pregunta: dict[str, Any]) -> list[str]:
        correcta = str(pregunta.get("respuesta", ""))
        distractores = {
            "GET": ["POST", "PUT", "DELETE"],
            "200": ["201", "400", "404"],
            "201": ["200", "400", "404"],
            "req.params.id": ["req.body.id", "req.query.id", "req.headers.id"],
            "req.params": ["req.body", "req.query", "req.headers"],
            "Sí": ["No"],
            "No": ["Sí"],
            "POST": ["GET", "PUT", "DELETE"],
        }
        opciones = [correcta] + [o for o in distractores.get(correcta, ["Opción A", "Opción B", "Opción C"]) if o != correcta]
        return list(dict.fromkeys(opciones))

    def crear_actividad(
        clave: str,
        actual: dict[str, Any],
        origen: str = "actividad",
        permitir_bloqueado: bool = False,
    ) -> tuple[dict[str, Any], str, bool]:
        info = actividades.get(clave)
        if not info:
            return actual, "Selecciona una actividad disponible.", False
        estado, faltantes = _estado_del_tema(motor, info["tema"], actual["completados"])
        if estado == "Bloqueado" and not permitir_bloqueado:
            return actual, (
                f"{info['tema']} está bloqueado. Primero acredita: "
                + ", ".join(faltantes) + "."
            ), False
        usados = list(actual.get("variantes_usadas", []))
        actual_act = actual.get("actividad")
        if actual_act and actual_act.get("variante") and not actual_act.get("enviado"):
            usados.append(actual_act["variante"])
        nuevo = deepcopy(actual)
        variante = None
        if clave == "poo":
            items = deepcopy(banco_poo["ejercicios"])
            for item in items:
                item["enunciado"] = item.get("enunciado", "")
                item["titulo"] = item.get("titulo", item.get("id"))
        elif clave == "pg_lab":
            items = deepcopy(ejercicios_pg)
        elif clave == "pg_seg":
            try:
                variante, preguntas = obtener_variante_seguimiento(usados)
            except ValueError as exc:
                return actual, f"No se puede iniciar el seguimiento: {exc}", False
            items = deepcopy(preguntas)
        elif clave == "node_lab":
            items = deepcopy(ejercicios_node)
        elif clave == "node_seg":
            try:
                variante, preguntas = obtener_variante_seguimiento_node(usados)
            except ValueError as exc:
                return actual, f"No se puede iniciar el seguimiento: {exc}", False
            items = []
            for pregunta in preguntas:
                copia = deepcopy(pregunta)
                copia["enunciado"] = copia.get("pregunta", "")
                copia["opciones"] = opciones_node(copia)
                items.append(copia)
        else:
            return actual, "Actividad no reconocida.", False
        nuevo["actividad"] = {
            **info,
            "clave": clave,
            "items": items,
            "indice": 0,
            "respuestas": {},
            "variante": variante,
            "inicio": time.monotonic(),
            "intento_id": str(uuid4()),
            "origen": origen,
            "revisando": False,
            "enviado": False,
        }
        return nuevo, "", True

    def guardar_respuesta(act: dict[str, Any], codigo, opcion, texto) -> None:
        item = act["items"][act["indice"]]
        if act["modo"] == "sql":
            valor = codigo
        elif act["modo"] in ("choice", "node_choice"):
            valor = opcion
        else:
            valor = texto
        act["respuestas"][item["id"]] = "" if valor is None else str(valor)

    def render_actividad(actual: dict[str, Any]):
        act = actual.get("actividad")
        if not act:
            return (
                gr.update(visible=False), "", "", gr.update(visible=False), "", "",
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), "",
            )
        item = act["items"][act["indice"]]
        total = len(act["items"])
        es_ultimo = act["indice"] == total - 1
        enviado = bool(act.get("enviado"))
        revisando = bool(act.get("revisando")) and not enviado
        respuesta = act["respuestas"].get(item["id"], "")
        encabezado = vistas.actividad_encabezado_html(act, item) + vistas.actividad_pregunta_html(act, item)
        referencia = vistas.actividad_referencia_html(act, item)
        lab_visible = act["modo"] == "sql"
        lab_html = vistas.lab_datos_html(item) if lab_visible else ""
        detalles = vistas.detalles_intento_html(act, item)
        sql_update = gr.update(
            visible=lab_visible, value=respuesta if lab_visible else "",
            interactive=not enviado, label="Tu consulta SQL",
        )
        radio_visible = act["modo"] in ("choice", "node_choice")
        radio_update = gr.update(
            visible=radio_visible,
            choices=item.get("opciones", []) if radio_visible else [],
            value=(respuesta or None) if radio_visible else None,
            interactive=not enviado,
            label="Selecciona una respuesta",
        )
        texto_visible = act["modo"] in ("texto", "poo")
        texto_update = gr.update(
            visible=texto_visible,
            value=respuesta if texto_visible else "",
            interactive=not enviado,
            label="Tu propuesta de solución" if act["modo"] == "poo" else "Tu respuesta",
        )
        if act["tipo"] == "seguimiento":
            etiqueta_envio = "Calificar seguimiento"
        elif act["tipo"] == "poo":
            etiqueta_envio = "Entregar práctica POO"
        else:
            etiqueta_envio = "Calificar laboratorio"
        pendientes = sum(
            not str(act["respuestas"].get(x["id"], "")).strip() for x in act["items"]
        )
        revision = vistas.revision_html(act, pendientes) if revisando else ""
        return (
            gr.update(visible=True),
            encabezado,
            referencia,
            gr.update(visible=lab_visible),
            lab_html,
            detalles,
            sql_update,
            radio_update,
            texto_update,
            gr.update(visible=act["indice"] > 0 and not enviado),
            gr.update(visible=not es_ultimo and not enviado),
            gr.update(visible=es_ultimo and not revisando and not enviado, value="Revisar y enviar"),
            gr.update(visible=revisando, value=etiqueta_envio, interactive=True),
            revision,
        )

    def act_full(
        actual: dict[str, Any],
        nav_update=None,
        selector_update=None,
        mensaje: str = "",
        tipo_mensaje: str = "info",
        ruta_update=None,
    ):
        # ``nav_update`` se conserva por compatibilidad de las llamadas, pero
        # la pestaña se cambia con el evento JS encadenado (ver ``js_tab``).
        selector_update = selector_update if selector_update is not None else gr.update()
        ruta_update = ruta_update if ruta_update is not None else gr.update()
        clases = {"info": "", "warn": "warn", "bad": "bad", "good": "good"}
        status = (
            f'<div class="callout {clases.get(tipo_mensaje, "")}">{mensaje}</div>'
            if mensaje else ""
        )
        return (actual, selector_update, *render_actividad(actual), status, ruta_update)

    def render_resultado(resultado: dict[str, Any], actual: dict[str, Any]):
        tema = NODO_A_TEMA.get(resultado.get("tema"), resultado.get("tema", "Tema"))
        resultado["tema"] = tema
        rec = actual["recomendacion"]
        estados = _estados_temas(motor, actual["completados"])
        siguiente = rec.get("siguiente_tema")
        dependientes = [
            t for t, (est, falt) in estados.items()
            if est == "Bloqueado" and tema in falt
        ]
        info_siguiente = _info_actividad(siguiente) if siguiente else None
        principal = vistas.resultado_principal_html(
            resultado, descripciones, resultado.get("_titulo", "")
        )
        efecto = vistas.resultado_efecto_html(
            estado_meta=rec.get("estado_meta", "En progreso"),
            aprobado=bool(resultado.get("acreditado")),
            tema=tema,
            siguiente=siguiente,
            bloqueados_dependientes=dependientes,
            completados=actual["completados"],
            actividad_siguiente=info_siguiente["etiqueta"] if info_siguiente else None,
        )
        revision = vistas.resultado_revision_html(resultado, descripciones)
        retro = vistas.resultado_retro_html(resultado)
        recursos = _recursos(motor, catalogo, tema) if tema in motor.temas else ""
        recurso = vistas.recurso_repaso_html(recursos)
        reintentar_update = gr.update(visible=bool(actual.get("actividad")))
        continuar_update = gr.update(
            visible=bool(siguiente),
            value=f"Continuar con {siguiente}" if siguiente else "Continuar con el siguiente tema",
        )
        elegir_update = gr.update(visible=rec.get("estado_meta") == "Meta completada")
        return principal, efecto, revision, retro, recurso, reintentar_update, continuar_update, elegir_update


    # ── Componentes ────────────────────────────────────────────────────────
    home_inicial, _, home_meta_visible = home_render(inicial)
    diag_inicial = diag_render(1, inicial["perfil"]["tema"], inicial)
    ruta_inicial = ruta_render(inicial)
    estados_iniciales = metricas(inicial)["estados"]
    etiquetas_actividad = {t: _info_actividad(t)["etiqueta"] or "" for t in motor.temas}
    texto_iniciar = "Continuar aprendizaje" if inicial["simulacion_activa"] else "Iniciar simulación"

    with gr.Blocks(title="Rutas de aprendizaje") as demo:
        estado = gr.State(inicial)
        paso_diagnostico = gr.State(1)

        gr.HTML(
            """
            <header id="app-header">
              <div class="brand">
                <div class="brand-mark" aria-hidden="true">R</div>
                <div>
                  <h1>Rutas de aprendizaje</h1>
                  <p class="tagline">Un recorrido claro: diagnóstico, práctica y ruta que se adapta.</p>
                </div>
              </div>
            </header>
            """,
            container=False,
        )

        with gr.Tabs(selected="inicio", elem_id="main-nav", overflow_behavior="wrap") as navegacion:
            # ── Inicio ─────────────────────────────────────────────────────
            with gr.Tab("Inicio", id="inicio"):
                inicio_resumen = gr.HTML(home_inicial, elem_id="inicio-resumen")
                with gr.Row(elem_classes=["button-row"]):
                    iniciar = gr.Button(texto_iniciar, variant="primary")
                    home_cambiar_meta = gr.Button(
                        "Elegir otra meta", visible=home_meta_visible.get("visible", False)
                    )
                    reiniciar = gr.Button(
                        "Reiniciar simulación", variant="secondary", elem_classes=["danger-outline"]
                    )
                with gr.Group(visible=False, elem_classes=["danger-zone"]) as confirmar_reinicio:
                    gr.HTML(
                        "<h3>¿Reiniciar la simulación?</h3>"
                        "<p>Se borrarán la meta activa, las acreditaciones y el historial "
                        "de intentos de esta simulación local. El archivo de progreso se "
                        "reemplazará por un estado inicial. Esta acción no se puede deshacer.</p>"
                    )
                    with gr.Row(elem_classes=["button-row"]):
                        cancelar_reinicio = gr.Button("Cancelar")
                        confirmar = gr.Button("Reiniciar", variant="stop")

            # ── Diagnóstico ────────────────────────────────────────────────
            with gr.Tab("Diagnóstico", id="diagnostico"):
                diag_encabezado = gr.HTML(diag_inicial[4])
                with gr.Group(visible=True, elem_classes=["card"]) as diag_paso_1:
                    gr.HTML(
                        "<span class='eyebrow'>Paso 1</span><h3>Elige tu meta</h3>"
                        "<p class='small muted'>La meta define los temas pertinentes y el "
                        "progreso que verás en Inicio y Mi ruta.</p>"
                    )
                    meta = gr.Dropdown(
                        motor.temas, value=inicial["perfil"]["meta"],
                        label="Meta de aprendizaje", elem_id="meta-select",
                    )
                    meta_detalle = gr.HTML(render_meta_detalle(inicial["perfil"]["meta"], inicial))
                with gr.Group(visible=False, elem_classes=["card"]) as diag_paso_2:
                    gr.HTML(
                        "<span class='eyebrow'>Paso 2</span><h3>Preferencias de estudio</h3>"
                        "<p class='small muted'>El motor usa estas preferencias para ordenar "
                        "recursos y contextualizar la recomendación.</p>"
                    )
                    with gr.Row():
                        nivel = gr.Radio(
                            NIVELES, value=inicial["perfil"]["nivel"], label="Nivel previo"
                        )
                        formato = gr.Radio(
                            FORMATOS, value=inicial["perfil"]["formato"], label="Formato preferido"
                        )
                    with gr.Accordion("Parámetros de simulación", open=False):
                        gr.HTML(
                            "<p class='small muted'>Estos valores describen el contexto "
                            "simulado del estudiante. No son datos obtenidos al calificar "
                            "una actividad real; esos llegan del calificador y del intento.</p>"
                        )
                        tema_actual = gr.Dropdown(
                            motor.temas, value=inicial["perfil"]["tema"],
                            label="Tema actual",
                        )
                        with gr.Row():
                            tiempo = gr.Slider(
                                5, 300, value=inicial["perfil"]["tiempo"], step=1,
                                label="Tiempo de interacción (s)",
                            )
                            errores = gr.Slider(
                                0, 100, value=inicial["perfil"]["errores"], step=1,
                                label="Tasa de errores (%)",
                            )
                        with gr.Row():
                            fallos = gr.Slider(
                                0, 6, value=inicial["perfil"]["fallos"], step=1,
                                label="Fallos consecutivos",
                            )
                            abandono = gr.Checkbox(
                                value=inicial["perfil"]["abandono"],
                                label="Abandonó la actividad",
                            )
                with gr.Group(visible=False, elem_classes=["card"]) as diag_paso_3:
                    gr.HTML(
                        "<span class='eyebrow'>Paso 3</span>"
                        "<h3>Qué conocimientos quieres evaluar</h3>"
                        "<p class='small muted'>Sólo un resultado calificado y aprobado "
                        "crea una acreditación nueva. Elegir un tema aquí no acredita.</p>"
                    )
                    acreditaciones_diag = gr.HTML(diag_inicial[7])
                    tema_evaluar = gr.Dropdown(
                        motor.temas, value=inicial["perfil"]["tema"],
                        label="Tema que quieres evaluar",
                    )
                    disponibilidad_diag = gr.HTML(diag_inicial[8])
                    with gr.Row(elem_classes=["button-row"]):
                        evaluar_tema = gr.Button("Evaluar este tema", variant="secondary")
                        generar_ruta = gr.Button(
                            "Generar / actualizar mi ruta", variant="primary"
                        )
                with gr.Row(elem_classes=["button-row"]):
                    diag_anterior = gr.Button("Anterior", visible=False)
                    diag_siguiente = gr.Button("Siguiente", variant="primary")
                aviso_diag = gr.HTML(elem_id="diag-aviso")

            # ── Mi ruta ────────────────────────────────────────────────────
            with gr.Tab("Mi ruta", id="ruta"):
                ruta_cabecera = gr.HTML(ruta_inicial[0])
                siguiente_paso = gr.HTML(ruta_inicial[1])
                with gr.Row(elem_classes=["button-row"]):
                    abrir_siguiente = gr.Button("Iniciar actividad", variant="primary")
                    actualizar_ruta = gr.Button("Actualizar ruta")
                    cambiar_meta = gr.Button("Cambiar meta")
                with gr.Row(elem_classes=["route-layout"]):
                    with gr.Column(elem_classes=["route-main"]):
                        lista_pasos = gr.HTML(ruta_inicial[2])
                    with gr.Column(elem_classes=["route-side"]):
                        grafo = gr.Plot(value=ruta_inicial[3], label="Grafo de conocimiento")
                        tema_grafo = gr.Dropdown(
                            motor.temas, value=inicial["perfil"]["tema"],
                            label="Explorar un tema del grafo",
                        )
                        tema_detalle = gr.HTML(ruta_inicial[4])
                        ir_prerrequisito = gr.Button("Ir al prerrequisito")
                ruta_aviso = gr.HTML()

            # ── Actividad ──────────────────────────────────────────────────
            with gr.Tab("Actividad", id="actividad"):
                gr.HTML(
                    "<span class='eyebrow'>Catálogo de actividades</span>"
                    "<h2>Elige qué quieres practicar</h2>"
                    "<p class='muted reading'>Cada tarjeta indica el tema, el tipo, la "
                    "cantidad de ejercicios y el modo de evaluación real disponible. "
                    "Las respuestas se conservan mientras avanzas.</p>"
                )
                actividad_selector = gr.Radio(
                    opciones_catalogo, value=None, label="Actividades disponibles",
                    elem_classes=["activity-cards"],
                )
                catalogo_nota = gr.HTML(
                    vistas.catalogo_nota_html(estados_iniciales, etiquetas_actividad)
                )
                actividad_status = gr.HTML(elem_id="actividad-status")
                with gr.Group(visible=False, elem_classes=["activity-panel"]) as panel_actividad:
                    actividad_encabezado = gr.HTML()
                    with gr.Row(elem_classes=["lab-layout"]):
                        with gr.Column(elem_classes=["lab-editor"]):
                            respuesta_sql = gr.Code(
                                value="", language="sql", lines=10, visible=False,
                                label="Tu consulta SQL",
                            )
                            respuesta_opcion = gr.Radio(
                                [], visible=False, label="Selecciona una respuesta",
                                elem_classes=["sql-choice"],
                            )
                            respuesta_texto = gr.Textbox(
                                lines=8, visible=False, label="Tu respuesta"
                            )
                            actividad_revision = gr.HTML()
                            with gr.Row(elem_classes=["button-row"]):
                                actividad_anterior = gr.Button("Anterior", visible=False)
                                actividad_siguiente = gr.Button("Siguiente", visible=False)
                                revisar_actividad = gr.Button(
                                    "Revisar y enviar", visible=False
                                )
                                enviar_actividad = gr.Button(
                                    "Calificar", variant="primary", visible=False
                                )
                        with gr.Column(elem_classes=["lab-reference"]):
                            actividad_referencia = gr.HTML()
                            with gr.Accordion("Filas de ejemplo", open=False) as lab_datos_acc:
                                lab_datos_html = gr.HTML()
                    with gr.Accordion("Detalles del intento", open=False):
                        detalles_html = gr.HTML()

            # ── Resultados ─────────────────────────────────────────────────
            with gr.Tab("Resultados", id="resultados"):
                resultado_principal = gr.HTML(
                    "<section class='empty-card'><span class='eyebrow'>Resultados</span>"
                    "<h2>Aún no hay resultados</h2><p class='muted'>Completa una actividad "
                    "para revisar el puntaje, los criterios y su efecto en la ruta.</p></section>"
                )
                resultado_efecto = gr.HTML()
                with gr.Accordion("Revisión por pregunta o ejercicio", open=False):
                    resultado_revision = gr.HTML(
                        "<p class='muted small'>El detalle aparecerá después de calificar.</p>"
                    )
                with gr.Accordion("Comentario y refuerzo", open=False):
                    resultado_retro = gr.HTML()
                resultado_recurso = gr.HTML()
                with gr.Row(elem_classes=["button-row"]):
                    reintentar = gr.Button("Reintentar")
                    otra_actividad = gr.Button("Elegir otra actividad")
                    volver_ruta = gr.Button("Volver a Mi ruta", variant="primary")
                with gr.Row(elem_classes=["button-row"]):
                    volver_diagnostico = gr.Button("Volver al diagnóstico")
                    continuar_siguiente = gr.Button("Continuar con el siguiente tema")
                    elegir_meta = gr.Button("Elegir otra meta", visible=False)


        # ── Navegación entre pestañas ──────────────────────────────────────
        # Gradio 6 no permite que gr.Tabs sea un componente de salida, así que
        # el cambio de pestaña se hace con un evento JS encadenado al callback.
        def js_tab(tab_id: str) -> str:
            return (
                "() => {"
                "const el = document.querySelector('#main-nav [role=\"tab\"]"
                f"[data-tab-id=\"{tab_id}\"]');"
                "if (el) el.click();"
                "}"
            )

        JS_INICIO = js_tab("inicio")
        JS_DIAGNOSTICO = js_tab("diagnostico")
        JS_RUTA = js_tab("ruta")
        JS_ACTIVIDAD = js_tab("actividad")
        JS_RESULTADOS = js_tab("resultados")
        JS_INICIAR = (
            "() => {"
            "const resumen = document.querySelector('#inicio-resumen');"
            "const destino = resumen && resumen.textContent.includes('Simulación local recuperada')"
            " ? 'ruta' : 'diagnostico';"
            "const el = document.querySelector('#main-nav [role=\"tab\"]"
            "[data-tab-id=\"' + destino + '\"]');"
            "if (el) el.click();"
            "}"
        )
        JS_ABRIR_ACTIVIDAD = (
            "() => {"
            "const status = document.querySelector('#actividad-status');"
            "if (status && status.textContent.includes('Actividad abierta')) {"
            "const el = document.querySelector('#main-nav [role=\"tab\"]"
            "[data-tab-id=\"actividad\"]');"
            "if (el) el.click();"
            "}"
            "}"
        )
        JS_VER_RESULTADOS = (
            "() => {"
            "const status = document.querySelector('#actividad-status');"
            "if (status && status.textContent.includes('Resultado guardado')) {"
            "const el = document.querySelector('#main-nav [role=\"tab\"]"
            "[data-tab-id=\"resultados\"]');"
            "if (el) el.click();"
            "}"
            "}"
        )
        JS_REINTENTO = (
            "() => {"
            "const status = document.querySelector('#actividad-status');"
            "if (status && status.textContent.includes('Reintento preparado')) {"
            "const el = document.querySelector('#main-nav [role=\"tab\"]"
            "[data-tab-id=\"actividad\"]');"
            "if (el) el.click();"
            "}"
            "}"
        )

        # ── Listas de salida reutilizadas ──────────────────────────────────
        RUTA_OUTPUTS = [
            ruta_cabecera, siguiente_paso, lista_pasos, grafo, tema_detalle,
            tema_grafo, ruta_aviso,
        ]
        HOME_OUTPUTS = [inicio_resumen, iniciar, home_cambiar_meta]
        DIAG_OUTPUTS = [
            paso_diagnostico, diag_paso_1, diag_paso_2, diag_paso_3,
            diag_encabezado, diag_anterior, diag_siguiente,
            acreditaciones_diag, disponibilidad_diag,
        ]
        INIT_OUTPUTS = [
            estado, *HOME_OUTPUTS, *RUTA_OUTPUTS, *DIAG_OUTPUTS,
            nivel, formato, tema_actual, tiempo, errores, meta, fallos, abandono,
        ]
        ACT_OUTPUTS = [
            estado, actividad_selector, panel_actividad,
            actividad_encabezado, actividad_referencia, lab_datos_acc,
            lab_datos_html, detalles_html, respuesta_sql, respuesta_opcion,
            respuesta_texto, actividad_anterior, actividad_siguiente,
            revisar_actividad, enviar_actividad, actividad_revision,
            actividad_status, ruta_aviso,
        ]
        SUBMIT_OUTPUTS = [
            estado, resultado_principal, resultado_efecto, resultado_revision,
            resultado_retro, resultado_recurso, reintentar, continuar_siguiente,
            elegir_meta, enviar_actividad, actividad_status,
            *RUTA_OUTPUTS, *HOME_OUTPUTS,
        ]
        RESET_OUTPUTS = [
            estado, *HOME_OUTPUTS, confirmar_reinicio, *RUTA_OUTPUTS,
            *DIAG_OUTPUTS,
            nivel, formato, tema_actual, tiempo, errores, meta, fallos, abandono,
            actividad_selector, panel_actividad, actividad_status,
            resultado_principal, resultado_efecto, resultado_revision,
            resultado_retro, resultado_recurso, reintentar, continuar_siguiente,
            elegir_meta, catalogo_nota,
        ]

        # ── Inicio ─────────────────────────────────────────────────────────
        def iniciar_fn(actual: dict[str, Any]):
            nuevo = _recargar(motor)
            home = home_render(nuevo)
            route = ruta_render(nuevo)
            diag = diag_render(1, nuevo["perfil"]["tema"], nuevo)
            perfil = perfil_updates(nuevo["perfil"])
            return (nuevo, *home, *route, *diag, *perfil)

        iniciar.click(iniciar_fn, estado, INIT_OUTPUTS).then(
            None, None, None, js=JS_INICIAR
        )

        reiniciar.click(lambda: gr.update(visible=True), outputs=confirmar_reinicio)
        cancelar_reinicio.click(lambda: gr.update(visible=False), outputs=confirmar_reinicio)

        def confirmar_reinicio_fn():
            simulacion.reiniciar()
            nuevo = _recargar(motor)
            home = home_render(nuevo)
            route = ruta_render(nuevo)
            diag = diag_render(1, nuevo["perfil"]["tema"], nuevo)
            perfil = perfil_updates(nuevo["perfil"])
            placeholder = (
                "<section class='empty-card'><span class='eyebrow'>Resultados</span>"
                "<h2>Aún no hay resultados</h2><p class='muted'>Completa una actividad "
                "para revisar el puntaje, los criterios y su efecto en la ruta.</p></section>"
            )
            nota = vistas.catalogo_nota_html(
                metricas(nuevo)["estados"],
                {t: _info_actividad(t)["etiqueta"] or "" for t in motor.temas},
            )
            return (
                nuevo, *home, gr.update(visible=False),
                *route, *diag, *perfil,
                gr.update(value=None), gr.update(visible=False), "",
                placeholder, "", "<p class='muted small'>El detalle aparecerá después de calificar.</p>",
                "", "", gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), nota,
            )

        confirmar.click(confirmar_reinicio_fn, outputs=RESET_OUTPUTS).then(
            None, None, None, js=JS_INICIO
        )

        # ── Diagnóstico ────────────────────────────────────────────────────
        def mover_paso(paso: int, tema_valor: str, actual: dict[str, Any], direccion: int):
            return diag_render(int(paso) + direccion, tema_valor, actual)

        diag_siguiente.click(
            lambda paso, tema_v, actual: mover_paso(paso, tema_v, actual, 1),
            [paso_diagnostico, tema_evaluar, estado], DIAG_OUTPUTS,
        )
        diag_anterior.click(
            lambda paso, tema_v, actual: mover_paso(paso, tema_v, actual, -1),
            [paso_diagnostico, tema_evaluar, estado], DIAG_OUTPUTS,
        )
        meta.change(render_meta_detalle, [meta, estado], meta_detalle)
        tema_evaluar.change(disponibilidad, [tema_evaluar, estado], disponibilidad_diag)

        def ir_a_diagnostico(actual: dict[str, Any], tema_v: str, paso: int = 1):
            return diag_render(paso, tema_v, actual)

        def conectar_diagnostico(boton, fn):
            boton.click(fn, estado, DIAG_OUTPUTS).then(
                None, None, None, js=JS_DIAGNOSTICO
            )

        conectar_diagnostico(
            home_cambiar_meta,
            lambda actual: ir_a_diagnostico(actual, actual["perfil"]["tema"], 1),
        )
        conectar_diagnostico(
            cambiar_meta,
            lambda actual: ir_a_diagnostico(actual, actual["perfil"]["tema"], 1),
        )
        conectar_diagnostico(
            elegir_meta,
            lambda actual: ir_a_diagnostico(actual, actual["perfil"]["tema"], 1),
        )
        volver_diagnostico.click(
            lambda actual, tema_v: ir_a_diagnostico(actual, tema_v, 3),
            [estado, tema_evaluar], DIAG_OUTPUTS,
        ).then(None, None, None, js=JS_DIAGNOSTICO)

        def generar_ruta_fn(
            nivel_v, formato_v, tema_v, tiempo_v, errores_v, meta_v,
            fallos_v, abandono_v, actual: dict[str, Any],
        ):
            perfil = {
                "nivel": nivel_v, "formato": formato_v, "tema": tema_v,
                "tiempo": tiempo_v, "errores": errores_v, "meta": meta_v,
                "fallos": int(fallos_v), "abandono": bool(abandono_v),
            }
            try:
                guardado = _persistir_perfil(perfil)
            except (ErrorProgreso, ValueError) as exc:
                return (
                    actual,
                    f"<div class='callout bad'><b>No se guardó el perfil.</b> {exc}</div>",
                    gr.update(), *[gr.update() for _ in range(10)],
                )
            nuevo = deepcopy(actual)
            nuevo["perfil"] = perfil
            nuevo["completados"] = temas_acreditados(guardado)
            nuevo["intentos"] = guardado["intentos"]
            nuevo["simulacion_activa"] = guardado["simulacion_activa"]
            _actualizar_recomendacion(motor, nuevo)
            route = ruta_render(nuevo)
            home = home_render(nuevo)
            aviso = (
                "<div class='callout good'>Ruta actualizada con tus acreditaciones "
                "verificadas. Las selecciones del diagnóstico no crearon acreditaciones.</div>"
            )
            return (nuevo, aviso, *route, *home)

        generar_ruta.click(
            generar_ruta_fn,
            [nivel, formato, tema_actual, tiempo, errores, meta, fallos, abandono, estado],
            [estado, aviso_diag, *RUTA_OUTPUTS, *HOME_OUTPUTS],
        ).then(None, None, None, js=JS_RUTA)

        # ── Actividad: apertura y navegación ───────────────────────────────
        def abrir_evaluacion(tema_v: str, actual: dict[str, Any]):
            info = _info_actividad(tema_v)
            clave = info["clave"]
            if not clave:
                mensaje = (
                    f"Evaluación no disponible para {tema_v}. {info['detalle']}"
                )
                return act_full(
                    actual, nav_update=gr.update(selected="diagnostico"),
                    selector_update=gr.update(value=None), mensaje=mensaje,
                    tipo_mensaje="warn", ruta_update="",
                ) + (mensaje,)
            nuevo, aviso, ok = crear_actividad(
                clave, actual, origen="diagnostico", permitir_bloqueado=True
            )
            if not ok:
                return act_full(
                    actual, nav_update=gr.update(selected="diagnostico"),
                    selector_update=gr.update(value=None), mensaje=aviso,
                    tipo_mensaje="bad",
                ) + (aviso,)
            mensaje = aviso or "Actividad abierta desde el diagnóstico."
            return act_full(
                nuevo, nav_update=gr.update(selected="actividad"),
                selector_update=gr.update(value=clave), mensaje=mensaje,
            ) + ("",)

        evaluar_tema.click(
            abrir_evaluacion, [tema_evaluar, estado], [*ACT_OUTPUTS, aviso_diag]
        ).then(None, None, None, js=JS_ABRIR_ACTIVIDAD)

        def seleccionar_actividad(clave: str, actual: dict[str, Any]):
            if not clave:
                return act_full(
                    actual, mensaje="Selecciona una tarjeta para abrir su actividad.",
                    tipo_mensaje="info",
                )
            nuevo, aviso, ok = crear_actividad(
                clave, actual, origen="actividad", permitir_bloqueado=True
            )
            if not ok:
                return act_full(
                    actual, selector_update=gr.update(value=None), mensaje=aviso,
                    tipo_mensaje="warn",
                )
            return act_full(
                nuevo, nav_update=gr.update(selected="actividad"),
                selector_update=gr.update(value=clave),
                mensaje="Actividad cargada desde el banco real. La variante queda estable durante el intento.",
            )

        actividad_selector.select(
            seleccionar_actividad, [actividad_selector, estado], ACT_OUTPUTS
        )

        def mover_actividad(direccion: int, codigo, opcion, texto, actual: dict[str, Any]):
            nuevo = deepcopy(actual)
            act = nuevo.get("actividad")
            if not act:
                return act_full(nuevo, mensaje="Selecciona una actividad.", tipo_mensaje="warn")
            guardar_respuesta(act, codigo, opcion, texto)
            act["indice"] = max(0, min(len(act["items"]) - 1, act["indice"] + direccion))
            act["revisando"] = False
            return act_full(nuevo)

        NAV_INPUTS = [respuesta_sql, respuesta_opcion, respuesta_texto, estado]
        actividad_anterior.click(
            lambda c, o, t, actual: mover_actividad(-1, c, o, t, actual),
            NAV_INPUTS, ACT_OUTPUTS,
        )
        actividad_siguiente.click(
            lambda c, o, t, actual: mover_actividad(1, c, o, t, actual),
            NAV_INPUTS, ACT_OUTPUTS,
        )

        def revisar_fn(codigo, opcion, texto, actual: dict[str, Any]):
            nuevo = deepcopy(actual)
            act = nuevo.get("actividad")
            if not act:
                return act_full(nuevo, mensaje="Selecciona una actividad.", tipo_mensaje="warn")
            guardar_respuesta(act, codigo, opcion, texto)
            act["indice"] = len(act["items"]) - 1
            act["revisando"] = True
            return act_full(nuevo)

        revisar_actividad.click(revisar_fn, NAV_INPUTS, ACT_OUTPUTS)

        # ── Actividad: calificación real (generador con estado visible) ────
        def enviar_fn(codigo, opcion, texto, actual: dict[str, Any]):
            nuevo = deepcopy(actual)
            act = nuevo.get("actividad")
            if not act:
                aviso = "<div class='callout warn'>Selecciona una actividad antes de calificar.</div>"
                yield (
                    nuevo, *[gr.update() for _ in range(8)],
                    gr.update(interactive=True), aviso,
                    *[gr.update() for _ in range(10)],
                )
                return
            if act.get("enviado"):
                aviso = (
                    "<div class='callout warn'>Este intento ya fue enviado. "
                    "Usa Reintentar para una nueva variante.</div>"
                )
                yield (
                    nuevo, *[gr.update() for _ in range(8)], gr.update(),
                    gr.update(interactive=True), aviso,
                    *[gr.update() for _ in range(10)],
                )
                return
            guardar_respuesta(act, codigo, opcion, texto)
            act["revisando"] = True
            segundos = max(0.0, time.monotonic() - act.get("inicio", time.monotonic()))
            etiqueta = (
                "Calificando…" if act["tipo"] != "poo" else "Entregando…"
            )
            estado_txt = (
                "<div class='callout'>Calificando… El calificador real está procesando "
                "las respuestas.</div>"
                if act["tipo"] != "poo"
                else "<div class='callout'>Entregando… Se está registrando la práctica "
                "para revisión.</div>"
            )
            yield (
                nuevo, *[gr.update() for _ in range(8)],
                gr.update(value=etiqueta, interactive=False), estado_txt,
                *[gr.update() for _ in range(10)],
            )
            try:
                if act["clave"] == "poo":
                    respuestas = act["respuestas"]
                    detalle = [
                        {
                            "id": item["id"],
                            "concepto": item.get("concepto", ""),
                            "correcto": bool(str(respuestas.get(item["id"], "")).strip()),
                            "criterios_cumplidos": [],
                            "criterios_incumplidos": [],
                        }
                        for item in act["items"]
                    ]
                    bruto = {
                        "tipo": "poo",
                        "tema": act["tema"],
                        "acreditado": False,
                        "respondidos": sum(bool(str(v).strip()) for v in respuestas.values()),
                        "total": len(act["items"]),
                        "detalle": detalle,
                        "conceptos_con_errores": [],
                    }
                    persistible = {
                        "id": act["intento_id"],
                        "tema": act["tema"],
                        "tipo_actividad": "Práctica POO",
                        "puntaje": bruto["respondidos"],
                        "puntaje_maximo": bruto["total"],
                        "tiempo_segundos": segundos,
                        "conceptos_con_error": [],
                        "aprobado": False,
                        "detalle": detalle,
                    }
                elif act["clave"] == "pg_lab":
                    bruto = calificar_laboratorio(act["respuestas"], segundos)
                    bruto["intento"] = act["intento_id"]
                    persistible = normalizar_resultado_calificador(bruto)
                elif act["clave"] == "pg_seg":
                    bruto = calificar_seguimiento(
                        act["respuestas"], segundos, variante_usada=act["variante"]
                    )
                    bruto["intento"] = act["intento_id"]
                    persistible = normalizar_resultado_calificador(bruto)
                elif act["clave"] == "node_lab":
                    bruto = calificar_laboratorio_node(act["respuestas"], segundos)
                    bruto["intento"] = act["intento_id"]
                    persistible = normalizar_resultado_calificador(bruto)
                else:
                    bruto = calificar_seguimiento_node(
                        act["respuestas"], segundos, act["variante"]
                    )
                    bruto["intento"] = act["intento_id"]
                    persistible = normalizar_resultado_calificador(bruto)
                guardado = simulacion.persistir_intento(persistible)
            except (ErrorProgreso, ValueError, TypeError, OverflowError, KeyError) as exc:
                mensaje = (
                    "<div class='callout bad'><b>No se pudo guardar el intento.</b> "
                    f"{exc} Tus respuestas siguen disponibles: vuelve a intentarlo o "
                    "elige otra actividad.</div>"
                )
                yield (
                    nuevo, *[gr.update() for _ in range(8)],
                    gr.update(value=(
                        "Calificar seguimiento" if act["tipo"] == "seguimiento"
                        else "Entregar práctica POO" if act["tipo"] == "poo"
                        else "Calificar laboratorio"
                    ), interactive=True),
                    mensaje, *[gr.update() for _ in range(10)],
                )
                return

            act["enviado"] = True
            act["revisando"] = True
            nuevo["completados"] = temas_acreditados(guardado)
            nuevo["intentos"] = guardado["intentos"]
            nuevo["variantes_usadas"] = [
                i["variante"] for i in guardado["intentos"] if i.get("variante")
            ]
            nuevo["simulacion_activa"] = guardado["simulacion_activa"]
            _actualizar_recomendacion(motor, nuevo)
            bruto["_respuestas"] = dict(act["respuestas"])
            bruto["_items"] = deepcopy(act["items"])
            bruto["_titulo"] = act.get("titulo", "")
            nuevo["resultado"] = bruto
            nuevo["resultado_origen"] = act.get("origen", "actividad")
            principal, efecto, revision, retro, recurso, b1, b2, b3 = render_resultado(bruto, nuevo)
            route = ruta_render(nuevo)
            home = home_render(nuevo)
            status = (
                "<div class='callout good'><b>Resultado guardado.</b> El intento se "
                "registró y la ruta se recalculó con las acreditaciones verificadas.</div>"
            )
            yield (
                nuevo, principal, efecto, revision, retro, recurso, b1, b2, b3,
                gr.update(value="Intento enviado", interactive=False), status,
                *route, *home,
            )

        enviar_actividad.click(enviar_fn, NAV_INPUTS, SUBMIT_OUTPUTS).then(
            None, None, None, js=JS_VER_RESULTADOS
        )

        # ── Mi ruta ────────────────────────────────────────────────────────
        def abrir_siguiente_fn(actual: dict[str, Any]):
            siguiente = actual["recomendacion"].get("siguiente_tema")
            if not siguiente:
                aviso = "La meta está completada. Puedes elegir otra meta conservando tu historial."
                return act_full(
                    actual, nav_update=gr.update(selected="ruta"),
                    mensaje=aviso, tipo_mensaje="good", ruta_update=f"<div class='callout good'>{aviso}</div>",
                )
            info = _info_actividad(siguiente)
            clave = info["clave"]
            if not clave:
                aviso = (
                    f"La actividad de {siguiente} no está conectada. Consulta sus "
                    "recursos en Mi ruta y el estado real de la evaluación."
                )
                return act_full(
                    actual, nav_update=gr.update(selected="ruta"),
                    mensaje=aviso, tipo_mensaje="warn",
                    ruta_update=f"<div class='callout warn'>{aviso}</div>",
                )
            nuevo, aviso, ok = crear_actividad(clave, actual, origen="actividad")
            if not ok:
                return act_full(
                    actual, nav_update=gr.update(selected="ruta"), mensaje=aviso,
                    tipo_mensaje="warn", ruta_update=f"<div class='callout warn'>{aviso}</div>",
                )
            return act_full(
                nuevo, nav_update=gr.update(selected="actividad"),
                selector_update=gr.update(value=clave),
                mensaje=f"Actividad abierta: {siguiente}.",
            )

        abrir_siguiente.click(abrir_siguiente_fn, estado, ACT_OUTPUTS).then(
            None, None, None, js=JS_ABRIR_ACTIVIDAD
        )
        continuar_siguiente.click(abrir_siguiente_fn, estado, ACT_OUTPUTS).then(
            None, None, None, js=JS_ABRIR_ACTIVIDAD
        )

        def actualizar_ruta_fn(actual: dict[str, Any]):
            nuevo = _recargar(motor)
            return (nuevo, *ruta_render(nuevo), *home_render(nuevo))

        actualizar_ruta.click(
            actualizar_ruta_fn, estado, [estado, *RUTA_OUTPUTS, *HOME_OUTPUTS]
        )

        def mostrar_tema(tema_v: str, actual: dict[str, Any]):
            figura = _dibujar_grafo(motor, actual["completados"], tema_v)
            return figura, detalle_ui(actual, tema_v), ""

        tema_grafo.select(mostrar_tema, [tema_grafo, estado], [grafo, tema_detalle, ruta_aviso])

        def ir_prerrequisito_fn(tema_v: str, actual: dict[str, Any]):
            _, faltantes = _estado_del_tema(motor, tema_v, actual["completados"])
            destino = faltantes[0] if faltantes else actual["recomendacion"].get("siguiente_tema")
            if not destino or destino not in motor.temas:
                route = ruta_render(actual)
                return route[3], route[4], route[5], (
                    "<div class='callout good'>Este tema no tiene prerrequisitos pendientes.</div>"
                )
            route = ruta_render(actual, destino)
            return route[3], route[4], route[5], (
                f"<div class='callout'>Mostrando el prerrequisito pendiente: <b>{destino}</b>.</div>"
            )

        ir_prerrequisito.click(
            ir_prerrequisito_fn, [tema_grafo, estado],
            [grafo, tema_detalle, tema_grafo, ruta_aviso],
        )

        # ── Resultados y reinicio ──────────────────────────────────────────
        def reintentar_fn(actual: dict[str, Any]):
            act = actual.get("actividad")
            if not act:
                return act_full(
                    actual, nav_update=gr.update(selected="actividad"),
                    selector_update=gr.update(value=None),
                    mensaje="Elige una actividad para reintentar.", tipo_mensaje="warn",
                )
            nuevo, aviso, ok = crear_actividad(
                act["clave"], actual, origen=act.get("origen", "actividad"),
                permitir_bloqueado=True,
            )
            if not ok:
                return act_full(actual, mensaje=aviso, tipo_mensaje="warn")
            return act_full(
                nuevo, nav_update=gr.update(selected="actividad"),
                selector_update=gr.update(value=act["clave"]),
                mensaje="Reintento preparado sin agregar un intento. Envía cuando termines.",
            )

        reintentar.click(reintentar_fn, estado, ACT_OUTPUTS).then(
            None, None, None, js=JS_REINTENTO
        )

        otra_actividad.click(
            lambda: (
                gr.update(value=None),
                gr.update(visible=False), "",
            ),
            outputs=[actividad_selector, panel_actividad, actividad_status],
        ).then(None, None, None, js=JS_ACTIVIDAD)
        volver_ruta.click(
            lambda actual: ruta_render(actual),
            estado, RUTA_OUTPUTS,
        ).then(None, None, None, js=JS_RUTA)

    return demo



