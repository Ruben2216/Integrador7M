"""Vistas HTML de la interfaz.

Este módulo sólo compone HTML a partir de datos ya calculados por el motor, el
calificador o la persistencia. No escribe archivos, no acredita temas y no
decide aprobaciones: esa responsabilidad sigue en los módulos existentes.
"""
from __future__ import annotations

import html
import re
import sqlite3
from typing import Any, Iterable, Mapping, Sequence


# ── Utilidades ──────────────────────────────────────────────────────────────
def e(value: Any) -> str:
    """Escapa cualquier valor que se interpole en HTML."""
    return html.escape("" if value is None else str(value), quote=True)


def _pill(estado: str) -> str:
    mapa = {
        "Acreditado": ("status-ok", "✓"),
        "Correcta": ("status-ok", "✓"),
        "Incorrecta": ("status-warn", "!"),
        "Disponible": ("status-info", "→"),
        "Bloqueado": ("status-warn", "!"),
        "Meta completada": ("status-ok", "✓"),
        "En progreso": ("status-warn", "•"),
        "Tema acreditado": ("status-ok", "✓"),
        "Tema pendiente": ("status-warn", "!"),
        "Práctica entregada": ("status-warn", "…"),
        "Pendiente de revisión": ("status-warn", "…"),
        "Evaluación no disponible": ("status-bad", "×"),
    }
    clase, icono = mapa.get(estado, ("status-neutral", "•"))
    return f'<span class="{clase}">{icono} {e(estado)}</span>'


def _progress(hechos: int, total: int, etiqueta: str = "") -> str:
    total = max(int(total), 1)
    hechos = max(0, min(int(hechos), total))
    pct = round(100 * hechos / total)
    return (
        '<div class="progress-wrap">'
        f'<div class="progress-label"><span>{e(etiqueta or "Avance")}</span>'
        f'<span><b>{hechos} de {total}</b> · {pct}%</span></div>'
        f'<progress class="progress-bar" value="{hechos}" max="{total}" '
        f'aria-label="{e(etiqueta or "Avance")}: {hechos} de {total}">{pct}%</progress>'
        "</div>"
    )


def recursos_html(catalogo: Mapping[str, Mapping[str, Any]], ids: Iterable[str]) -> str:
    elementos: list[str] = []
    for recurso_id in ids:
        recurso = catalogo.get(recurso_id)
        if not recurso:
            continue
        enlace = recurso.get("enlace", "")
        titulo = e(recurso.get("titulo", recurso_id))
        fuente = e(recurso.get("fuente", "Fuente no indicada"))
        formato = e(recurso.get("formato", "Formato no indicado"))
        if enlace:
            accion = (
                f'<a href="{e(enlace)}" target="_blank" rel="noopener noreferrer">'
                f"{titulo}</a>"
            )
        else:
            accion = f"<strong>{titulo}</strong>"
        elementos.append(
            "<li>"
            f"{accion}"
            f'<div class="resource-meta">{fuente} · {formato}</div>'
            "</li>"
        )
    if not elementos:
        return '<p class="muted small">No hay recursos registrados para este tema.</p>'
    return f'<ul class="resource-list">{"".join(elementos)}</ul>'


# ── Inicio ──────────────────────────────────────────────────────────────────
def inicio_html(
    *,
    simulacion_activa: bool,
    error_progreso: str | None,
    meta: str,
    acreditados_meta: Sequence[str],
    total_meta: int,
    completados_todos: Sequence[str],
    siguiente: str | None,
    estado_meta: str,
    actividad_siguiente: str | None,
    intentos: int,
) -> str:
    if error_progreso:
        return (
            '<section class="notice-card notice-danger">'
            '<span class="status-bad">× No se pudo leer el progreso</span>'
            f'<p class="small">{e(error_progreso)}</p>'
            '<p class="small">El archivo local se conserva intacto. Corrige o respalda '
            "el archivo y vuelve a iniciar la simulación.</p></section>"
        )

    if not simulacion_activa:
        return (
            '<section class="hero-card">'
            '<span class="eyebrow">Tu recorrido empieza aquí</span>'
            "<h2>Aprende con una ruta que cambia cuando aprendes</h2>"
            '<p class="reading">Elige una meta, revisa tus conocimientos previos y recibe '
            "el siguiente paso. Cada actividad calificada actualiza tu ruta; una simple "
            "selección no acredita nada.</p>"
            '<div class="stat-grid">'
            '<div class="stat"><b>1</b><span>Diagnóstico guiado</span></div>'
            '<div class="stat"><b>2</b><span>Actividad real</span></div>'
            '<div class="stat"><b>3</b><span>Ruta recalculada</span></div>'
            "</div>"
            '<h3>Ejemplo de ruta</h3>'
            '<ol class="steps">'
            '<li><span class="step-index">1</span><span><span class="step-title">Lógica de Programación</span>'
            '<div class="step-reason">Base para comprender estructuras y algoritmos.</div></span>'
            '<span class="status-info">→ Base</span></li>'
            '<li><span class="step-index">2</span><span><span class="step-title">POO y PostgreSQL</span>'
            '<div class="step-reason">Dos ramas que habilitan el backend.</div></span>'
            '<span class="status-warn">! En progreso</span></li>'
            '<li><span class="step-index">3</span><span><span class="step-title">Backend con Node.js</span>'
            '<div class="step-reason">Meta final del ejemplo.</div></span>'
            '<span class="status-neutral">Meta</span></li>'
            "</ol></section>"
        )

    acreditados = " · ".join(e(t) for t in acreditados_meta) or "Aún ninguno"
    if estado_meta == "Meta completada":
        siguiente_html = (
            '<div class="callout good"><b>Meta completada.</b> '
            "Ya acreditaste todos los temas de esta meta. Puedes elegir otra meta "
            "conservando tu historial.</div>"
        )
        accion = "Elegir otra meta"
    else:
        detalle = (
            f"Actividad conectada: {e(actividad_siguiente)}."
            if actividad_siguiente
            else "La actividad de este tema aún no está conectada; puedes consultar sus recursos."
        )
        siguiente_html = (
            f'<div class="callout"><b>Siguiente paso:</b> {e(siguiente or "Revisa tu ruta")}. '
            f"{detalle}</div>"
        )
        accion = "Continuar aprendizaje"

    return (
        '<section class="hero-card">'
        '<span class="eyebrow">Simulación local recuperada</span>'
        f"<h2>{e(meta)}</h2>"
        f'<p class="reading">Tu progreso se guarda automáticamente. Cada actividad '
        "calificada actualiza tu ruta y las acreditaciones verificadas.</p>"
        + _progress(len(acreditados_meta), total_meta, "Progreso de la meta")
        + '<div class="stat-grid">'
        f'<div class="stat"><b>{len(acreditados_meta)}</b><span>temas acreditados</span></div>'
        f'<div class="stat"><b>{intentos}</b><span>intento(s) registrado(s)</span></div>'
        f'<div class="stat"><b>{len(completados_todos)}</b><span>tema(s) en total</span></div>'
        "</div>"
        + siguiente_html
        + f'<p class="small muted">{accion}.</p>'
        "</section>"
    )


# ── Diagnóstico ─────────────────────────────────────────────────────────────
def meta_detalle_html(
    meta: str,
    prerequisitos: Sequence[str],
    pendientes: Sequence[str],
    recursos: str,
) -> str:
    req = ", ".join(e(t) for t in prerequisitos) or "No tiene prerrequisitos."
    pend = ", ".join(e(t) for t in pendientes) if pendientes else "Ninguno"
    return (
        '<section class="card">'
        f'<span class="eyebrow">Meta seleccionada</span><h3>{e(meta)}</h3>'
        f'<p><b>Prerrequisitos:</b> {req}</p>'
        f'<p><b>Pendientes:</b> {pend}</p>'
        '<p class="small muted">La meta se acredita tras aprobar los tres niveles '
        "y la práctica integradora de ese tema. Elegir una meta no crea acreditaciones.</p>"
        f"<h4>Recursos de la meta</h4>{recursos}"
        "</section>"
    )


def disponibilidad_html(
    tema: str,
    estado: str,
    faltantes: Sequence[str],
    actividad: str,
    detalle_actividad: str,
    es_diagnostico: bool = True,
) -> str:
    pend = (
        " · Prerrequisito(s) pendiente(s): " + ", ".join(e(t) for t in faltantes)
        if faltantes
        else ""
    )
    nota = (
        "El tema tiene prerrequisitos pendientes. Acredítalos antes de iniciar "
        "sus niveles y la práctica integradora."
        if es_diagnostico and faltantes
        else "Una selección no acredita el tema; completa las cuatro etapas de evaluación."
    )
    return (
        '<section class="card">'
        f'<span class="eyebrow">Tema a evaluar</span><h3>{e(tema)}</h3>'
        f'<p>{_pill(estado)}{pend}</p>'
        f"<p><b>Actividad:</b> {e(actividad)}</p>"
        f'<p class="small muted">{e(detalle_actividad)}</p>'
        f'<div class="callout"><span class="small">{nota}</span></div>'
        "</section>"
    )


def acreditaciones_html(completados: Sequence[str]) -> str:
    if not completados:
        return (
            '<div class="notice-card"><b>Aún no hay acreditaciones verificadas.</b> '
            "Puedes evaluar un tema o generar la ruta para empezar con los temas "
            "pendientes. El archivo existente se conserva.</div>"
        )
    items = "".join(f"<li>{e(t)}</li>" for t in completados)
    return (
        '<div class="card"><b>Acreditaciones verificadas</b>'
        f'<ul class="criteria-list">{items}</ul>'
        '<p class="small muted">Incluye temas acreditados con la ruta de cuatro etapas '
        "y acreditaciones anteriores conservadas en el progreso local.</p></div>"
    )


# ── Mi ruta ─────────────────────────────────────────────────────────────────
def ruta_cabecera_html(
    meta: str,
    acreditados: int,
    total: int,
    estado_meta: str,
    completados: Sequence[str],
) -> str:
    resumen = ", ".join(e(t) for t in completados) or "Aún ninguno"
    return (
        '<section class="route-card">'
        '<span class="eyebrow">Mi ruta</span>'
        f"<h2>{e(meta)}</h2>"
        f'<p><b>{acreditados} de {max(total, 1)}</b> temas pertinentes acreditados '
        f"{_pill(estado_meta)}</p>"
        + _progress(acreditados, total, "Progreso calculado por el motor")
        + f'<p class="small muted">Acreditados: {resumen}</p>'
        "</section>"
    )


def siguiente_paso_html(
    tema: str | None,
    explicacion: str,
    actividad: str | None,
    recursos: str,
    bloqueado_por: Sequence[str] = (),
) -> str:
    if not tema:
        return (
            '<article class="card"><span class="eyebrow">Tu siguiente paso</span>'
            "<h3>La meta está completada</h3>"
            '<p class="muted">No quedan temas pendientes en la ruta calculada. '
            "Puedes elegir otra meta; tu historial y acreditaciones se conservan.</p></article>"
        )
    if bloqueado_por:
        razon = ", ".join(e(t) for t in bloqueado_por)
        return (
            '<article class="card"><span class="eyebrow">Tu siguiente paso</span>'
            f"<h3>{e(tema)}</h3>"
            f'<p>{_pill("Bloqueado")} Primero acredita: <b>{razon}</b>.</p>'
            f'<p class="small muted">{e(explicacion)}</p>'
            f"{recursos}</article>"
        )
    return (
        '<article class="card"><span class="eyebrow">Tu siguiente paso</span>'
        f"<h3>{e(tema)}</h3>"
        f'<p>{e(explicacion)}</p>'
        f'<p class="small">{_pill("Disponible")} · Actividad: {e(actividad or "no conectada")}</p>'
        f"{recursos}</article>"
    )


def lista_pasos_html(
    temas: Sequence[str],
    estados: Mapping[str, tuple[str, Sequence[str]]],
    siguiente: str | None,
    ruta_pendiente: Sequence[str],
) -> str:
    pasos: list[str] = []
    for indice, tema in enumerate(temas, 1):
        estado, faltantes = estados.get(tema, ("Bloqueado", []))
        clases = ["is-next"] if tema == siguiente else []
        razon = ""
        if estado == "Bloqueado" and faltantes:
            razon = "Falta acreditar: " + ", ".join(faltantes)
        elif tema in ruta_pendiente:
            razon = "Forma parte de la ruta pendiente hacia tu meta."
        elif estado == "Acreditado":
            razon = "Tema acreditado tras completar su evaluación o por historial previo."
        elif estado == "En progreso":
            razon = "Ya aprobaste etapas; continúa con el siguiente nivel."
        else:
            razon = "Disponible para estudiar."
        pasos.append(
            f'<li class="{" ".join(clases)}">'
            f'<span class="step-index">{indice:02d}</span>'
            f'<span><span class="step-title">{e(tema)}</span>'
            f'<div class="step-reason">{e(razon)}</div></span>'
            f'{_pill(estado)}</li>'
        )
    return (
        '<section class="card"><span class="eyebrow">Pasos de la ruta</span>'
        "<h3>Lista sincronizada con el grafo</h3>"
        f'<ol class="steps">{"".join(pasos)}</ol>'
        '<p class="small muted">La lista y el grafo salen de la misma consulta al '
        "motor A* y de las mismas acreditaciones verificadas.</p></section>"
    )


def tema_detalle_html(
    tema: str,
    estado: str,
    prerequisitos: Sequence[str],
    pendientes: Sequence[str],
    recursos: str,
    actividad: str,
    detalle_actividad: str,
    es_siguiente: bool = False,
) -> str:
    req = ", ".join(e(t) for t in prerequisitos) or "Ninguno"
    pend = ", ".join(e(t) for t in pendientes) or "Ninguno"
    aviso = ""
    if estado == "Bloqueado":
        aviso = (
            '<div class="callout warn"><b>Tema bloqueado.</b> Para estudiarlo primero '
            f"acredita: <b>{pend}</b>. Puedes usar «Ir al prerrequisito» para revisarlo."
            "</div>"
        )
    elif estado == "Acreditado":
        aviso = '<div class="callout good"><b>Tema acreditado.</b> Ya forma parte de tu historial verificado.</div>'
    elif estado == "En progreso":
        aviso = '<div class="callout"><b>Tema en progreso.</b> Revisa las etapas pendientes para acreditarlo.</div>'
    elif estado == "Disponible":
        aviso = '<div class="callout good"><b>Tema disponible.</b> Puedes abrir sus recursos o iniciar su actividad conectada.</div>'
    siguiente = ' <span class="status-info">→ siguiente</span>' if es_siguiente else ""
    return (
        '<section class="card">'
        f'<span class="eyebrow">Detalle del tema</span><h3>{e(tema)}{siguiente}</h3>'
        f"<p>{_pill(estado)}</p>"
        f'<p><b>Prerrequisitos:</b> {req}</p>'
        f'<p><b>Pendientes:</b> {pend}</p>'
        f"{aviso}"
        f'<p><b>Actividad:</b> {e(actividad)}<br><span class="small muted">{e(detalle_actividad)}</span></p>'
        f"<h4>Recursos</h4>{recursos}"
        "</section>"
    )


# ── Actividad ───────────────────────────────────────────────────────────────
def actividad_avance_html(respondidos: Sequence[bool], indice: int, seguimiento: bool) -> str:
    etiqueta = "Pregunta" if seguimiento else "Ejercicio"
    unidad = "preguntas respondidas" if seguimiento else "ejercicios respondidos"
    pasos = []
    for numero, respondido in enumerate(respondidos):
        activo = numero == indice
        estado = ("respondida" if seguimiento else "respondido") if respondido else "pendiente"
        actual = ' aria-current="step"' if activo else ""
        pasos.append(
            f'<li class="{"answered" if respondido else ""}"{actual} '
            f'aria-label="{etiqueta} {numero + 1}: {estado}{", actual" if activo else ""}">'
            f'{numero + 1}</li>'
        )
    return (
        '<section aria-label="Resumen de avance" aria-live="polite">'
        '<h3>Tu avance</h3>'
        f'<p class="activity-caption">{sum(respondidos)} de {len(respondidos)} {unidad}</p>'
        f'<ol class="activity-steps">{"".join(pasos)}</ol>'
        '<p class="activity-caption">Borde verde: paso actual. Fondo verde: respuesta completa.</p>'
        '<p class="activity-caption">Usa Anterior y Siguiente para revisar tus respuestas antes de enviar.</p>'
        '</section>'
    )


def actividad_enunciado_html(item: Mapping[str, Any], concepto: str | None = None) -> str:
    titulo = item.get("titulo") or concepto or item.get("concepto", "Ejercicio")
    return (
        '<header class="activity-prompt">'
        f'<p class="activity-meta">{e(item.get("id"))} · {e(item.get("dificultad", ""))}</p>'
        f'<h3>{e(titulo)}</h3>'
        f'<p>{e(item.get("enunciado") or item.get("pregunta", ""))}</p>'
        '</header>'
    )


def actividad_codigo_html(codigo: str) -> str:
    return f'<pre class="activity-code"><code>{e(codigo)}</code></pre>'


def actividad_fragmentos_mvc(item: Mapping[str, Any]) -> dict[str, str]:
    """Separa sólo fragmentos etiquetados por el propio banco, sin alterar el código."""
    partes = re.split(r"(?m)^(// Fragmento [A-Z])\r?\n", item.get("codigo", ""))
    return {
        partes[i].removeprefix("// "): partes[i] + "\n" + partes[i + 1].rstrip()
        for i in range(1, len(partes), 2)
    }


def catalogo_nota_html(estados: Mapping[str, tuple[str, Sequence[str]]], actividades: Mapping[str, str]) -> str:
    filas = []
    for tema, (estado, faltantes) in estados.items():
        act = actividades.get(tema, "Evaluación no disponible")
        extra = ""
        if estado == "Bloqueado" and faltantes:
            extra = " · Falta: " + ", ".join(faltantes)
        filas.append(
            f'<li><div class="fila-disponibilidad">'
            f'<span class="step-title">{e(tema)}</span>'
            f'{_pill(estado)}'
            f'<span class="motivo">{e(act)}{e(extra)}</span>'
            f'</div></li>'
        )
    return (
        '<section class="notice-card"><b>Disponibilidad de actividades</b>'
        '<p class="small">La disponibilidad del tema en el grafo y la disponibilidad de '
        "su actividad son estados distintos. Un tema puede estar disponible y aun así "
        "no tener evaluación conectada.</p>"
        f'<ol class="steps">{"".join(filas)}</ol></section>'
    )


def actividad_encabezado_html(act: Mapping[str, Any], item: Mapping[str, Any]) -> str:
    total = len(act["items"])
    numero = int(act["indice"]) + 1
    tipo = {
        "seguimiento": "Seguimiento",
        "laboratorio": "Laboratorio",
        "poo": "Práctica",
    }.get(act.get("tipo"), "Actividad")
    etiqueta = "Pregunta" if act.get("modo") in ("choice", "node_choice") else "Ejercicio"
    concepto = item.get("concepto", "Actividad")
    dificultad = item.get("dificultad", "")
    dificultad_html = f' <span class="status-neutral">{e(dificultad)}</span>' if dificultad else ""
    return (
        '<article class="question-card">'
        f'<span class="eyebrow">{e(tipo)} · {e(act.get("tema", "Tema"))}</span>'
        f"<h2>{etiqueta} {numero} de {total}</h2>"
        f'<p class="muted small">{e(concepto)}{dificultad_html}</p>'
        + _progress(numero, total, "Avance del intento")
        + "</article>"
    )


def actividad_pregunta_html(act: Mapping[str, Any], item: Mapping[str, Any]) -> str:
    titulo = item.get("titulo") or item.get("id") or "Ejercicio"
    enunciado = item.get("enunciado") or item.get("pregunta") or ""
    titulo_html = f"<h3>{e(titulo)}</h3>" if act.get("modo") == "poo" else ""
    return (
        '<section class="card reading">'
        f"{titulo_html}"
        f'<p class="reading">{e(enunciado)}</p>'
        "</section>"
    )


def detalles_intento_html(act: Mapping[str, Any], item: Mapping[str, Any]) -> str:
    variante = act.get("variante") or "No aplica"
    identificador = act.get("intento_id") or "Sin identificar"
    return (
        '<section class="card"><dl class="kv">'
        f"<dt>Tema</dt><dd>{e(act.get('tema'))}</dd>"
        f"<dt>Tipo</dt><dd>{e(act.get('tipo'))}</dd>"
        f"<dt>Variante</dt><dd>{e(variante)}</dd>"
        f"<dt>Ejercicio</dt><dd>{e(item.get('id'))}</dd>"
        f"<dt>ID del intento</dt><dd class=\"mono\">{e(identificador)}</dd>"
        "</dl></section>"
    )


def actividad_referencia_html(act: Mapping[str, Any], item: Mapping[str, Any]) -> str:
    if act.get("modo") == "sql":
        return _lab_referencia(item)
    if act.get("modo") == "poo":
        return _poo_referencia(item)
    if act.get("modo") == "node_choice":
        return (
            '<section class="card"><b>Cómo se califica</b>'
            "<p class=\"small muted\">Cada pregunta vale un punto. Se acredita el tema con "
            "4 de 5 respuestas correctas. La variante se conserva durante todo el intento.</p></section>"
        )
    return (
        '<section class="card"><b>Cómo se califica</b>'
        '<p class="small muted">Cada pregunta tiene una única opción correcta. Se acredita '
        "el tema con 4 de 5 respuestas correctas.</p></section>"
    )


def lab_datos_html(item: Mapping[str, Any]) -> str:
    tablas = _leer_esquema(item.get("esquema_sql", ""))
    if not tablas:
        return '<p class="muted small">El banco no incluye filas de ejemplo para este ejercicio.</p>'
    bloques = []
    for tabla in tablas:
        cabecera = "".join(f"<th>{e(col['nombre'])}</th>" for col in tabla["columnas"])
        filas = []
        for fila in tabla["filas"]:
            celdas = "".join(f'<td class="mono">{e(valor)}</td>' for valor in fila)
            filas.append(f"<tr>{celdas}</tr>")
        if not filas:
            filas.append(f'<tr><td colspan="{max(len(tabla["columnas"]), 1)}" class="muted">Sin filas de ejemplo.</td></tr>')
        bloques.append(
            '<div class="schema-block">'
            f"<h4>Filas de ejemplo · {e(tabla['nombre'])}</h4>"
            '<div class="table-scroll"><table class="schema">'
            f"<thead><tr>{cabecera}</tr></thead><tbody>{''.join(filas)}</tbody>"
            "</table></div></div>"
        )
    return "".join(bloques)


def revision_html(act: Mapping[str, Any], pendientes: int) -> str:
    total = len(act["items"])
    respuesta = (
        " Puedes enviar en blanco; el calificador registrará las respuestas vacías "
        "como incorrectas."
        if pendientes
        else " Todas las respuestas están completas."
    )
    return (
        '<section class="review-card">'
        '<span class="eyebrow">Revisión antes de enviar</span>'
        f"<h3>{pendientes} de {total} respuesta(s) pendiente(s)</h3>"
        f'<p class="small">{respuesta} Usa «Anterior» y «Siguiente» para volver a '
        "completarlas antes de enviar.</p>"
        "</section>"
    )


def _lab_referencia(item: Mapping[str, Any]) -> str:
    tablas = _leer_esquema(item.get("esquema_sql", ""))
    esquema = []
    for tabla in tablas:
        filas = []
        for col in tabla["columnas"]:
            marca = " · PK" if col["pk"] else ""
            filas.append(
                f'<tr><td class="mono">{e(col["nombre"])}</td>'
                f'<td>{e(col["tipo"] or "—")}{marca}</td></tr>'
            )
        esquema.append(
            '<div class="schema-block">'
            f"<h4>{e(tabla['nombre'])}</h4>"
            '<div class="table-scroll"><table class="schema">'
            "<thead><tr><th>Columna</th><th>Tipo</th></tr></thead>"
            f"<tbody>{''.join(filas)}</tbody></table></div></div>"
        )
    columnas = _columnas_esperadas(item.get("respuesta_esperada_sql", ""))
    cols = ", ".join(f"<code>{e(c)}</code>" for c in columnas) or "las columnas descritas en el criterio"
    criterios = item.get("criterios", [])
    criterios_html = "".join(f"<li>{e(c.get('descripcion', c.get('id', '')))}</li>" for c in criterios)
    integradora = (
        '<div class="callout warn"><b>Ejercicio integrador obligatorio.</b> '
        "El laboratorio no acredita si este ejercicio no se aprueba.</div>"
        if item.get("id") == "PSQL-LAB04"
        else ""
    )
    pista = _pista_sql(item.get("concepto", ""))
    return (
        '<section class="card">'
        '<span class="eyebrow">Referencia de solo lectura</span>'
        "<h3>Tablas disponibles</h3>"
        f"{''.join(esquema) or '<p class=\"muted small\">Sin esquema en el banco.</p>'}"
        "<h3>Qué debe devolver tu consulta</h3>"
        f"<p class=\"small\">Columnas solicitadas: {cols}.</p>"
        f'<ul class="criteria-list">{criterios_html}</ul>'
        '<h3>Criterio de acreditación</h3>'
        '<p class="small">Se requieren al menos 3 de 4 ejercicios correctos y el '
        "ejercicio integrador PSQL-LAB04 aprobado. La comparación la hace el "
        "calificador real contra la base temporal.</p>"
        f"{integradora}"
        '<details class="callout" style="margin-top:10px"><summary><b>Ver pista</b></summary>'
        f'<p class="small">{e(pista)}</p></details>'
        "</section>"
    )


def _pista_sql(concepto: str) -> str:
    pistas = {
        "WHERE": "Filtra filas con una condición sobre la columna que describe el enunciado; no necesitas modificar la tabla.",
        "JOIN": "Identifica la clave que relaciona ambas tablas y decide si debes conservar las filas sin coincidencia.",
        "GROUP_BY": "Agrupa por la dimensión solicitada y aplica la función de agregación sobre el grupo, no sobre cada fila.",
        "INTEGRADORA": "Combina la relación entre tablas, una agregación por entidad y el tratamiento de valores ausentes. Revisa el orden solicitado.",
    }
    return pistas.get(concepto, "Lee el resultado esperado y elige las columnas y el filtro que describen el enunciado.")


def _poo_referencia(item: Mapping[str, Any]) -> str:
    criterios = _criterios_poo(item.get("id", ""))
    lista = "".join(f"<li>{e(c)}</li>" for c in criterios)
    return (
        '<section class="card"><b>Criterios de revisión</b>'
        f'<ul class="criteria-list">{lista}</ul>'
        '<p class="small muted">Escribe código Python. La revisión automática comprueba '
        "la estructura del programa sin ejecutarlo; no garantiza su comportamiento.</p></section>"
    )


def _criterios_poo(identificador: str) -> list[str]:
    mapa = {
        "POO-01": [
            "La clase Libro declara los atributos titulo y autor.",
            "El método describir() devuelve ambos datos.",
            "Se crean dos objetos Libro con información distinta.",
        ],
        "POO-02": [
            "La cuenta conserva un saldo inicial válido.",
            "depositar() y retirar() modifican el saldo de forma coherente.",
            "Se evitan depósitos no positivos y retiros mayores al saldo.",
        ],
        "POO-03": [
            "El stock está encapsulado y no se modifica directamente desde fuera.",
            "vender() descuenta unidades sólo si hay existencias.",
            "consultar_stock() expone el estado sin permitir saltarse la validación.",
        ],
        "POO-04": [
            "Pedido y Producto tienen responsabilidades distintas y claras.",
            "Producto aporta precio y datos; Pedido calcula el total.",
            "El método recorre los productos y suma correctamente.",
        ],
    }
    return mapa.get(identificador, ["Resuelve el enunciado con clases, atributos y métodos coherentes."])


# ── Resultados ──────────────────────────────────────────────────────────────
def _descripcion_criterio(identificador: str, descripciones: Mapping[str, str]) -> str:
    return descripciones.get(identificador, identificador)


def resultado_principal_html(
    resultado: Mapping[str, Any],
    descripciones: Mapping[str, str],
    actividad_titulo: str,
) -> str:
    tipo = resultado.get("tipo")
    tema = resultado.get("tema", "Tema")
    if tipo == "poo":
        respondidos = int(resultado.get("respondidos", 0))
        total = int(resultado.get("total", 4))
        estado = "Práctica entregada · pendiente de revisión"
        score = f"{respondidos} / {total}"
        unidad = "respuestas entregadas"
    else:
        if tipo == "laboratorio":
            aciertos = resultado.get("puntaje_obtenido", resultado.get("ejercicios_correctos", 0))
            total = resultado.get("puntaje_maximo", resultado.get("total_ejercicios", 0))
        else:
            aciertos = resultado.get("correctas", 0)
            total = resultado.get("total_preguntas", 0)
        score = f"{aciertos} / {total}"
        unidad = "aciertos o puntos"
        estado = "Tema acreditado" if resultado.get("acreditado") else "Tema pendiente"

    cumplidos = [_descripcion_criterio(c, descripciones) for c in resultado.get("criterios_cumplidos", [])]
    incumplidos = [_descripcion_criterio(c, descripciones) for c in resultado.get("criterios_incumplidos", [])]
    conceptos = list(resultado.get("conceptos_con_errores", []))

    if tipo == "poo":
        bien = ["Entregaste tu solución para revisión."] + ([f"Completaste {score} retos."] if resultado.get("respondidos") else [])
        reforzar = ["La práctica no tiene evaluador automático conectado; no se acredita hasta la revisión."]
        respuestas = resultado.get("_respuestas", {})
        faltantes = [
            item.get("titulo", item.get("id"))
            for item in resultado.get("_items", [])
            if not str(respuestas.get(item.get("id", ""), "")).strip()
        ]
        if faltantes:
            reforzar.append("Retos sin respuesta: " + ", ".join(faltantes) + ".")
    else:
        bien = cumplidos or ["No hubo criterios cumplidos registrados por el calificador."]
        reforzar = incumplidos or conceptos or ["No se registraron criterios incumplidos."]
        if conceptos and incumplidos:
            reforzar.append("Conceptos a repasar: " + ", ".join(conceptos) + ".")

    bien_html = "".join(f'<li class="criteria-ok">✓ {e(x)}</li>' for x in bien)
    ref_html = "".join(f'<li class="criteria-bad">! {e(x)}</li>' for x in reforzar)
    return (
        '<section class="result-card">'
        '<span class="eyebrow">Resultado verificado</span>'
        f"<h2>{e(tema)}</h2>"
        f'<p class="muted small">{e(actividad_titulo)}</p>'
        f'<div class="score-line"><b>{e(score)}</b><span class="muted">{e(unidad)}</span>'
        f"{_pill(estado)}</div>"
        '<div class="entity-grid" style="margin-top:14px">'
        '<div><h3>Qué hiciste bien</h3>'
        f'<ul class="criteria-list">{bien_html}</ul></div>'
        '<div><h3>Qué debes reforzar</h3>'
        f'<ul class="criteria-list">{ref_html}</ul></div>'
        "</div></section>"
    )


def resultado_efecto_html(
    *,
    estado_meta: str,
    aprobado: bool,
    tema: str,
    siguiente: str | None,
    bloqueados_dependientes: Sequence[str],
    completados: Sequence[str],
    actividad_siguiente: str | None,
) -> str:
    if estado_meta == "Meta completada":
        lista = "".join(f"<li>{e(t)}</li>" for t in completados) or "<li>Sin acreditaciones registradas.</li>"
        return (
            '<section class="route-card"><span class="eyebrow">Cómo afecta tu ruta</span>'
            "<h3>Meta completada</h3>"
            '<div class="callout good">El motor A* ya no tiene pasos pendientes para esta '
            "meta. Elige otra meta cuando quieras seguir; el historial se conserva.</div>"
            f'<h4>Temas acreditados</h4><ul class="criteria-list">{lista}</ul></section>'
        )
    if aprobado:
        extra = (
            f"La actividad conectada del siguiente tema es: {e(actividad_siguiente)}."
            if actividad_siguiente
            else "El siguiente tema puede no tener actividad conectada; revisa sus recursos."
        )
        return (
            '<section class="route-card"><span class="eyebrow">Cómo afecta tu ruta</span>'
            f"<h3>{e(tema)} acreditado · ruta actualizada</h3>"
            f'<p><b>Siguiente paso:</b> {e(siguiente or "revisa Mi ruta")}.</p>'
            f'<p class="small muted">{extra}</p>'
            '<p class="small muted">El bloqueo y el cierre de la meta provienen del motor '
            "A* consultado con las acreditaciones guardadas, no de esta pantalla.</p>"
            "</section>"
        )
    bloqueo = ""
    if bloqueados_dependientes:
        bloqueo = (
            '<p class="small">Temas que siguen bloqueados: '
            + ", ".join(f"<b>{e(t)}</b>" for t in bloqueados_dependientes)
            + " hasta acreditar este tema.</p>"
        )
    return (
        '<section class="notice-card"><span class="eyebrow">Cómo afecta tu ruta</span>'
        f"<h3>{e(tema)} sigue pendiente</h3>"
        f'<p><b>Siguiente paso:</b> {e(siguiente or "revisa Mi ruta")}.</p>'
        f"{bloqueo}"
        '<p class="small muted">El resultado quedó registrado como intento, pero el tema '
        "no se acredita. Puedes reintentar o volver a Mi ruta.</p></section>"
    )


def resultado_revision_html(
    resultado: Mapping[str, Any],
    descripciones: Mapping[str, str],
) -> str:
    detalle = resultado.get("detalle", [])
    respuestas = resultado.get("_respuestas", resultado.get("respuestas", {}))
    items = {item.get("id"): item for item in resultado.get("_items", [])}
    if not detalle:
        return '<p class="muted small">El calificador no entregó detalle por pregunta o ejercicio.</p>'
    bloques = []
    for entrada in detalle:
        identificador = str(entrada.get("id", ""))
        item = items.get(identificador, {})
        concepto = entrada.get("concepto") or item.get("concepto") or identificador
        correcto = bool(entrada.get("correcto"))
        marca = _pill("Correcta") if correcto else _pill("Incorrecta")
        respuesta = respuestas.get(identificador, "")
        if isinstance(respuesta, str) and len(respuesta) > 700:
            respuesta = respuesta[:700] + "…"
        cumplidos = [_descripcion_criterio(c, descripciones) for c in entrada.get("criterios_cumplidos", [])]
        incumplidos = [_descripcion_criterio(c, descripciones) for c in entrada.get("criterios_incumplidos", [])]
        criterios = ""
        if cumplidos or incumplidos:
            ok = "".join(f'<li class="criteria-ok">✓ {e(c)}</li>' for c in cumplidos)
            no = "".join(f'<li class="criteria-bad">! {e(c)}</li>' for c in incumplidos)
            criterios = f'<ul class="criteria-list">{ok}{no}</ul>'
        error = f'<p class="small status-bad">! {e(entrada.get("error"))}</p>' if entrada.get("error") else ""
        respuesta_html = (
            f'<pre class="mono small" style="white-space:pre-wrap;overflow-wrap:anywhere;background:var(--surface-2);padding:8px;border-radius:8px">{e(respuesta) or "Sin respuesta"}</pre>'
            if respuesta
            else '<p class="small muted">Sin respuesta registrada.</p>'
        )
        bloques.append(
            '<article class="card" style="margin-bottom:10px">'
            f"<h4>{e(concepto)} {marca}</h4>"
            f"{respuesta_html}{criterios}{error}"
            "</article>"
        )
    variante = resultado.get("variante")
    pie = f'<p class="small muted">Variante del intento: {e(variante)}</p>' if variante else ""
    return pie + "".join(bloques)


def resultado_retro_html(resultado: Mapping[str, Any], recursos: str = "") -> str:
    retro = resultado.get("retroalimentacion")
    partes: list[str] = []
    if isinstance(retro, dict):
        if retro.get("comentario"):
            partes.append(f'<p><b>Comentario:</b> {e(retro["comentario"])}</p>')
        if retro.get("pista"):
            partes.append(f'<p><b>Pista:</b> {e(retro["pista"])}</p>')
        recurso = retro.get("recurso")
        if isinstance(recurso, dict):
            titulo = e(recurso.get("titulo", "Recurso recomendado"))
            enlace = recurso.get("enlace")
            formato = e(recurso.get("formato", ""))
            if enlace:
                partes.append(
                    f'<p><b>Recurso:</b> <a href="{e(enlace)}" target="_blank" rel="noopener noreferrer">{titulo}</a>'
                    f' <span class="muted small">{formato}</span></p>'
                )
            else:
                partes.append(f"<p><b>Recurso:</b> {titulo} {formato}</p>")
        elif isinstance(recurso, str) and recurso.strip():
            partes.append(f"<p><b>Recurso:</b> {e(recurso)}</p>")
    if partes:
        return '<section class="card">' + "".join(partes) + "</section>"
    return (
        '<section class="card"><p class="muted small">La explicación automática no está '
        "conectada en esta rama. El resultado y su efecto en la ruta siguen disponibles; "
        "puedes repasar con los recursos del tema.</p>"
        f"{recursos}</section>"
    )


def recurso_repaso_html(recursos: str) -> str:
    return f'<section class="card"><h3>Recurso de repaso</h3>{recursos}</section>'


# ── Esquema SQL del banco ───────────────────────────────────────────────────
def _leer_esquema(esquema_sql: str) -> list[dict[str, Any]]:
    if not esquema_sql:
        return []
    conn = None
    try:
        conn = sqlite3.connect(":memory:")
        conn.executescript(esquema_sql)
        tablas = [
            fila[0]
            for fila in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        resultado = []
        for tabla in tablas:
            columnas = []
            for col in conn.execute(f'PRAGMA table_info("{tabla}")').fetchall():
                columnas.append({
                    "nombre": col[1],
                    "tipo": col[2],
                    "pk": bool(col[5]),
                })
            filas = conn.execute(f'SELECT * FROM "{tabla}" LIMIT 3').fetchall()
            resultado.append({"nombre": tabla, "columnas": columnas, "filas": filas})
        return resultado
    except sqlite3.Error:
        return []
    finally:
        if conn is not None:
            conn.close()


def _columnas_esperadas(sql: str) -> list[str]:
    coincidencia = re.search(r"\bselect\b(.*?)\bfrom\b", sql or "", re.IGNORECASE | re.DOTALL)
    if not coincidencia:
        return []
    expresion = coincidencia.group(1).strip()
    partes: list[str] = []
    profundidad = 0
    actual: list[str] = []
    for caracter in expresion:
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad = max(0, profundidad - 1)
        if caracter == "," and profundidad == 0:
            partes.append("".join(actual).strip())
            actual = []
        else:
            actual.append(caracter)
    if actual:
        partes.append("".join(actual).strip())
    columnas = []
    for parte in partes:
        parte = re.sub(r"^\s*distinct\s+", "", parte, flags=re.IGNORECASE)
        alias = re.search(r"\bas\s+([A-Za-z_][\w$]*)\s*$", parte, re.IGNORECASE)
        if alias:
            columnas.append(alias.group(1))
            continue
        simple = re.fullmatch(r"(?:[A-Za-z_][\w$]*\.)?([A-Za-z_][\w$]*)", parte.strip())
        if simple:
            columnas.append(simple.group(1))
        else:
            columnas.append(parte.strip())
    return columnas
