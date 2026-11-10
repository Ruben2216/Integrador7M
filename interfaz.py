"""Interfaz Gradio del recomendador, niveles formativos y ruta visual."""
from __future__ import annotations

import json
import os
import time
from typing import Any

import gradio as gr

from calificador import (
    calificar_laboratorio,
    obtener_ejercicios_laboratorio,
)
from calificador_mvc import (
    calificar_laboratorio_mvc,
    obtener_conceptos_mvc,
    obtener_ejercicios_laboratorio_mvc,
)
from calificador_logica import (
    calificar_laboratorio_logica,
    obtener_conceptos_logica,
    obtener_ejercicios_laboratorio_logica,
)
from calificador_node import (
    calificar_laboratorio_node,
    obtener_ejercicios_laboratorio_node,
)
from integracion_calificador import normalizar_resultado_calificador
from progreso import (ErrorProgreso, ETAPAS, NOMBRES_ETAPAS,
                      siguiente_etapa, temas_acreditados)
from niveles import calificar_nivel, preguntas_nivel
from calificador_poo import calificar_laboratorio_poo
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
from ui.resultados import (renderizar_retroalimentacion, solicitud_explicacion_html,
                           error_explicacion_html)
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
    return {
        "perfil": profile,
        "completados": completados,
        "recomendacion": motor.consultar(**profile, completados=completados),
        "tipo_actividad": None,
        "inicio_actividad": None,
        "resultado": None,
        "simulacion_activa": guardado["simulacion_activa"],
        "intentos": guardado["intentos"],
        "acreditaciones": guardado["temas_acreditados"],
        "etapa_activa": None,
        "error_progreso": error_progreso,
    }


# ── Consultas al grafo y catálogo ───────────────────────────────────────────
def _estado_del_tema(motor: Any, tema: str, completados: list[str], intentos=None) -> tuple[str, list[str]]:
    nodo = TEMA_A_NODO[tema]
    if tema in completados:
        return "Acreditado", []
    faltantes = [
        NODO_A_TEMA[pre] for pre in motor.grafo[nodo]["prerrequisitos"]
        if NODO_A_TEMA[pre] not in completados
    ]
    if faltantes:
        return "Bloqueado", faltantes
    if any(i.get("tema") == tema and i.get("etapa") in ETAPAS and i.get("aprobado")
           for i in (intentos or [])):
        return "En progreso", []
    return "Disponible", []


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
        "Programación Orientada a Objetos": ("Tres niveles y práctica de código Python", "La práctica se califica por estructura sin ejecutar el código."),
        "Bases de Datos PostgreSQL": ("Tres niveles y laboratorio SQL", "Cada nivel requiere 4/5; después se abre el laboratorio."),
        "Backend con Node.js": ("Tres niveles y laboratorio Node.js", "Cada nivel requiere 4/5; después se abre el laboratorio."),
        "Lógica de Programación": ("Tres niveles y práctica integradora", "Cada nivel requiere 4/5; después se abre la práctica."),
        "Patrón MVC en PHP": ("Tres niveles y práctica integradora", "Cada nivel requiere 4/5; después se abre la práctica."),
    }.get(tema, ("Evaluación no disponible", "Sin actividad conectada."))
    return vistas.disponibilidad_html(tema, estado, faltantes, info[0], info[1])


# ── Grafo ───────────────────────────────────────────────────────────────────
def _dibujar_grafo(motor: Any, completados: list[str], seleccionado: str | None,
                  intentos=None, acreditaciones=None, ruta=()):
    from matplotlib.figure import Figure
    from matplotlib.patches import FancyBboxPatch, Patch

    # Las posiciones reflejan las cinco dependencias reales, sin empalmar etiquetas.
    posiciones = {
        "Logica_de_Programacion": (0, 0),
        "Programacion_Orientada_a_Objetos": (1.15, .76),
        "Bases_de_Datos_PostgreSQL": (1.15, -.76),
        "Backend_con_Nodejs": (2.3, -.76),
        "Patron_MVC_en_PHP": (2.3, .76),
    }
    nombres = {
        "Logica_de_Programacion": "Lógica",
        "Programacion_Orientada_a_Objetos": "POO",
        "Bases_de_Datos_PostgreSQL": "PostgreSQL",
        "Backend_con_Nodejs": "Node.js",
        "Patron_MVC_en_PHP": "MVC en PHP",
    }
    colores = {"Acreditado": "#4ADE80", "En progreso": "#FBBF24",
               "Disponible": "#7DD3FC", "Bloqueado": "#64748B"}
    ruta_nodos = {TEMA_A_NODO[t] for t in ruta if t in TEMA_A_NODO}
    fig = Figure(figsize=(8.5, 4.6), dpi=115)
    ax = fig.subplots()
    fig.patch.set_facecolor("#0C131E")
    ax.set_facecolor("#0C131E")
    for origen, destino in motor._rec.aristas:
        x1, y1 = posiciones[origen]
        x2, y2 = posiciones[destino]
        destacada = destino in ruta_nodos and (origen in ruta_nodos or NODO_A_TEMA[origen] in completados)
        ax.annotate("", xy=(x2 - .35, y2), xytext=(x1 + .35, y1),
                    arrowprops={"arrowstyle": "-|>", "color": "#79D8C1" if destacada else "#536A7F",
                                "lw": 2.4 if destacada else 1.6, "mutation_scale": 14})
    for nodo in motor.grafo:
        tema = NODO_A_TEMA[nodo]
        x, y = posiciones[nodo]
        estado, _ = _estado_del_tema(motor, tema, completados, intentos)
        color = colores[estado]
        legado = bool((acreditaciones or {}).get(tema, {}).get("legado"))
        etapas = len({i.get("etapa") for i in (intentos or [])
                      if i.get("tema") == tema and i.get("aprobado") and i.get("etapa") in ETAPAS})
        avance = "Acreditado previo" if legado else f"{etapas}/4 etapas"
        caja = FancyBboxPatch((x - .34, y - .25), .68, .5,
                               boxstyle="round,pad=0.03,rounding_size=0.08",
                               linewidth=2.5 if tema == seleccionado else 1.5,
                               edgecolor="#79D8C1" if tema == seleccionado else color,
                               facecolor="#142535")
        ax.add_patch(caja)
        ax.text(x, y + .08, nombres[nodo], ha="center", va="center",
                color="#F1F5F9", fontsize=10, fontweight="bold")
        ax.text(x, y - .10, avance, ha="center", va="center",
                color=color, fontsize=8)
    ax.set_xlim(-.48, 2.78)
    ax.set_ylim(-1.37, 1.37)
    ax.set_aspect(.65)
    ax.legend(handles=[Patch(facecolor=color, label=estado) for estado, color in colores.items()],
              loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(.5, -.04),
              labelcolor="#B8C5D6", fontsize=8)
    ax.set_title("Ruta de aprendizaje · borde turquesa: tema seleccionado",
                 color="#B8C5D6", fontsize=10)
    ax.set_axis_off()
    fig.tight_layout()
    return fig


def _detalle_etapas(estado: dict[str, Any], tema: str) -> str:
    aprobadas = {i.get("etapa") for i in estado["intentos"]
                 if i.get("tema") == tema and i.get("aprobado") and i.get("etapa") in ETAPAS}
    legado = estado.get("acreditaciones", {}).get(tema, {}).get("legado")
    actual = next((paso for paso in ETAPAS if paso not in aprobadas), None)
    filas = "".join(
        f'<li><span class="step-index">{numero}</span><span class="step-title">{NOMBRES_ETAPAS[paso]}</span>'
        f'<span class="{"status-ok" if paso in aprobadas else "status-info" if paso == actual and not legado else "status-neutral"}">'
        f'{"Aprobada" if paso in aprobadas else "Sin registro" if legado else "Siguiente" if paso == actual else "Pendiente"}</span></li>'
        for numero, paso in enumerate(ETAPAS, 1)
    )
    nota = ('<p class="small muted">Acreditación anterior conservada. No se atribuyen niveles que no constan en el historial.</p>'
            if legado else '<p class="small muted">Cada nivel requiere 4 de 5 aciertos. La práctica final usa su rúbrica propia.</p>')
    if tema == "Programación Orientada a Objetos":
        nota += '<p class="small muted">La práctica POO se revisa por estructura; no se ejecuta el código.</p>'
    return f'<section class="card"><h3>Etapas del tema</h3><ol class="steps">{filas}</ol>{nota}</section>'


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

    estados = {t: _estado_del_tema(motor, t, completados, estado["intentos"]) for t in temas}
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
    figura = _dibujar_grafo(motor, completados, seleccionado, estado["intentos"],
                           estado.get("acreditaciones"), ruta)
    detalle = vistas.tema_detalle_html(
        seleccionado, estados[seleccionado][0],
        [NODO_A_TEMA[n] for n in motor.grafo[TEMA_A_NODO[seleccionado]]["prerrequisitos"]],
        [t for t in [NODO_A_TEMA[n] for n in motor.grafo[TEMA_A_NODO[seleccionado]]["prerrequisitos"]] if t not in completados],
        _recursos_html(catalogo, seleccionado, motor),
        "Consulta Mi ruta", "", es_siguiente=True,
    )
    detalle += _detalle_etapas(estado, seleccionado)
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
    "Lógica de Programación · niveles": "Lógica de Programación",
    "POO · niveles": "Programación Orientada a Objetos",
    "PostgreSQL · niveles": "Bases de Datos PostgreSQL",
    "Backend con Node.js · niveles": "Backend con Node.js",
    "PHP MVC · niveles": "Patrón MVC en PHP",
}
LABORATORIOS = {
    "Lógica de Programación · práctica integradora": "Lógica de Programación",
    "POO · práctica integradora": "Programación Orientada a Objetos",
    "PostgreSQL · práctica integradora": "Bases de Datos PostgreSQL",
    "Backend con Node.js · práctica integradora": "Backend con Node.js",
    "PHP MVC · práctica integradora": "Patrón MVC en PHP",
}


def _seleccion_para_tema(estado: dict[str, Any], tema: str | None) -> str | None:
    if not tema:
        return None
    etapa = siguiente_etapa({"intentos": estado["intentos"],
                            "temas_acreditados": estado.get("acreditaciones", {})}, tema)
    opciones = SEGUIMIENTOS if etapa in ETAPAS[:3] else LABORATORIOS if etapa == "integradora" else {}
    return next((etiqueta for etiqueta, destino in opciones.items() if destino == tema), None)

GEMINI_ACTIVO = cargar_config().disponible
TEXTO_BOTON_IA = "Pedir explicación con IA"
CARGANDO_IA_HTML = (
    '<div class="feedback-loading" role="status" aria-live="polite">'
    '<svg width="20" height="20" viewBox="0 0 50 50" aria-hidden="true">'
    '<circle cx="25" cy="25" r="20" fill="none" stroke="#2B3A50" stroke-width="4"/>'
    '<circle cx="25" cy="25" r="20" fill="none" stroke="#5EEAD4" stroke-width="4" '
    'stroke-linecap="round" stroke-dasharray="80 126">'
    '<animateTransform attributeName="transform" type="rotate" from="0 25 25" '
    'to="360 25 25" dur="0.9s" repeatCount="indefinite"/></circle></svg>'
    '<span>Preparando tu explicación…</span></div>'
)


def _boton_ia(habilitado: bool, texto: str = TEXTO_BOTON_IA) -> dict[str, Any]:
    if not GEMINI_ACTIVO:
        return {"value": "Explicación con IA no disponible",
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
    etapa_aprobada = resultado["acreditado"]
    estado = resultado.get("_estado", {})
    acreditado = tema in estado.get("completados", [])
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

    estado_texto = ("Tema acreditado" if acreditado else
                    "Etapa aprobada · tema pendiente" if etapa_aprobada else "Etapa pendiente")
    etapa_nombre = NOMBRES_ETAPAS.get(resultado.get("etapa"), "Diagnóstico")
    principal = (
        '<section class="result-card">'
        '<span class="eyebrow">Resultado verificado</span>'
        f"<h2>{tema}</h2>"
        f'<p class="muted small">{vistas.e(etapa_nombre)}</p>'
        f'<div class="score-line"><b>{correctas} / {total}</b><span class="muted">aciertos o puntos</span>'
        f'• {estado_texto}</div>'
        '<div class="entity-grid" style="margin-top:14px">'
        f'<div><h3>Qué hiciste bien</h3><ul class="criteria-list">{bien_html}</ul></div>'
        f'<div><h3>Qué debes reforzar</h3><ul class="criteria-list">{ref_html}</ul></div>'
        '</div></section>'
    )

    rec = estado.get("recomendacion")
    siguiente = rec.get("siguiente_tema") if rec else None
    efecto = (
        f'<section class="route-card"><span class="eyebrow">Cómo afecta tu ruta</span>'
        f"<h3>{'Tema acreditado · ruta actualizada' if acreditado else 'Etapa aprobada · continúa el tema' if etapa_aprobada else 'Etapa pendiente'}</h3>"
        f'<p><b>Siguiente paso:</b> {siguiente or "revisa Mi ruta"}.</p>'
        '<p class="muted small">El tema se acredita al aprobar las tres etapas y la práctica final.</p></section>'
    )
    revision = vistas.resultado_revision_html(resultado, {})
    retro = renderizar_retroalimentacion(retroalimentacion)
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
    ejercicios_lab_logica = obtener_ejercicios_laboratorio_logica()
    conceptos_logica = obtener_conceptos_logica()
    estado_inicial = _estado_inicial(motor)
    progreso_activo = estado_inicial["simulacion_activa"]

    # ── Disponibilidad de actividades (catálogo visual) ─────────────────
    _ACTIVIDADES_POR_TEMA = {
        tema: "Básico · Intermedio · Avanzado · práctica integradora"
        for tema in motor.temas
    }
    estados_actividad = {
        tema: _estado_del_tema(motor, tema, estado_inicial["completados"], estado_inicial["intentos"])
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
        return [gr.Textbox(lines=10, label=f"Código Python {ejercicio['id']}",
                           elem_classes=["activity-editor"])]

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

    criterios_logica: list[str] = []

    def montar_logica(ejercicio, numero):
        gr.HTML(vistas.actividad_enunciado_html(
            ejercicio, conceptos_logica.get(ejercicio["concepto"], ejercicio["concepto"])
        ))
        if ejercicio.get("codigo"):
            gr.HTML(vistas.actividad_codigo_html(ejercicio["codigo"]))
        controles = []
        for criterio in ejercicio["criterios"]:
            with gr.Group(elem_classes=["activity-criterion"]):
                criterios_logica.append(criterio["id"])
                controles.append(gr.Radio(
                    criterio["opciones"], label=criterio["pregunta"], value=None,
                    elem_classes=["activity-options"],
                ))
        return controles

    def ayuda_logica(ejercicio):
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

    def montar_seguimiento(item, numero):
        preguntas_seg.append(gr.Markdown(elem_classes=["activity-prompt"]))
        return [gr.Radio([], label=f"Respuesta {numero + 1}", show_label=False, elem_classes=["activity-options"])]

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
                with gr.Group(elem_classes=["graph-scroll"]):
                    grafo = gr.Plot(value=vr[3], label="Grafo de conocimiento", elem_id="learning-graph")
                with gr.Row(elem_classes=["route-layout"]):
                    with gr.Column(elem_classes=["route-main"]):
                        lista_pasos = gr.HTML(vr[2])
                    with gr.Column(elem_classes=["route-side"]):
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
                        *SEGUIMIENTOS,
                        *LABORATORIOS,
                    ],
                    value=None, label="Actividad", elem_classes=["activity-catalog"],
                )
                instrucciones = gr.Markdown(elem_classes=["activity-instructions"])

                with gr.Group(visible=False, elem_classes=["activity-panel"]) as grupo_logica:
                    vista_logica = VistaActividad(
                        "Laboratorio Lógica de Programación", ejercicios_lab_logica, montar_logica,
                        "Calificar laboratorio Lógica", ayuda_logica,
                    )
                    respuestas_logica, enviar_logica = vista_logica.respuestas, vista_logica.enviar

                with gr.Group(visible=False, elem_classes=["activity-panel"]) as grupo_poo:
                    vista_poo = VistaActividad(
                        "Programación Orientada a Objetos", banco_poo["ejercicios"], montar_poo,
                        "Calificar práctica POO",
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
                        "Niveles de aprendizaje", list(range(5)), montar_seguimiento,
                        "Calificar nivel", seguimiento=True,
                    )
                    respuestas_seg, enviar_seg = vista_seg.respuestas, vista_seg.enviar

                with gr.Group(visible=False, elem_classes=["activity-panel"]) as grupo_laboratorio_node:
                    vista_node = VistaActividad(
                        "Laboratorio Node.js · 5 puntos", ejercicios_lab_node, montar_node,
                        "Calificar laboratorio Node.js",
                    )
                    respuestas_lab_node, enviar_lab_node = vista_node.respuestas, vista_node.enviar

                vistas_actividad = [vista_logica, vista_poo, vista_sql, vista_mvc, vista_seg, vista_node]

            # ── Resultados ─────────────────────────────────────────────────
            with gr.Tab("Resultados", id="resultados"):
                resultado_principal = gr.HTML(
                    "<section class='empty-card'><span class='eyebrow'>Resultados</span>"
                    "<h2>Aún no hay resultados</h2><p class='muted'>Completa una actividad para revisar el puntaje, los criterios y su efecto en la ruta.</p></section>"
                )
                resultado_efecto = gr.HTML()
                with gr.Accordion("Revisión por pregunta o ejercicio", open=False):
                    resultado_revision = gr.HTML("<p class='muted small'>El detalle aparecerá después de calificar.</p>")
                resultado_recurso = gr.HTML()
                with gr.Row(elem_classes=["button-row"]):
                    reintentar = gr.Button("Volver a la actividad")
                    otra_actividad = gr.Button("Elegir otra actividad")
                    volver_ruta = gr.Button("Volver a Mi ruta", variant="primary")
                with gr.Row(elem_classes=["button-row"]):
                    volver_diagnostico = gr.Button("Volver al diagnóstico")
                    continuar_siguiente = gr.Button("Continuar con el siguiente tema")
                    elegir_meta = gr.Button("Elegir otra meta", visible=False)

                with gr.Column(elem_id="feedback-view", min_width=0):
                    resultado_retro = gr.HTML(elem_id="feedback-local")
                    explicacion_ia = gr.HTML(elem_id="feedback-ai")
                    with gr.Column(elem_id="feedback-request", min_width=0):
                        gr.HTML(solicitud_explicacion_html(estado_gemini()))
                        with gr.Row(elem_classes=["feedback-actions"]):
                            pedir_ia = gr.Button(**_boton_ia(False), variant="secondary")
                        cargando_ia = gr.HTML(CARGANDO_IA_HTML, visible=False)

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
            nuevo["acreditaciones"] = guardado["temas_acreditados"]
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
            estado_tema, faltantes = _estado_del_tema(
                motor, tema_v, estado_actual["completados"], estado_actual["intentos"])
            return (
                vistas.tema_detalle_html(
                    tema_v, estado_tema,
                    [NODO_A_TEMA[n] for n in motor.grafo[TEMA_A_NODO[tema_v]]["prerrequisitos"]],
                    faltantes, _recursos_html(catalogo, tema_v, motor), "", "", es_siguiente=False,
                ) + _detalle_etapas(estado_actual, tema_v),
                _dibujar_grafo(motor, estado_actual["completados"], tema_v,
                               estado_actual["intentos"], estado_actual.get("acreditaciones"),
                               estado_actual["recomendacion"].get("ruta_pendiente", [])),
            )

        tema_grafo.change(
            mostrar_tema, [tema_grafo, estado], [tema_detalle, grafo],
        )

        def seleccionar_actividad(seleccion, estado_actual):
            nuevo = dict(estado_actual)
            nuevo["tipo_actividad"] = seleccion
            nuevo["inicio_actividad"] = time.monotonic() if seleccion else None
            nuevo["etapa_activa"] = None
            tema_seleccionado = SEGUIMIENTOS.get(seleccion) or LABORATORIOS.get(seleccion)
            faltantes = []
            if tema_seleccionado:
                faltantes = [NODO_A_TEMA[n] for n in motor.grafo[TEMA_A_NODO[tema_seleccionado]]["prerrequisitos"]
                             if NODO_A_TEMA[n] not in nuevo["completados"]]
            guardado = {"intentos": nuevo["intentos"], "temas_acreditados": nuevo.get("acreditaciones", {})}
            etapa = siguiente_etapa(guardado, tema_seleccionado) if tema_seleccionado else None
            nivel_visible = seleccion in SEGUIMIENTOS and etapa in ETAPAS[:3] and not faltantes
            practica_visible = seleccion in LABORATORIOS and etapa == "integradora" and not faltantes
            visibilidad = [
                gr.update(visible=practica_visible and tema_seleccionado == "Lógica de Programación"),
                gr.update(visible=practica_visible and tema_seleccionado == "Programación Orientada a Objetos"),
                gr.update(visible=practica_visible and tema_seleccionado == "Bases de Datos PostgreSQL"),
                gr.update(visible=practica_visible and tema_seleccionado == "Patrón MVC en PHP"),
                gr.update(visible=nivel_visible),
                gr.update(visible=practica_visible and tema_seleccionado == "Backend con Node.js"),
            ]
            prompts = [gr.update(value="") for _ in range(5)]
            radios = [gr.update(choices=[], value=None) for _ in range(5)]
            instruccion = "Selecciona una actividad para mostrar sus ejercicios."
            if faltantes:
                instruccion = f"Primero acredita: {', '.join(faltantes)}."
            elif tema_seleccionado and etapa is None:
                instruccion = "Este tema ya está acreditado. Puedes consultar su avance en Mi ruta."
            elif nivel_visible:
                nuevo["etapa_activa"] = etapa
                for indice, pregunta in enumerate(preguntas_nivel(tema_seleccionado, etapa)):
                    prompts[indice] = gr.update(value=f"**{pregunta['concepto']}**\n\n{pregunta['enunciado']}")
                    radios[indice] = gr.update(choices=pregunta["opciones"], value=None)
                instruccion = f"Nivel **{NOMBRES_ETAPAS[etapa]}** · 5 preguntas · aprueba con 4 aciertos."
            elif practica_visible:
                nuevo["etapa_activa"] = "integradora"
                instruccion = ("Práctica integradora desbloqueada. Aprueba con la rúbrica indicada para este tema. "
                               "En POO se analiza la estructura del código Python, sin ejecutarlo.")
            elif tema_seleccionado:
                instruccion = ("Primero completa el nivel **" + NOMBRES_ETAPAS[etapa] +
                               "**; luego podrás abrir la práctica integradora.")
            return (
                *visibilidad, *prompts, *radios,
                instruccion, nuevo,
            )

        seleccion_outputs = [
            grupo_logica, grupo_poo, grupo_laboratorio, grupo_mvc, grupo_seguimiento,
            grupo_laboratorio_node,
            *preguntas_seg, *respuestas_seg,
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

        abrir_siguiente.click(
            lambda actual: (
                gr.update(selected="actividad" if actual["recomendacion"].get("siguiente_tema") else "ruta"),
                gr.update(value=_seleccion_para_tema(
                    actual, actual["recomendacion"].get("siguiente_tema"))),
            ),
            estado, [navegacion, tipo_actividad],
        ).then(seleccionar_actividad, [tipo_actividad, estado], seleccion_outputs)

        def abrir_desde_diagnostico(tema_v, actual):
            faltantes = [NODO_A_TEMA[n] for n in motor.grafo[TEMA_A_NODO[tema_v]]["prerrequisitos"]
                         if NODO_A_TEMA[n] not in actual["completados"]]
            if faltantes:
                return gr.update(), gr.update(), (
                    "Primero acredita los prerrequisitos: " + ", ".join(faltantes) + ".")
            seleccion = _seleccion_para_tema(actual, tema_v)
            if not seleccion:
                return gr.update(), gr.update(), "El tema ya está acreditado."
            return gr.update(selected="actividad"), gr.update(value=seleccion), (
                "El diagnóstico orienta tu ruta; completar las cuatro etapas acredita el tema.")

        evaluar_tema.click(
            abrir_desde_diagnostico, [tema_evaluar, estado],
            [navegacion, tipo_actividad, aviso_diag],
        ).then(seleccionar_actividad, [tipo_actividad, estado], seleccion_outputs)

        def registrar_resultado(resultado, estado_actual):
            try:
                seleccion = estado_actual.get("tipo_actividad")
                tema_esperado = SEGUIMIENTOS.get(seleccion) or LABORATORIOS.get(seleccion)
                tema_resultado = NODO_A_TEMA.get(resultado.get("tema"), resultado.get("tema"))
                etapa_esperada = siguiente_etapa(
                    {"intentos": estado_actual["intentos"],
                     "temas_acreditados": estado_actual.get("acreditaciones", {})},
                    tema_esperado) if tema_esperado else None
                if (tema_resultado != tema_esperado or
                    estado_actual.get("etapa_activa") != etapa_esperada or
                    (seleccion in SEGUIMIENTOS and etapa_esperada not in ETAPAS[:3]) or
                    (seleccion in LABORATORIOS and etapa_esperada != "integradora")):
                    raise ValueError("La etapa activa cambió. Vuelve a abrir la actividad.")
                faltantes = [NODO_A_TEMA[n] for n in motor.grafo[TEMA_A_NODO[tema_esperado]]["prerrequisitos"]
                             if NODO_A_TEMA[n] not in estado_actual["completados"]]
                if faltantes:
                    raise ValueError("Primero acredita los prerrequisitos del tema.")
                resultado["etapa"] = etapa_esperada
                persistible = normalizar_resultado_calificador(resultado)
                guardado = simulacion.persistir_intento(persistible)
            except (ErrorProgreso, ValueError, TypeError, OverflowError) as exc:
                vr = _vista_ruta(motor, catalogo, estado_actual)
                return (
                    estado_actual, f"## No se guardó el resultado\n\n{exc}",
                    "", "", "", "", *vr,
                    gr.update(selected="resultados"), gr.update(), "", gr.update(), gr.update(visible=False),
                )
            retroalimentacion = _retroalimentacion_local(resultado, estado_actual["perfil"].get("formato"))
            nuevo = dict(estado_actual)
            nuevo["completados"] = temas_acreditados(guardado)
            nuevo["intentos"] = guardado["intentos"]
            nuevo["acreditaciones"] = guardado["temas_acreditados"]
            nuevo["simulacion_activa"] = guardado["simulacion_activa"]
            nuevo["resultado"] = resultado
            _actualizar_recomendacion(motor, nuevo)
            resultado["_estado"] = {"completados": list(nuevo["completados"]),
                                    "recomendacion": nuevo["recomendacion"]}
            vr = _vista_ruta(motor, catalogo, nuevo)
            principal, efecto, revision, retro, recurso = _resultado_markdown(resultado, retroalimentacion, motor, catalogo)
            return (
                nuevo, principal, efecto, revision, retro, recurso,
                vr[0], vr[1], vr[2], vr[3], vr[4], vr[5],
                gr.update(selected="resultados"), gr.update(value=None),
                "", gr.update(**_boton_ia(True)), gr.update(visible=False),
            )

        def entregar_poo(*valores):
            estado_actual = valores[-1]
            respuestas = {f"POO-{i + 1:02d}": str(r or "").strip()
                          for i, r in enumerate(valores[:-1])}
            inicio = estado_actual.get("inicio_actividad") or time.monotonic()
            resultado = calificar_laboratorio_poo(respuestas, max(0.0, time.monotonic() - inicio))
            resultado["respuestas"] = respuestas
            return registrar_resultado(resultado, estado_actual)

        def calificar_lab(*valores):
            estado_actual = valores[-1]
            respuestas = {e["id"]: r or "" for e, r in zip(ejercicios_lab, valores[:-1])}
            inicio = estado_actual.get("inicio_actividad") or time.monotonic()
            resultado = calificar_laboratorio(respuestas, tiempo=max(0.0, time.monotonic() - inicio))
            resultado["respuestas"] = respuestas
            return registrar_resultado(resultado, estado_actual)

        def calificar_lab_logica(*valores):
            estado_actual = valores[-1]
            respuestas = {c: r or "" for c, r in zip(criterios_logica, valores[:-1])}
            inicio = estado_actual.get("inicio_actividad") or time.monotonic()
            resultado = calificar_laboratorio_logica(respuestas, tiempo=max(0.0, time.monotonic() - inicio))
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
            seleccion = estado_actual.get("tipo_actividad")
            etapa = estado_actual.get("etapa_activa")
            if seleccion not in SEGUIMIENTOS or etapa not in ETAPAS[:3]:
                raise ValueError("Selecciona un nivel disponible antes de calificar.")
            tema = SEGUIMIENTOS[seleccion]
            preguntas = preguntas_nivel(tema, etapa)
            respuestas = {p["id"]: r or "" for p, r in zip(preguntas, valores[:-1])}
            resultado = calificar_nivel(tema, etapa, respuestas,
                                       max(0.0, time.monotonic() - (estado_actual.get("inicio_actividad") or time.monotonic())))
            resultado["respuestas"] = respuestas
            return registrar_resultado(resultado, estado_actual)

        def calificar_lab_node(*valores):
            estado_actual = valores[-1]
            respuestas = {e["id"]: r or "" for e, r in zip(ejercicios_lab_node, valores[:-1])}
            inicio = estado_actual.get("inicio_actividad") or time.monotonic()
            resultado = calificar_laboratorio_node(respuestas, tiempo_segundos=max(0.0, time.monotonic() - inicio))
            resultado["respuestas"] = respuestas
            return registrar_resultado(resultado, estado_actual)

        resultado_outputs = [
            estado, resultado_principal, resultado_efecto, resultado_revision,
            resultado_retro, resultado_recurso,
            ruta_cabecera, siguiente_paso, lista_pasos, grafo, tema_detalle, tema_grafo,
            navegacion, tipo_actividad, explicacion_ia, pedir_ia, cargando_ia,
        ]
        enviar_logica.click(calificar_lab_logica, [*respuestas_logica, estado], resultado_outputs)
        enviar_mvc.click(calificar_lab_mvc, [*respuestas_mvc, estado], resultado_outputs)
        enviar_poo.click(entregar_poo, [*respuestas_poo, estado], resultado_outputs)
        enviar_lab.click(calificar_lab, [*respuestas_lab, estado], resultado_outputs)
        enviar_seg.click(calificar_seg, [*respuestas_seg, estado], resultado_outputs)
        enviar_lab_node.click(calificar_lab_node, [*respuestas_lab_node, estado], resultado_outputs)

        def mostrar_cargando_ia():
            return (gr.update(**_boton_ia(False, "Generando explicación…")), gr.update(visible=True), "")

        def pedir_explicacion(estado_actual):
            resultado = estado_actual.get("resultado")
            if not resultado:
                return ("Primero completa una actividad calificada.", gr.update(**_boton_ia(False)), gr.update(visible=False))
            try:
                explicacion = solicitar_explicacion(resultado, estado_actual["perfil"].get("formato"))
            except Exception as exc:
                return (error_explicacion_html(str(exc)), gr.update(**_boton_ia(True, "Reintentar explicación")), gr.update(visible=False))
            if explicacion.get("origen") == "gemini":
                boton = _boton_ia(False, "Explicación con IA generada")
            else:
                boton = _boton_ia(True, "Reintentar explicación")
            return (renderizar_retroalimentacion(explicacion), gr.update(**boton), gr.update(visible=False))

        pedir_ia.click(mostrar_cargando_ia, outputs=[pedir_ia, cargando_ia, explicacion_ia], queue=False, show_progress="hidden", trigger_mode="once").then(
            pedir_explicacion, inputs=estado, outputs=[explicacion_ia, pedir_ia, cargando_ia], show_progress="hidden", concurrency_limit=1,
        )

        volver_ruta.click(lambda: gr.update(selected="ruta"), outputs=navegacion)
        def volver_a_actividad(actual):
            resultado = actual.get("resultado") or {}
            tema = NODO_A_TEMA.get(resultado.get("tema"), resultado.get("tema"))
            seleccion = _seleccion_para_tema(actual, tema)
            if not seleccion:
                seleccion = _seleccion_para_tema(actual, actual["recomendacion"].get("siguiente_tema"))
            return (gr.update(selected="actividad" if seleccion else "ruta"),
                    gr.update(value=seleccion))

        reintentar.click(volver_a_actividad, estado, [navegacion, tipo_actividad]).then(
            seleccionar_actividad, [tipo_actividad, estado], seleccion_outputs,
        ).then(
            reiniciar_navegacion_actividades,
            [control for vista in vistas_actividad for control in vista.respuestas],
            [salida for vista in vistas_actividad for salida in vista.salidas],
            show_progress="hidden",
        )
        otra_actividad.click(lambda: (gr.update(selected="actividad"), gr.update(value=None)), outputs=[navegacion, tipo_actividad])
        continuar_siguiente.click(
            lambda actual: (
                gr.update(selected="actividad") if actual["recomendacion"].get("siguiente_tema") else gr.update(selected="ruta"),
                gr.update(value=_seleccion_para_tema(actual, actual["recomendacion"].get("siguiente_tema"))),
            ), estado, [navegacion, tipo_actividad],
        ).then(seleccionar_actividad, [tipo_actividad, estado], seleccion_outputs).then(
            reiniciar_navegacion_actividades,
            [control for vista in vistas_actividad for control in vista.respuestas],
            [salida for vista in vistas_actividad for salida in vista.salidas],
            show_progress="hidden",
        )

    return demo
