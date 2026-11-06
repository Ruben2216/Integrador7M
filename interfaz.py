"""Interfaz Gradio del recomendador — versión integrada.

Montaje visual sobre la lógica del compañero (commit cc8bca1):
  · calificador_mvc, laboratorio PHP MVC, seguimientos PHP/PostgreSQL/Node.js
  · retroalimentación local, IA/Gemini, rúbrica de retroalimentación
  · variantes de seguimiento, botón de explicación con IA

La presentación usa vistas semánticas de ``ui/vistas.py`` y el CSS centralizado
de ``ui/estilos.py``. La lógica de calificación, persistencia y motor A* se
conserva íntegramente sin cambios de responsabilidad.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any
from uuid import uuid4

import gradio as gr

from calificador import (
    calificar_laboratorio,
    calificar_seguimiento,
    obtener_ejercicios_laboratorio,
    obtener_variante_seguimiento,
)
from calificador_mvc import (
    calificar_laboratorio_mvc,
    calificar_seguimiento_mvc,
    obtener_conceptos_mvc,
    obtener_ejercicios_laboratorio_mvc,
    obtener_variante_seguimiento_mvc,
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
from retroalimentacion import (
    cargar_config,
    estado_gemini,
    generar_retroalimentacion,
    solicitar_explicacion,
)
from ui import vistas
from ui.actividad import VistaActividad
from ui.resultados import renderizar_retroalimentacion
from ui.estilos import CSS

_DIR = os.path.dirname(os.path.abspath(__file__))
_RUTA_CATALOGO = os.path.join(_DIR, "catalogo_recursos.json")
_RUTA_POO = os.path.join(_DIR, "ejercicios_poo.json")


# ── Carga y estado ──────────────────────────────────────────────────────────
def _cargar_json(ruta: str) -> dict[str, Any]:
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def _cargar_catalogo() -> dict[str, dict[str, Any]]:
    return _cargar_json(_RUTA_CATALOGO)


def _estado_inicial(motor: Any) -> dict[str, Any]:
    error_progreso = None
    try:
        guardado = simulacion.almacen.cargar()
    except ErrorProgreso as exc:
        from progreso import estado_inicial as crear_estado_vacio

        guardado = crear_estado_vacio()
        error_progreso = str(exc)
    perfil_guardado = guardado.get("perfil", {})
    profile = {
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
    variantes_usadas = [
        intento["variante"] for intento in guardado["intentos"] if intento.get("variante")
    ]
    return {
        "perfil": profile,
        "completados": completados,
        "recomendacion": motor.consultar(**profile, completados=completados),
        "variantes_usadas": variantes_usadas,
        "variante_activa": None,
        "tipo_actividad": None,
        "inicio_actividad": None,
        "resultado": None,
        "simulacion_activa": guardado["simulacion_activa"],
        "intentos": guardado["intentos"],
        "error_progreso": error_progreso,
    }


# ── Consultas al grafo y catálogo ───────────────────────────────────────────
def _estado_del_tema(motor: Any, tema: str, completados: list[str]) -> tuple[str, list[str]]:
    nodo = TEMA_A_NODO[tema]
    if tema in completados:
        return "Acreditado", []
    faltantes = [
        NODO_A_TEMA[pre] for pre in motor.grafo[nodo]["prerrequisitos"]
        if NODO_A_TEMA[pre] not in completados
    ]
    return ("Bloqueado", faltantes) if faltantes else ("Disponible", [])


def _temas_pertinentes(motor: Any, meta: str) -> list[str]:
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


def _recursos_html(catalogo: dict[str, dict[str, Any]], tema: str, motor: Any) -> str:
    nodo = TEMA_A_NODO[tema]
    return vistas.recursos_html(catalogo, motor.grafo[nodo]["recursos"])


def _meta_detalle(motor: Any, catalogo: dict[str, dict[str, Any]], meta: str, completados: list[str]) -> str:
    nodo = TEMA_A_NODO[meta]
    prerequisitos = [NODO_A_TEMA[n] for n in motor.grafo[nodo]["prerrequisitos"]]
    pendientes = [t for t in prerequisitos if t not in completados]
    return vistas.meta_detalle_html(meta, prerequisitos, pendientes, _recursos_html(catalogo, tema=meta, motor=motor))


def _disponibilidad(motor: Any, tema: str, completados: list[str]) -> str:
    estado, faltantes = _estado_del_tema(motor, tema, completados)
    info = {
        "Programación Orientada a Objetos": ("Práctica de POO · 4 retos · Revisión", "Práctica abierta para revisión docente"),
        "Bases de Datos PostgreSQL": ("Laboratorio (4 ejercicios) o seguimiento (5 preguntas)", "Calificación automática con el calificador real de PostgreSQL."),
        "Backend con Node.js": ("Laboratorio (5 puntos) o seguimiento (5 preguntas)", "Calificación automática con el calificador real de Node.js."),
        "Lógica de Programación": ("Evaluación no disponible", "Hay ejercicios, pero no un evaluador conectado en esta rama."),
        "Patrón MVC en PHP": ("Evaluación no disponible", "No hay evaluador conectado para este tema."),
    }.get(tema, ("Evaluación no disponible", "Sin actividad conectada."))
    return vistas.disponibilidad_html(tema, estado, faltantes, info[0], info[1])


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
    nx.draw_networkx_edges(grafo, posicion, ax=ax, arrows=True, arrowsize=17,
                           edge_color="#5D7088", width=1.4, node_size=4300)
    nx.draw_networkx_nodes(grafo, posicion, ax=ax, node_color=colores, edgecolors=bordes,
                           linewidths=2.4, node_size=4300)
    etiquetas = {nodo: NODO_A_TEMA[nodo].replace(" ", "\n", 2) for nodo in grafo.nodes}
    nx.draw_networkx_labels(grafo, posicion, labels=etiquetas, ax=ax, font_size=7.5,
                            font_color="#08111F", font_weight="bold")
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


def _vista_ruta(motor: Any, catalogo: dict[str, dict[str, Any]], estado: dict[str, Any]):
    recomendacion = estado["recomendacion"]
    completados = estado["completados"]
    temas = motor.temas
    porcentaje = round(100 * len(completados) / len(temas))
    ruta = recomendacion["ruta_pendiente"]
    siguiente = recomendacion.get("siguiente_tema") or "Meta completada"

    cabecera = vistas.ruta_cabecera_html(
        estado["perfil"]["meta"], len([t for t in _temas_pertinentes(motor, estado["perfil"]["meta"]) if t in completados]),
        len(_temas_pertinentes(motor, estado["perfil"]["meta"])),
        recomendacion.get("estado_meta", "En progreso"), completados,
    )

    estados = {t: _estado_del_tema(motor, t, completados) for t in temas}
    next_theme = recomendacion.get("siguiente_tema")
    if next_theme:
        estado_next, faltantes_next = estados[next_theme]
        explicacion = (
            "El motor A* lo coloca como el primer paso disponible para tu meta."
            if estado_next != "Bloqueado"
            else "La ruta lo señala, pero todavía tiene prerrequisitos pendientes."
        )
        siguiente_html = vistas.siguiente_paso_html(
            next_theme, explicacion,
            "Actividad conectada: consulta Mi ruta.",
            _recursos_html(catalogo, next_theme, motor),
            faltantes_next if estado_next == "Bloqueado" else (),
        )
    else:
        siguiente_html = vistas.siguiente_paso_html(None, "", None, "")

    lista_html = vistas.lista_pasos_html(temas, estados, next_theme, recomendacion.get("ruta_pendiente", []))
    seleccionado = next_theme if next_theme in temas else temas[0]
    figura = _dibujar_grafo(motor, completados, seleccionado)
    detalle = vistas.tema_detalle_html(
        seleccionado, estados[seleccionado][0],
        [NODO_A_TEMA[n] for n in motor.grafo[TEMA_A_NODO[seleccionado]]["prerrequisitos"]],
        [t for t in [NODO_A_TEMA[n] for n in motor.grafo[TEMA_A_NODO[seleccionado]]["prerrequisitos"]] if t not in completados],
        _recursos_html(catalogo, seleccionado, motor),
        "Consulta Mi ruta", "", es_siguiente=True,
    )
    return cabecera, siguiente_html, lista_html, figura, detalle, gr.update(value=seleccionado)


def _actualizar_recomendacion(motor: Any, estado: dict[str, Any]) -> None:
    estado["recomendacion"] = motor.consultar(
        **estado["perfil"], completados=estado["completados"],
    )


def _persistir_perfil(perfil: dict[str, Any]) -> dict[str, Any]:
    store = simulacion.almacen
    guardado = store.cargar()
    if guardado["simulacion_activa"]:
        guardado.update(
            meta=perfil["meta"], formato_preferido=perfil["formato"], nivel=perfil["nivel"]
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


# ── Actividades conectadas ─────────────────────────────────────────────────
SEGUIMIENTOS = {
    "PostgreSQL · seguimiento": (obtener_variante_seguimiento, calificar_seguimiento),
    "PHP MVC · seguimiento": (obtener_variante_seguimiento_mvc, calificar_seguimiento_mvc),
}

GEMINI_ACTIVO = cargar_config().disponible
TEXTO_BOTON_IA = "Pedir explicación con IA (Gemini)"
CARGANDO_IA_HTML = (
    '<div style="display:flex;align-items:center;gap:12px;padding:12px 4px;">'
    '<svg width="26" height="26" viewBox="0 0 50 50" aria-hidden="true">'
    '<circle cx="25" cy="25" r="20" fill="none" stroke="#d0d7de" stroke-width="5"/>'
    '<circle cx="25" cy="25" r="20" fill="none" stroke="#f97316" stroke-width="5" '
    'stroke-linecap="round" stroke-dasharray="80 126">'
    '<animateTransform attributeName="transform" type="rotate" from="0 25 25" '
    'to="360 25 25" dur="0.9s" repeatCount="indefinite"/></circle></svg>'
    '<span>Generando la explicación con Gemini… puede tardar unos segundos.</span></div>'
)


def _boton_ia(habilitado: bool, texto: str = TEXTO_BOTON_IA) -> dict[str, Any]:
    if not GEMINI_ACTIVO:
        return {"value": "Explicación con IA no disponible (Gemini no configurado)",
                "interactive": False}
    return {"value": texto, "interactive": habilitado}


def _retroalimentacion_local(resultado: dict[str, Any], formato: str | None):
    try:
        return generar_retroalimentacion(resultado, formato)
    except Exception:
        return None


# ── Resultado ───────────────────────────────────────────────────────────────
def _resultado_markdown(resultado: dict[str, Any], retroalimentacion=None, motor=None, catalogo=None) -> str:
    tema = NODO_A_TEMA.get(resultado.get("tema"), resultado.get("tema", "Tema"))
    try:
        _ = TEMA_A_NODO[tema]
        tema_en_grafo = tema
    except KeyError:
        tema_en_grafo = None
    if resultado.get("tipo") == "poo":
        respondidos = resultado["respondidos"]
        principal = vistas.resultado_principal_html(
            resultado, {}, "Práctica de POO · 4 retos"
        )
        principal = (
            '<section class="result-card">'
            '<span class="eyebrow">Resultado verificado</span>'
            f"<h2>{tema}</h2>"
            '<p class="muted small">Práctica de POO · 4 retos</p>'
            f'<div class="score-line"><b>{respondidos} / 4</b><span class="muted">respuestas entregadas</span>'
            '• Práctica entregada · pendiente de revisión</div>'
            '<div class="entity-grid" style="margin-top:14px">'
            '<div><h3>Qué hiciste bien</h3>'
            '<ul class="criteria-list"><li class="criteria-ok">✓ Entregaste tu solución para revisión.</li>'
            f'<li class="criteria-ok">✓ Completaste {respondidos} / 4 retos.</li></ul></div>'
            '<div><h3>Qué debes reforzar</h3>'
            '<ul class="criteria-list"><li class="criteria-bad">! La práctica no tiene evaluador automático conectado; no se acredita hasta la revisión.</li></ul></div>'
            '</div></section>'
        )
        efecto = (
            '<section class="route-card"><span class="eyebrow">Cómo afecta tu ruta</span>'
            "<h3>Práctica entregada · pendiente de revisión</h3>"
            '<p class="muted">La práctica abierta se entrega para revisión; no acredita el tema por sí sola.</p></section>'
        )
        revision = vistas.resultado_revision_html(resultado, {})
        retro = vistas.resultado_retro_html(resultado)
        recursos = _recursos_html(catalogo, tema_en_grafo, motor) if catalogo and motor and tema_en_grafo else ""
        return principal, efecto, revision, retro, vistas.recurso_repaso_html(recursos)

    acreditado = resultado["acreditado"]
    if resultado["tipo"] == "laboratorio":
        correctas = resultado.get("puntaje_obtenido", resultado.get("ejercicios_correctos", 0))
        total = resultado.get("puntaje_maximo", resultado.get("total_ejercicios", 0))
        detalle = resultado.get("detalle", [])
    else:
        correctas = resultado.get("correctas", 0)
        total = resultado.get("total_preguntas", 0)
        detalle = resultado.get("detalle", [])

    cumplidos = resultado.get("criterios_cumplidos", [])
    incumplidos = resultado.get("criterios_incumplidos", [])
    conceptos = list(resultado.get("conceptos_con_errores", []))

    bien = [f"✓ {c}" for c in cumplidos] if cumplidos else ["No hubo criterios cumplidos registrados."]
    reforzar = [f"! {c}" for c in incumplidos] if incumplidos else []
    if conceptos:
        reforzar.append(f"Conceptos a repasar: {', '.join(conceptos)}.")
    if not reforzar:
        reforzar = ["No se registraron criterios incumplidos."]

    bien_html = "".join(f'<li class="criteria-ok">{x}</li>' for x in bien)
    ref_html = "".join(f'<li class="criteria-bad">{x}</li>' for x in reforzar)

    estado_texto = "Tema acreditado" if acreditado else "Tema pendiente"
    principal = (
        '<section class="result-card">'
        '<span class="eyebrow">Resultado verificado</span>'
        f"<h2>{tema}</h2>"
        f'<p class="muted small">{resultado.get("tipo", "actividad").capitalize()}</p>'
        f'<div class="score-line"><b>{correctas} / {total}</b><span class="muted">aciertos o puntos</span>'
        f'• {estado_texto}</div>'
        '<div class="entity-grid" style="margin-top:14px">'
        f'<div><h3>Qué hiciste bien</h3><ul class="criteria-list">{bien_html}</ul></div>'
        f'<div><h3>Qué debes reforzar</h3><ul class="criteria-list">{ref_html}</ul></div>'
        '</div></section>'
    )

    rec = estado.get("recomendacion") if (estado := resultado.get("_estado")) else None
    siguiente = rec.get("siguiente_tema") if rec else None
    efecto = (
        f'<section class="route-card"><span class="eyebrow">Cómo afecta tu ruta</span>'
        f"<h3>{'Tema acreditado · ruta actualizada' if acreditado else 'Tema sigue pendiente'}</h3>"
        f'<p><b>Siguiente paso:</b> {siguiente or "revisa Mi ruta"}.</p>'
        '<p class="muted small">El bloqueo y el cierre de la meta provienen del motor A*.</p></section>'
    )
    revision = vistas.resultado_revision_html(resultado, {})
    retro = vistas.resultado_retro_html(resultado)
    recursos = _recursos_html(catalogo, tema, motor) if catalogo and motor else ""
    return principal, efecto, revision, retro, vistas.recurso_repaso_html(recursos)


# ── Montaje ─────────────────────────────────────────────────────────────────
def construir_interfaz(motor: Any) -> gr.Blocks:
    catalogo = _cargar_catalogo()
    banco_poo = _cargar_json(_RUTA_POO)
    ejercicios_lab = obtener_ejercicios_laboratorio()
    ejercicios_lab_node = obtener_ejercicios_laboratorio_node()
    ejercicios_mvc = obtener_ejercicios_laboratorio_mvc()
    conceptos_mvc = obtener_conceptos_mvc()
    estado_inicial = _estado_inicial(motor)
    progreso_activo = estado_inicial["simulacion_activa"]

    # ── Disponibilidad de actividades (catálogo visual) ─────────────────
    _ACTIVIDADES_POR_TEMA = {
        "Programación Orientada a Objetos": "Práctica de POO · 4 retos · Revisión",
        "Bases de Datos PostgreSQL": "Laboratorio (4 ejercicios) o seguimiento (5 preguntas)",
        "Backend con Node.js": "Laboratorio (5 puntos) o seguimiento (5 preguntas)",
        "Lógica de Programación": "Evaluación no disponible",
        "Patrón MVC en PHP": "Laboratorio (4 ejercicios) o seguimiento (5 preguntas)",
    }
    estados_actividad = {
        tema: _estado_del_tema(motor, tema, estado_inicial["completados"])
        for tema in motor.temas
    }
    actividades_por_tema = {
        tema: _ACTIVIDADES_POR_TEMA.get(tema, "Evaluación no disponible")
        for tema in motor.temas
    }
    catalogo_disponibilidad_html = vistas.catalogo_nota_html(
        estados_actividad, actividades_por_tema
    )

    criterios_mvc: list[str] = []

    # Estos montajes conservan el orden de entradas que reciben los calificadores.
    def montar_poo(ejercicio, numero):
        gr.HTML(vistas.actividad_enunciado_html(ejercicio))
        return [gr.Textbox(lines=6, label=f"Respuesta {ejercicio['id']}")]

    def montar_sql(ejercicio, numero):
        gr.HTML(vistas.actividad_enunciado_html(ejercicio))
        return [gr.Textbox(lines=10, label=f"Consulta SQL · {ejercicio['id']}",
                           elem_classes=["activity-editor"])]

    def ayuda_sql(ejercicio):
        gr.HTML(vistas.actividad_referencia_html({"modo": "sql"}, ejercicio))
        with gr.Accordion("Filas de ejemplo", open=False):
            gr.HTML(vistas.lab_datos_html(ejercicio))

    def montar_mvc(ejercicio, numero):
        gr.HTML(vistas.actividad_enunciado_html(
            ejercicio, conceptos_mvc.get(ejercicio["concepto"], ejercicio["concepto"])
        ))
        fragmentos = vistas.actividad_fragmentos_mvc(ejercicio)
        if ejercicio.get("codigo") and not fragmentos:
            gr.HTML(vistas.actividad_codigo_html(ejercicio["codigo"]))
        controles = []
        for criterio in ejercicio["criterios"]:
            with gr.Group(elem_classes=["activity-criterion"]):
                for nombre, codigo in fragmentos.items():
                    if criterio["pregunta"].startswith(nombre):
                        gr.HTML(vistas.actividad_codigo_html(codigo))
                criterios_mvc.append(criterio["id"])
                controles.append(gr.Radio(
                    criterio["opciones"], label=criterio["pregunta"], value=None,
                    elem_classes=["activity-options"],
                ))
        return controles

    def ayuda_mvc(ejercicio):
        gr.HTML(
            '<h3>Para este ejercicio</h3>'
            f'<p class="activity-caption">{vistas.e(ejercicio.get("criterio_evaluacion", ""))}</p>'
            '<details class="activity-help-details"><summary>Cómo se acredita</summary>'
            '<p class="activity-caption">Se requieren 3 de 4 ejercicios correctos, '
            'incluida la integradora.</p></details>'
        )

    ejemplos_node = (
        "Método y estado HTTP (ejemplo: GET, 200)",
        "Ruta y acceso al parámetro (ejemplo: /libros/:id, req.params.id)",
        "Validación y error antes de guardar (ejemplo: nombre obligatorio; 400; no crear)",
        "Crear y consultar (ejemplo: POST /productos 201; GET /productos 200)",
    )

    def montar_node(ejercicio, numero):
        gr.HTML(vistas.actividad_enunciado_html(ejercicio))
        return [gr.Textbox(lines=5, label=f"Respuesta Node.js · {ejercicio['id']}",
                           placeholder=ejemplos_node[numero])]

    preguntas_seg = []
    preguntas_seg_node = []

    def montar_seguimiento(item, numero):
        preguntas_seg.append(gr.Markdown(elem_classes=["activity-prompt"]))
        return [gr.Radio([], label=f"Respuesta {numero + 1}", elem_classes=["activity-options"])]

    def montar_seguimiento_node(item, numero):
        preguntas_seg_node.append(gr.Markdown(elem_classes=["activity-prompt"]))
        return [gr.Radio([], label=f"Respuesta Node.js {numero + 1}", elem_classes=["activity-options"])]

    with gr.Blocks(title="Rutas de aprendizaje · Proyecto Integrador") as demo:
        estado = gr.State(estado_inicial)

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
                inicio_html = vistas.inicio_html(
                    simulacion_activa=progreso_activo,
                    error_progreso=estado_inicial.get("error_progreso"),
                    meta=estado_inicial["perfil"]["meta"],
                    acreditados_meta=estado_inicial["completados"],
                    total_meta=len(_temas_pertinentes(motor, estado_inicial["perfil"]["meta"])),
                    completados_todos=estado_inicial["completados"],
                    siguiente=estado_inicial["recomendacion"].get("siguiente_tema"),
                    estado_meta=estado_inicial["recomendacion"].get("estado_meta", "En progreso"),
                    actividad_siguiente=None,
                    intentos=len(estado_inicial["intentos"]),
                )
                inicio_resumen = gr.HTML(inicio_html, elem_id="inicio-resumen")
                with gr.Row(elem_classes=["button-row"]):
                    iniciar = gr.Button(
                        "Continuar aprendizaje" if progreso_activo else "Iniciar simulación",
                        variant="primary",
                    )
                    reiniciar_simulacion = gr.Button("Reiniciar simulación", variant="stop")

            # ── Diagnóstico ────────────────────────────────────────────────
            with gr.Tab("Diagnóstico", id="diagnostico"):
                paso_diagnostico = gr.State(1)
                diag_encabezado = gr.HTML(
                    "<span class='step-label'>Paso 1 de 3</span><h2>¿Qué quieres aprender?</h2>"
                )
                with gr.Group(visible=True, elem_classes=["card"]) as diag_paso_1:
                    gr.HTML("<span class='eyebrow'>Paso 1</span><h3>Elige tu meta</h3>"
                            "<p class='small muted'>La meta define los temas pertinentes y el progreso que verás.</p>")
                    meta = gr.Dropdown(motor.temas, value=estado_inicial["perfil"]["meta"], label="Meta de aprendizaje")
                    meta_detalle = gr.HTML(_meta_detalle(motor, catalogo, estado_inicial["perfil"]["meta"], estado_inicial["completados"]))
                with gr.Group(visible=False, elem_classes=["card"]) as diag_paso_2:
                    gr.HTML("<span class='eyebrow'>Paso 2</span><h3>Preferencias de estudio</h3>")
                    with gr.Row():
                        nivel = gr.Radio(NIVELES, value=estado_inicial["perfil"]["nivel"], label="Nivel previo")
                        formato = gr.Radio(FORMATOS, value=estado_inicial["perfil"]["formato"], label="Formato preferido")
                    with gr.Accordion("Parámetros de simulación", open=False):
                        gr.HTML("<p class='small muted'>Estos valores describen el contexto simulado del estudiante.</p>")
                        tema_actual = gr.Dropdown(motor.temas, value=estado_inicial["perfil"]["tema"], label="Tema actual")
                        with gr.Row():
                            tiempo = gr.Slider(5, 300, value=estado_inicial["perfil"]["tiempo"], step=1, label="Tiempo de interacción (s)")
                            errores = gr.Slider(0, 100, value=estado_inicial["perfil"]["errores"], step=1, label="Tasa de errores (%)")
                        with gr.Row():
                            fallos = gr.Slider(0, 6, value=estado_inicial["perfil"]["fallos"], step=1, label="Fallos consecutivos")
                            abandono = gr.Checkbox(value=estado_inicial["perfil"]["abandono"], label="Abandonó la actividad")
                with gr.Group(visible=False, elem_classes=["card"]) as diag_paso_3:
                    gr.HTML("<span class='eyebrow'>Paso 3</span><h3>Qué conocimientos quieres evaluar</h3>")
                    acreditaciones_diag = gr.HTML(vistas.acreditaciones_html(estado_inicial["completados"]))
                    tema_evaluar = gr.Dropdown(motor.temas, value=estado_inicial["perfil"]["tema"], label="Tema que quieres evaluar")
                    disponibilidad_diag = gr.HTML(_disponibilidad(motor, estado_inicial["perfil"]["tema"], estado_inicial["completados"]))
                    with gr.Row(elem_classes=["button-row"]):
                        evaluar_tema = gr.Button("Evaluar este tema", variant="secondary")
                        generar_ruta_btn = gr.Button("Generar / actualizar mi ruta", variant="primary")
                with gr.Row(elem_classes=["button-row"]):
                    diag_anterior = gr.Button("Anterior", visible=False)
                    diag_siguiente = gr.Button("Siguiente", variant="primary")
                aviso_diag = gr.HTML()

            # ── Mi ruta ────────────────────────────────────────────────────
            with gr.Tab("Mi ruta", id="ruta"):
                vr = _vista_ruta(motor, catalogo, estado_inicial)
                ruta_cabecera = gr.HTML(vr[0])
                siguiente_paso = gr.HTML(vr[1])
                with gr.Row(elem_classes=["button-row"]):
                    abrir_siguiente = gr.Button("Iniciar actividad", variant="primary")
                    actualizar_ruta = gr.Button("Actualizar ruta")
                    cambiar_meta = gr.Button("Cambiar meta")
                with gr.Row(elem_classes=["route-layout"]):
                    with gr.Column(elem_classes=["route-main"]):
                        lista_pasos = gr.HTML(vr[2])
                    with gr.Column(elem_classes=["route-side"]):
                        grafo = gr.Plot(value=vr[3], label="Grafo de conocimiento")
                        tema_grafo = gr.Dropdown(motor.temas, value=estado_inicial["perfil"]["tema"], label="Explorar un tema del grafo")
                        tema_detalle = gr.HTML(vr[4])
                        ir_prerrequisito = gr.Button("Ir al prerrequisito")
                ruta_aviso = gr.HTML()
                tema_grafo_sel = vr[5]

            # ── Actividad ──────────────────────────────────────────────────
            with gr.Tab("Actividad", id="actividad", elem_id="activity-view"):
                gr.HTML(
                    "<header class='activity-lead'><span class='activity-eyebrow'>Catálogo de actividades</span>"
                    "<h2>Elige qué quieres practicar</h2>"
                    "<p class='activity-caption'>Selecciona una actividad y resuelve cada paso con el avance y la ayuda a la vista.</p></header>"
                )
                with gr.Accordion("Disponibilidad de actividades", open=True):
                    gr.HTML(catalogo_disponibilidad_html, elem_id="catalogo-disponibilidad")
                actividad_selector = gr.Radio(
                    [
                        "POO · clases y objetos",
                        "PostgreSQL · laboratorio",
                        "PostgreSQL · seguimiento",
                        "Backend con Node.js · laboratorio diagnóstico",
                        "Backend con Node.js · seguimiento",
                        "PHP MVC · laboratorio",
                        "PHP MVC · seguimiento",
                    ],
                    value=None, label="Actividad", elem_classes=["activity-catalog"],
                )
                instrucciones = gr.Markdown(elem_classes=["activity-instructions"])

                with gr.Group(visible=False, elem_classes=["activity-panel"]) as grupo_poo:
                    vista_poo = VistaActividad(
                        "Programación Orientada a Objetos", banco_poo["ejercicios"], montar_poo,
                        "Entregar práctica POO",
                        lambda item: gr.HTML(vistas.actividad_referencia_html({"modo": "poo"}, item)),
                    )
                    respuestas_poo, enviar_poo = vista_poo.respuestas, vista_poo.enviar

                with gr.Group(visible=False, elem_classes=["activity-panel"]) as grupo_laboratorio:
                    vista_sql = VistaActividad(
                        "Laboratorio PostgreSQL", ejercicios_lab, montar_sql,
                        "Calificar laboratorio", ayuda_sql,
                    )
                    respuestas_lab, enviar_lab = vista_sql.respuestas, vista_sql.enviar

                with gr.Group(visible=False, elem_classes=["activity-panel"]) as grupo_mvc:
                    vista_mvc = VistaActividad(
                        "Laboratorio MVC en PHP", ejercicios_mvc, montar_mvc,
                        "Calificar laboratorio MVC", ayuda_mvc,
                    )
                    respuestas_mvc, enviar_mvc = vista_mvc.respuestas, vista_mvc.enviar

                with gr.Group(visible=False, elem_classes=["activity-panel"]) as grupo_seguimiento:
                    vista_seg = VistaActividad(
                        "Actividad de seguimiento", list(range(5)), montar_seguimiento,
                        "Calificar seguimiento", seguimiento=True,
                    )
                    respuestas_seg, enviar_seg = vista_seg.respuestas, vista_seg.enviar

                with gr.Group(visible=False, elem_classes=["activity-panel"]) as grupo_laboratorio_node:
                    vista_node = VistaActividad(
                        "Laboratorio Node.js · 5 puntos", ejercicios_lab_node, montar_node,
                        "Calificar laboratorio Node.js",
                    )
                    respuestas_lab_node, enviar_lab_node = vista_node.respuestas, vista_node.enviar

                with gr.Group(visible=False, elem_classes=["activity-panel"]) as grupo_seguimiento_node:
                    vista_seg_node = VistaActividad(
                        "Seguimiento Node.js", list(range(5)), montar_seguimiento_node,
                        "Calificar seguimiento Node.js", seguimiento=True,
                    )
                    respuestas_seg_node, enviar_seg_node = vista_seg_node.respuestas, vista_seg_node.enviar

                vistas_actividad = [vista_poo, vista_sql, vista_mvc, vista_seg, vista_node, vista_seg_node]

            # ── Resultados ─────────────────────────────────────────────────
            with gr.Tab("Resultados", id="resultados"):
                resultado_principal = gr.HTML(
                    "<section class='empty-card'><span class='eyebrow'>Resultados</span>"
                    "<h2>Aún no hay resultados</h2><p class='muted'>Completa una actividad para revisar el puntaje, los criterios y su efecto en la ruta.</p></section>"
                )
                resultado_efecto = gr.HTML()
                with gr.Accordion("Revisión por pregunta o ejercicio", open=False):
                    resultado_revision = gr.HTML("<p class='muted small'>El detalle aparecerá después de calificar.</p>")
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

                gr.HTML(
                    "<div style='margin-top:16px'><h4>Explicación con IA</h4>"
                    f"<p class='muted small'>{estado_gemini()}</p>"
                    "<p class='muted small'>La calificación, el guardado y la ruta ya están listos; la explicación es un complemento.</p></div>"
                )
                pedir_ia = gr.Button(**_boton_ia(False))
                cargando_ia = gr.HTML(CARGANDO_IA_HTML, visible=False)
                explicacion_ia = gr.Markdown()

        # ── Callbacks ──────────────────────────────────────────────────────

        def abrir_inicio(estado_actual: dict[str, Any]):
            if not estado_actual.get("simulacion_activa"):
                return (gr.update(selected="diagnostico"), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
            vr = _vista_ruta(motor, catalogo, estado_actual)
            return (gr.update(selected="ruta"), vr[0], vr[1], vr[2], vr[3], vr[4], vr[5])

        iniciar.click(
            abrir_inicio, estado,
            [navegacion, ruta_cabecera, siguiente_paso, lista_pasos, grafo, tema_detalle, tema_grafo],
        )

        def reiniciar_desde_interfaz():
            simulacion.reiniciar()
            nuevo = _estado_inicial(motor)
            vr = _vista_ruta(motor, catalogo, nuevo)
            inicio_html = vistas.inicio_html(
                simulacion_activa=True, error_progreso=None, meta=nuevo["perfil"]["meta"],
                acreditados_meta=[], total_meta=1, completados_todos=[], siguiente=None,
                estado_meta="En progreso", actividad_siguiente=None, intentos=0,
            )
            return (
                nuevo, gr.update(selected="inicio"), inicio_html,
                vr[0], vr[1], vr[2], vr[3], vr[4], vr[5],
                gr.update(value="Iniciar simulación"),
                gr.update(value="Principiante"), gr.update(value="Visual"),
                gr.update(value=motor.temas[0]), gr.update(value="Backend con Node.js"),
                gr.update(value=120), gr.update(value=50), gr.update(value=0),
                gr.update(value=False),
                "<section class='empty-card'><span class='eyebrow'>Resultados</span>"
                "<h2>Aún no hay resultados</h2><p class='muted'>Completa una actividad para ver aquí el resumen.</p></section>",
                "", gr.update(**_boton_ia(False)), gr.update(visible=False),
            )

        reiniciar_simulacion.click(
            reiniciar_desde_interfaz,
            outputs=[estado, navegacion, inicio_resumen, ruta_cabecera, siguiente_paso,
                     lista_pasos, grafo, tema_detalle, tema_grafo,
                     iniciar, nivel, formato, tema_actual, meta, tiempo, errores,
                     fallos, abandono, resultado_principal, explicacion_ia, pedir_ia, cargando_ia],
        )

        meta.change(
            lambda m, s: _meta_detalle(motor, catalogo, m, s["completados"]),
            [meta, estado], meta_detalle,
        )
        tema_evaluar.change(
            lambda t, s: _disponibilidad(motor, t, s["completados"]),
            [tema_evaluar, estado], disponibilidad_diag,
        )

        def ir_a_diagnostico(estado_actual, paso: int = 1):
            return diag_render(paso, estado_actual["perfil"]["tema"], estado_actual)

        def diag_render(paso: int, tema_valor: str, estado_actual: dict[str, Any]):
            paso = max(1, min(3, int(paso)))
            titulos = {1: "¿Qué quieres aprender?", 2: "¿Cómo prefieres estudiar?", 3: "¿Qué conocimientos quieres evaluar?"}
            encabezado = f"<span class='step-label'>Paso {paso} de 3</span><h2>{titulos[paso]}</h2>"
            return (
                paso, gr.update(visible=paso == 1), gr.update(visible=paso == 2), gr.update(visible=paso == 3),
                encabezado, gr.update(visible=paso > 1), gr.update(visible=paso < 3),
                vistas.acreditaciones_html(estado_actual["completados"]),
                _disponibilidad(motor, tema_valor, estado_actual["completados"]),
            )

        diag_siguiente.click(
            lambda p, t, s: diag_render(int(p) + 1, t, s),
            [paso_diagnostico, tema_evaluar, estado],
            [paso_diagnostico, diag_paso_1, diag_paso_2, diag_paso_3, diag_encabezado, diag_anterior, diag_siguiente, acreditaciones_diag, disponibilidad_diag],
        )
        diag_anterior.click(
            lambda p, t, s: diag_render(int(p) - 1, t, s),
            [paso_diagnostico, tema_evaluar, estado],
            [paso_diagnostico, diag_paso_1, diag_paso_2, diag_paso_3, diag_encabezado, diag_anterior, diag_siguiente, acreditaciones_diag, disponibilidad_diag],
        )
        home_cambiar_meta = None  # no existe en esta versión; se usa cambiar_meta/elegir_meta desde resultados

        def generar_ruta(nivel_v, formato_v, tema_v, tiempo_v, errores_v, meta_v, fallos_v, abandono_v, estado_actual):
            perfil = {"nivel": nivel_v, "formato": formato_v, "tema": tema_v, "tiempo": tiempo_v,
                      "errores": errores_v, "meta": meta_v, "fallos": int(fallos_v), "abandono": bool(abandono_v)}
            try:
                guardado = _persistir_perfil(perfil)
            except (ErrorProgreso, ValueError) as exc:
                return (estado_actual, f"No se guardó el perfil: {exc}", gr.update(), gr.update(), gr.update(), gr.update())
            nuevo = dict(estado_actual)
            nuevo["perfil"] = perfil
            nuevo["completados"] = temas_acreditados(guardado)
            nuevo["intentos"] = guardado["intentos"]
            nuevo["simulacion_activa"] = True
            _actualizar_recomendacion(motor, nuevo)
            vr = _vista_ruta(motor, catalogo, nuevo)
            inicio_html = vistas.inicio_html(
                simulacion_activa=True, error_progreso=None, meta=meta_v,
                acreditados_meta=nuevo["completados"],
                total_meta=len(_temas_pertinentes(motor, meta_v)),
                completados_todos=nuevo["completados"], siguiente=nuevo["recomendacion"].get("siguiente_tema"),
                estado_meta=nuevo["recomendacion"].get("estado_meta", "En progreso"),
                actividad_siguiente=None, intentos=len(nuevo["intentos"]),
            )
            return (
                nuevo, inicio_html, vr[0], vr[1], vr[2], vr[3], vr[4], vr[5],
                f"Ruta actualizada. Siguiente tema: **{nuevo['recomendacion'].get('siguiente_tema') or 'Meta completada'}**.",
                f"Progreso local recuperado: {len(nuevo['intentos'])} intento(s), {len(nuevo['completados'])} tema(s) acreditado(s).",
                gr.update(value="Continuar aprendizaje"),
            )

        generar_ruta_btn.click(
            generar_ruta,
            [nivel, formato, tema_actual, tiempo, errores, meta, fallos, abandono, estado],
            [estado, inicio_resumen, ruta_cabecera, siguiente_paso, lista_pasos, grafo, tema_detalle, tema_grafo,
             aviso_diag, iniciar],
        )

        actualizar_ruta.click(
            lambda actual: _vista_ruta(motor, catalogo, actual),
            estado, [ruta_cabecera, siguiente_paso, lista_pasos, grafo, tema_detalle, tema_grafo],
        )

        def mostrar_tema(tema_v, estado_actual):
            return (
                vistas.tema_detalle_html(
                    tema_v, _estado_del_tema(motor, tema_v, estado_actual["completados"])[0],
                    [], [], _recursos_html(catalogo, tema_v, motor), "", "", es_siguiente=False,
                ),
                _dibujar_grafo(motor, estado_actual["completados"], tema_v),
            )

        tema_grafo.change(
            mostrar_tema, [tema_grafo, estado], [tema_detalle, grafo],
        )

        def seleccionar_actividad(seleccion, estado_actual):
            nuevo = dict(estado_actual)
            nuevo["tipo_actividad"] = seleccion
            nuevo["inicio_actividad"] = time.monotonic() if seleccion else None
            nuevo["variante_activa"] = None
            node_id = TEMA_A_NODO["Backend con Node.js"]
            node_prerrequisitos = [NODO_A_TEMA[n] for n in motor.grafo[node_id]["prerrequisitos"]
                                   if NODO_A_TEMA[n] not in nuevo["completados"]]
            node_followup_allowed = (
                seleccion == "Backend con Node.js · seguimiento" and not node_prerrequisitos
            )
            visibilidad = [
                gr.update(visible=seleccion == "POO · clases y objetos"),
                gr.update(visible=seleccion == "PostgreSQL · laboratorio"),
                gr.update(visible=seleccion == "PHP MVC · laboratorio"),
                gr.update(visible=seleccion in SEGUIMIENTOS),
                gr.update(visible=seleccion == "Backend con Node.js · laboratorio diagnóstico"),
                gr.update(visible=node_followup_allowed),
            ]
            prompts = [gr.update(value="") for _ in range(5)]
            radios = [gr.update(choices=[], value=None) for _ in range(5)]
            prompts_node = [gr.update(value="") for _ in range(5)]
            radios_node = [gr.update(choices=[], value=None) for _ in range(5)]
            instruccion = "Selecciona una actividad para mostrar sus ejercicios."
            if seleccion == "POO · clases y objetos":
                instruccion = "Responde los cuatro ejercicios. La entrega se acompaña de una lista de revisión, no de una nota automática."
            elif seleccion == "PostgreSQL · laboratorio":
                instruccion = "Resuelve los cuatro ejercicios SQL. El calificador verificará los resultados y la regla de acreditación."
            elif seleccion == "PHP MVC · laboratorio":
                instruccion = ("Resuelve los cuatro ejercicios de MVC eligiendo una opción en cada criterio. "
                               "Se acredita con 3 de 4 ejercicios correctos, incluida la integradora.")
            elif seleccion in SEGUIMIENTOS:
                obtener_variante, _ = SEGUIMIENTOS[seleccion]
                try:
                    variante, preguntas = obtener_variante(nuevo["variantes_usadas"])
                except ValueError as exc:
                    instruccion = f"**No se puede iniciar el seguimiento:** {exc}"
                else:
                    nuevo["variante_activa"] = variante
                    for indice, pregunta in enumerate(preguntas):
                        prompts[indice] = gr.update(value=f"**{pregunta['id']} · {pregunta['concepto']}**\n\n{pregunta['enunciado']}")
                        radios[indice] = gr.update(choices=pregunta["opciones"], value=None)
                    instruccion = f"Variante asignada: **{variante}**."
            elif seleccion == "Backend con Node.js · laboratorio diagnóstico":
                instruccion = "Resuelve los cuatro ejercicios. Se acredita con al menos 4/5 puntos."
            elif seleccion == "Backend con Node.js · seguimiento":
                if node_prerrequisitos:
                    instruccion = f"Actividad bloqueada. Primero acredita: {', '.join(node_prerrequisitos)}."
                else:
                    try:
                        variante, preguntas = obtener_variante_seguimiento_node(nuevo["variantes_usadas"])
                    except ValueError as exc:
                        instruccion = f"**No se puede iniciar el seguimiento:** {exc}"
                    else:
                        nuevo["variante_activa"] = variante
                        for indice, pregunta in enumerate(preguntas):
                            prompts_node[indice] = gr.update(value=f"**{pregunta['id']} · {pregunta['concepto']}**\n\n{pregunta['pregunta']}")
                            radios_node[indice] = gr.update(choices=[pregunta["respuesta"]] + ["Opción A", "Opción B", "Opción C"], value=None)
                        instruccion = f"Variante asignada: **{variante}**."
            return (
                *visibilidad, *prompts, *radios, *prompts_node, *radios_node,
                instruccion, nuevo,
            )

        seleccion_outputs = [
            grupo_poo, grupo_laboratorio, grupo_mvc, grupo_seguimiento,
            grupo_laboratorio_node, grupo_seguimiento_node,
            *preguntas_seg, *respuestas_seg,
            *preguntas_seg_node, *respuestas_seg_node,
            instrucciones, estado,
        ]
        tipo_actividad = actividad_selector

        def reiniciar_navegacion_actividades(*valores):
            actualizaciones = []
            inicio = 0
            for vista in vistas_actividad:
                fin = inicio + len(vista.respuestas)
                actualizaciones.extend(vista.reiniciar_navegacion(*valores[inicio:fin]))
                inicio = fin
            return tuple(actualizaciones)

        tipo_actividad.change(
            seleccionar_actividad, [tipo_actividad, estado], seleccion_outputs,
        ).then(
            reiniciar_navegacion_actividades,
            [control for vista in vistas_actividad for control in vista.respuestas],
            [salida for vista in vistas_actividad for salida in vista.salidas],
            show_progress="hidden",
        )

        def registrar_resultado(resultado, estado_actual):
            try:
                if resultado.get("tipo") == "poo":
                    persistible = {
                        "id": str(uuid4()), "tema": "Programación Orientada a Objetos",
                        "tipo_actividad": "Práctica POO", "puntaje": resultado["respondidos"],
                        "puntaje_maximo": resultado["total"], "tiempo_segundos": 0,
                        "conceptos_con_error": [], "aprobado": False,
                        "detalle": resultado.get("detalle", []),
                    }
                else:
                    persistible = normalizar_resultado_calificador(resultado)
                guardado = simulacion.persistir_intento(persistible)
            except (ErrorProgreso, ValueError, TypeError, OverflowError) as exc:
                vr = _vista_ruta(motor, catalogo, estado_actual)
                return (
                    estado_actual, f"## No se guardó el resultado\n\n{exc}",
                    vr[0], vr[1], vr[2], vr[3], vr[4], vr[5],
                    gr.update(selected="resultados"), gr.update(), gr.update(), gr.update(), gr.update(),
                )
            retroalimentacion = _retroalimentacion_local(resultado, estado_actual["perfil"].get("formato"))
            nuevo = dict(estado_actual)
            nuevo["completados"] = temas_acreditados(guardado)
            nuevo["intentos"] = guardado["intentos"]
            nuevo["variantes_usadas"] = [i["variante"] for i in guardado["intentos"] if i.get("variante")]
            nuevo["simulacion_activa"] = guardado["simulacion_activa"]
            nuevo["resultado"] = resultado
            _actualizar_recomendacion(motor, nuevo)
            vr = _vista_ruta(motor, catalogo, nuevo)
            principal, efecto, revision, retro, recurso = _resultado_markdown(resultado, retroalimentacion, motor, catalogo)
            return (
                nuevo, principal, efecto, revision, retro, recurso,
                vr[0], vr[1], vr[2], vr[3], vr[4], vr[5],
                gr.update(selected="resultados"),
                "", gr.update(**_boton_ia(resultado.get("tipo") != "poo")), gr.update(visible=False),
            )

        def entregar_poo(*valores):
            estado_actual = valores[-1]
            respuestas = [str(r or "").strip() for r in valores[:-1]]
            resultado = {
                "tipo": "poo", "tema": "Programación Orientada a Objetos",
                "respondidos": sum(bool(r) for r in respuestas), "total": len(respuestas),
                "acreditado": False,
                "detalle": [{"id": f"POO-{i + 1:02d}", "respuesta": r} for i, r in enumerate(respuestas)],
            }
            return registrar_resultado(resultado, estado_actual)

        def calificar_lab(*valores):
            estado_actual = valores[-1]
            respuestas = {e["id"]: r or "" for e, r in zip(ejercicios_lab, valores[:-1])}
            inicio = estado_actual.get("inicio_actividad") or time.monotonic()
            resultado = calificar_laboratorio(respuestas, tiempo=max(0.0, time.monotonic() - inicio))
            resultado["respuestas"] = respuestas
            return registrar_resultado(resultado, estado_actual)

        def calificar_lab_mvc(*valores):
            estado_actual = valores[-1]
            respuestas = {c: r or "" for c, r in zip(criterios_mvc, valores[:-1])}
            inicio = estado_actual.get("inicio_actividad") or time.monotonic()
            resultado = calificar_laboratorio_mvc(respuestas, tiempo=max(0.0, time.monotonic() - inicio))
            resultado["respuestas"] = respuestas
            return registrar_resultado(resultado, estado_actual)

        def calificar_seg(*valores):
            estado_actual = valores[-1]
            variante = estado_actual.get("variante_activa")
            seleccion = estado_actual.get("tipo_actividad")
            if not variante or seleccion not in SEGUIMIENTOS:
                raise ValueError("Selecciona una variante de seguimiento antes de calificar.")
            obtener_variante, calificar = SEGUIMIENTOS[seleccion]
            variante_actual, preguntas = obtener_variante(estado_actual["variantes_usadas"])
            if variante_actual != variante:
                raise ValueError("La variante activa no coincide.")
            respuestas = {p["id"]: r or "" for p, r in zip(preguntas, valores[:-1])}
            resultado = calificar(respuestas, tiempo=max(0.0, time.monotonic() - (estado_actual.get("inicio_actividad") or time.monotonic())), variante_usada=variante)
            resultado["respuestas"] = respuestas
            nuevo = dict(estado_actual)
            nuevo["variantes_usadas"] = list(nuevo["variantes_usadas"]) + [variante]
            return registrar_resultado(resultado, nuevo)

        def calificar_lab_node(*valores):
            estado_actual = valores[-1]
            respuestas = {e["id"]: r or "" for e, r in zip(ejercicios_lab_node, valores[:-1])}
            inicio = estado_actual.get("inicio_actividad") or time.monotonic()
            resultado = calificar_laboratorio_node(respuestas, tiempo_segundos=max(0.0, time.monotonic() - inicio))
            return registrar_resultado(resultado, estado_actual)

        def calificar_seg_node(*valores):
            estado_actual = valores[-1]
            variante = estado_actual.get("variante_activa")
            if not variante:
                raise ValueError("Selecciona una variante de seguimiento Node.js.")
            variante_actual, preguntas = obtener_variante_seguimiento_node(estado_actual["variantes_usadas"])
            if variante_actual != variante:
                raise ValueError("La variante activa Node.js no coincide.")
            faltantes = [NODO_A_TEMA[r] for r in motor.grafo[TEMA_A_NODO["Backend con Node.js"]]["prerrequisitos"]
                         if NODO_A_TEMA[r] not in estado_actual["completados"]]
            if faltantes:
                raise ValueError("Backend con Node.js sigue bloqueado.")
            respuestas = {p["id"]: r or "" for p, r in zip(preguntas, valores[:-1])}
            resultado = calificar_seguimiento_node(respuestas, tiempo_segundos=max(0.0, time.monotonic() - (estado_actual.get("inicio_actividad") or time.monotonic())), variante=variante)
            return registrar_resultado(resultado, estado_actual)

        resultado_outputs = [
            estado, resultado_principal, resultado_efecto, resultado_revision,
            resultado_retro, resultado_recurso,
            ruta_cabecera, siguiente_paso, lista_pasos, grafo, tema_detalle, tema_grafo,
            navegacion, explicacion_ia, pedir_ia, cargando_ia,
        ]
        enviar_mvc.click(calificar_lab_mvc, [*respuestas_mvc, estado], resultado_outputs)
        enviar_poo.click(entregar_poo, [*respuestas_poo, estado], resultado_outputs)
        enviar_lab.click(calificar_lab, [*respuestas_lab, estado], resultado_outputs)
        enviar_seg.click(calificar_seg, [*respuestas_seg, estado], resultado_outputs)
        enviar_lab_node.click(calificar_lab_node, [*respuestas_lab_node, estado], resultado_outputs)
        enviar_seg_node.click(calificar_seg_node, [*respuestas_seg_node, estado], resultado_outputs)

        def mostrar_cargando_ia():
            return (gr.update(**_boton_ia(False, "Generando explicación…")), gr.update(visible=True), "")

        def pedir_explicacion(estado_actual):
            resultado = estado_actual.get("resultado")
            if not resultado:
                return ("Primero completa una actividad calificada.", gr.update(**_boton_ia(False)), gr.update(visible=False))
            if resultado.get("tipo") == "poo":
                return ("La práctica de POO no tiene calificación automática.", gr.update(**_boton_ia(False)), gr.update(visible=False))
            try:
                explicacion = solicitar_explicacion(resultado, estado_actual["perfil"].get("formato"))
            except Exception as exc:
                return (f"No se pudo generar la explicación: {exc}", gr.update(**_boton_ia(True, "Reintentar explicación con IA (Gemini)")), gr.update(visible=False))
            if explicacion.get("origen") == "gemini":
                boton = _boton_ia(False, "Explicación con IA generada")
            else:
                boton = _boton_ia(True, "Reintentar explicación con IA (Gemini)")
            return (renderizar_retroalimentacion(explicacion), gr.update(**boton), gr.update(visible=False))

        pedir_ia.click(mostrar_cargando_ia, outputs=[pedir_ia, cargando_ia, explicacion_ia], queue=False, show_progress="hidden", trigger_mode="once").then(
            pedir_explicacion, inputs=estado, outputs=[explicacion_ia, pedir_ia, cargando_ia], show_progress="hidden", concurrency_limit=1,
        )

        volver_ruta.click(lambda: gr.update(selected="ruta"), outputs=navegacion)
        otra_actividad.click(lambda: (gr.update(selected="actividad"), gr.update(value=None)), outputs=[navegacion, tipo_actividad])
        continuar_siguiente.click(
            lambda actual: (
                siguiente := actual["recomendacion"].get("siguiente_tema"),
                gr.update(selected="actividad") if siguiente else gr.update(selected="ruta"),
                gr.update(value=None),
            )[1:],
            estado, [navegacion, tipo_actividad],
        )

    return demo
