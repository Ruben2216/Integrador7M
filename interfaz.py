"""Interfaz principal del recomendador y las actividades del proyecto."""

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
from recomendador import NIVELES, FORMATOS, NODO_A_TEMA, TEMA_A_NODO
import simulacion
from integracion_calificador import normalizar_resultado_calificador
from progreso import ErrorProgreso, temas_acreditados
from ui.resultados import renderizar_retroalimentacion

_DIR = os.path.dirname(os.path.abspath(__file__))
_RUTA_CATALOGO = os.path.join(_DIR, "catalogo_recursos.json")
_RUTA_POO = os.path.join(_DIR, "ejercicios_poo.json")


def _cargar_json(ruta: str) -> dict[str, Any]:
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def _cargar_catalogo() -> dict[str, dict[str, str]]:
    return _cargar_json(_RUTA_CATALOGO)


def _estado_inicial(motor: Any) -> dict[str, Any]:
    error_progreso = None
    try:
        guardado = simulacion.almacen.cargar()
    except ErrorProgreso as exc:
        # No se escribe ni reemplaza un archivo existente que no pudo leerse.
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
        intento["variante"] for intento in guardado["intentos"]
        if intento.get("variante")
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


def _obtener_recursos(catalogo: dict[str, dict[str, str]], ids: list[str]) -> str:
    lineas = []
    for recurso_id in ids:
        recurso = catalogo[recurso_id]
        lineas.append(
            f"- **[{recurso['titulo']}]({recurso['enlace']})** — "
            f"{recurso['formato']} · {recurso['fuente']}"
        )
    return "\n".join(lineas) if lineas else "_No hay recursos registrados para este tema._"


def _estado_del_tema(motor: Any, tema: str, completados: list[str]) -> tuple[str, list[str]]:
    nodo = TEMA_A_NODO[tema]
    if tema in completados:
        return "Acreditado", []
    faltantes = [
        NODO_A_TEMA[prerrequisito]
        for prerrequisito in motor.grafo[nodo]["prerrequisitos"]
        if NODO_A_TEMA[prerrequisito] not in completados
    ]
    return ("Bloqueado", faltantes) if faltantes else ("Disponible", [])


def _detalle_tema(
    motor: Any,
    catalogo: dict[str, dict[str, str]],
    tema: str,
    completados: list[str],
) -> str:
    estado, faltantes = _estado_del_tema(motor, tema, completados)
    nodo = TEMA_A_NODO[tema]
    prerrequisitos = [
        NODO_A_TEMA[requisito] for requisito in motor.grafo[nodo]["prerrequisitos"]
    ]
    pendientes = ", ".join(faltantes) if faltantes else "Ninguno"
    requisitos = ", ".join(prerrequisitos) if prerrequisitos else "Ninguno"
    recursos = _obtener_recursos(catalogo, motor.grafo[nodo]["recursos"])
    return (
        f"### {tema}\n"
        f"**Estado:** {estado}  \n"
        f"**Prerrequisitos:** {requisitos}  \n"
        f"**Prerrequisitos pendientes:** {pendientes}\n\n"
        f"#### Recursos\n{recursos}"
    )


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

    colores = []
    for nodo in grafo.nodes:
        tema = NODO_A_TEMA[nodo]
        estado, _ = _estado_del_tema(motor, tema, completados)
        colores.append(
            "#63B77A" if estado == "Acreditado"
            else "#63A4E8" if estado == "Disponible"
            else "#C7CDD4"
        )
    bordes = [
        "#F39C12" if nodo == TEMA_A_NODO.get(seleccionado) else "#333333"
        for nodo in grafo.nodes
    ]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    nx.draw_networkx_edges(
        grafo, posicion, ax=ax, arrows=True, arrowsize=18, edge_color="#777777",
        node_size=7400,
    )
    nx.draw_networkx_nodes(
        grafo, posicion, ax=ax, node_color=colores, edgecolors=bordes,
        linewidths=2, node_size=7400,
    )
    etiquetas = {nodo: NODO_A_TEMA[nodo].replace(" ", "\n", 2) for nodo in grafo.nodes}
    nx.draw_networkx_labels(grafo, posicion, labels=etiquetas, ax=ax, font_size=8)
    ax.legend(
        handles=[
            Patch(color="#63B77A", label="Acreditado"),
            Patch(color="#63A4E8", label="Disponible"),
            Patch(color="#C7CDD4", label="Bloqueado"),
        ],
        loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.12),
    )
    ax.set_title("Grafo de conocimiento · borde naranja: tema seleccionado")
    ax.set_axis_off()
    fig.tight_layout()
    return fig


def _vista_ruta(motor: Any, catalogo: dict[str, dict[str, str]], estado: dict[str, Any]):
    recomendacion = estado["recomendacion"]
    completados = estado["completados"]
    temas = motor.temas
    porcentaje = round(100 * len(completados) / len(temas))
    ruta = recomendacion["ruta_pendiente"]
    pasos = "\n".join(
        f"{indice}. {tema}{' — siguiente recomendado' if indice == 1 else ''}"
        for indice, tema in enumerate(ruta, 1)
    )
    if not pasos:
        pasos = "_La meta está completada._"
    siguiente = recomendacion.get("siguiente_tema") or "Meta completada"
    ruta_md = (
        f"### Mi ruta de aprendizaje\n"
        f"**Meta:** {estado['perfil']['meta']}  \n"
        f"**Progreso global:** {len(completados)}/{len(temas)} temas ({porcentaje}%)  \n"
        f"**Siguiente tema recomendado:** {siguiente}  \n"
        f"**Estado de la meta:** {recomendacion['estado_meta']}\n\n"
        f"#### Pasos pendientes\n{pasos}\n\n"
        f"**Temas bloqueados:** "
        f"{', '.join(recomendacion.get('bloqueados', [])) or 'Ninguno'}"
    )
    seleccionado = siguiente if siguiente in temas else temas[0]
    figura = _dibujar_grafo(motor, completados, seleccionado)
    detalle = _detalle_tema(motor, catalogo, seleccionado, completados)
    return ruta_md, figura, detalle, gr.update(value=seleccionado)


def _actualizar_recomendacion(motor: Any, estado: dict[str, Any]) -> None:
    estado["recomendacion"] = motor.consultar(
        **estado["perfil"],
        completados=estado["completados"],
    )


def _persistir_perfil(perfil: dict[str, Any], completados: list[str]) -> dict[str, Any]:
    """Guarda preferencias y diagnósticos marcados, preservando el resto del avance."""
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
    # Los temas declarados en el diagnóstico quedan marcados con su origen.
    for tema in completados:
        guardado["temas_acreditados"].setdefault(tema, {
            "origen": "diagnóstico",
            "intento_id": f"diagnostico-{uuid4()}",
        })
    return store.guardar(guardado)


def _resultado_markdown(resultado: dict[str, Any], retroalimentacion=None) -> str:
    if resultado.get("tipo") == "poo":
        respondidos = resultado["respondidos"]
        return (
            "### Resultado de la práctica de POO\n"
            f"**Respuestas entregadas:** {respondidos}/4  \n"
            "**Estado:** recibido para revisión; esta práctica abierta no asigna "
            "una calificación automática.\n\n"
            "#### Lista de revisión\n"
            "- La clase tiene atributos adecuados y se crean objetos distintos.\n"
            "- Los métodos representan el comportamiento solicitado.\n"
            "- El encapsulamiento protege el estado y valida las operaciones.\n"
            "- Las dos clases colaboran mediante responsabilidades claras.\n\n"
            f"{renderizar_retroalimentacion(retroalimentacion)}"
        )

    acreditado = "Acreditado" if resultado["acreditado"] else "Pendiente de acreditación"
    if resultado["tipo"] == "laboratorio":
        correctas = resultado["ejercicios_correctos"]
        total = resultado["total_ejercicios"]
        detalle = resultado["detalle"]
    else:
        correctas = resultado["correctas"]
        total = resultado["total_preguntas"]
        detalle = resultado["detalle"]
    lineas = [
        f"### Resultado: {acreditado}",
        f"**Puntaje:** {correctas} / {total} ({resultado['puntaje']:.0%})  ",
        f"**Tema:** {NODO_A_TEMA.get(resultado['tema'], resultado['tema'])}",
    ]
    if resultado.get("variante"):
        lineas.append(f"**Variante:** {resultado['variante']}")
    lineas.extend(["", "#### Revisión por pregunta"])
    for item in detalle:
        estado = "Correcta" if item["correcto"] else "Revisar"
        lineas.append(f"- **{item.get('id', item.get('concepto'))}:** {estado}")
        if item.get("error"):
            lineas.append(f"  - {item['error']}")
    if resultado.get("conceptos_con_errores"):
        lineas.extend([
            "",
            "**Conceptos para repasar:** " + ", ".join(resultado["conceptos_con_errores"]),
        ])
    if resultado["acreditado"]:
        lineas.extend(["", "La ruta se actualizó con el tema acreditado."])
    lineas.extend(["", renderizar_retroalimentacion(retroalimentacion)])
    return "\n".join(lineas)


def construir_interfaz(motor: Any) -> gr.Blocks:
    """Construye la navegación, la ruta, el grafo y los formularios de actividad."""
    catalogo = _cargar_catalogo()
    banco_poo = _cargar_json(_RUTA_POO)
    ejercicios_lab = obtener_ejercicios_laboratorio()
    estado_inicial = _estado_inicial(motor)
    progreso_activo = estado_inicial["simulacion_activa"]

    with gr.Blocks(title="Rutas de aprendizaje · Proyecto Integrador") as demo:
        estado = gr.State(estado_inicial)
        gr.Markdown(
            "# Recomendador de rutas de aprendizaje\n"
            "Consulta una ruta personalizada, estudia recursos y completa actividades. "
            "Las recomendaciones usan datos simulados y son material de apoyo."
        )
        with gr.Tabs(selected="inicio") as navegacion:
            with gr.Tab("Inicio", id="inicio"):
                gr.Markdown(
                    "## Bienvenido\n"
                    "Comienza con tu diagnóstico para crear una ruta personalizada. "
                    "Desde **Mi ruta** podrás revisar el progreso y abrir recursos."
                )
                resumen_inicio = gr.Markdown(
                    f"Progreso local recuperado: {len(estado_inicial['intentos'])} intento(s), "
                    f"{len(estado_inicial['completados'])} tema(s) acreditado(s)."
                    + (f"\n\n**Error de lectura:** {estado_inicial['error_progreso']}" if estado_inicial.get("error_progreso") else "")
                )
                iniciar = gr.Button(
                    "Continuar aprendizaje" if progreso_activo else "Iniciar simulación",
                    variant="primary",
                )
                reiniciar_simulacion = gr.Button("Reiniciar simulación", variant="stop")
            with gr.Tab("Diagnóstico", id="diagnostico"):
                gr.Markdown("## Perfil de aprendizaje")
                with gr.Row():
                    nivel = gr.Radio(NIVELES, value=estado_inicial["perfil"]["nivel"], label="Nivel previo")
                    formato = gr.Radio(FORMATOS, value=estado_inicial["perfil"]["formato"], label="Formato preferido")
                with gr.Row():
                    tema = gr.Dropdown(motor.temas, value=estado_inicial["perfil"]["tema"], label="Tema actual")
                    meta = gr.Dropdown(
                        motor.temas, value=estado_inicial["perfil"]["meta"], label="Meta de aprendizaje",
                    )
                with gr.Row():
                    tiempo = gr.Slider(5, 300, value=estado_inicial["perfil"]["tiempo"], step=1, label="Tiempo de interacción (s)")
                    errores = gr.Slider(0, 100, value=estado_inicial["perfil"]["errores"], step=1, label="Tasa de errores (%)")
                with gr.Row():
                    completados = gr.CheckboxGroup(
                        motor.temas, value=estado_inicial["completados"], label="Temas ya acreditados",
                    )
                    fallos = gr.Slider(0, 6, value=estado_inicial["perfil"]["fallos"], step=1, label="Fallos consecutivos")
                    abandono = gr.Checkbox(value=estado_inicial["perfil"]["abandono"], label="Abandonó la actividad")
                diagnosticar = gr.Button("Generar / actualizar mi ruta", variant="primary")
                estado_diagnostico = gr.Markdown()

            with gr.Tab("Mi ruta", id="ruta"):
                resumen_ruta = gr.Markdown()
                grafo = gr.Plot(label="Grafo de conocimiento")
                tema_grafo = gr.Dropdown(
                    motor.temas, value=motor.temas[0], label="Explorar un tema del grafo",
                )
                detalle_grafo = gr.Markdown()
                actualizar_ruta = gr.Button("Actualizar ruta")

            with gr.Tab("Actividad", id="actividad"):
                gr.Markdown(
                    "## Actividades\n"
                    "Selecciona la práctica. El laboratorio y el seguimiento PostgreSQL "
                    "se califican automáticamente; la práctica de POO se entrega para revisión."
                )
                tipo_actividad = gr.Radio(
                    ["POO · clases y objetos", "PostgreSQL · laboratorio", "PostgreSQL · seguimiento"],
                    label="Actividad",
                    value=None,
                )
                instrucciones = gr.Markdown()

                with gr.Group(visible=False) as grupo_poo:
                    gr.Markdown("### Programación Orientada a Objetos · ejercicios asignados")
                    respuestas_poo = []
                    for ejercicio in banco_poo["ejercicios"]:
                        gr.Markdown(
                            f"**{ejercicio['id']} · {ejercicio['concepto']} — "
                            f"{ejercicio['titulo']}**\n\n{ejercicio['enunciado']}"
                        )
                        respuestas_poo.append(
                            gr.Textbox(lines=4, label=f"Respuesta {ejercicio['id']}")
                        )
                    enviar_poo = gr.Button("Entregar práctica POO", variant="primary")

                with gr.Group(visible=False) as grupo_laboratorio:
                    gr.Markdown("### Laboratorio PostgreSQL · cuatro ejercicios")
                    respuestas_lab = []
                    for ejercicio in ejercicios_lab:
                        gr.Markdown(
                            f"**{ejercicio['id']} · {ejercicio['concepto']} "
                            f"({ejercicio['dificultad']})**\n\n{ejercicio['enunciado']}"
                        )
                        respuestas_lab.append(
                            gr.Textbox(lines=3, label=f"Consulta SQL · {ejercicio['id']}")
                        )
                    enviar_lab = gr.Button("Calificar laboratorio", variant="primary")

                with gr.Group(visible=False) as grupo_seguimiento:
                    gr.Markdown("### Seguimiento PostgreSQL · cinco preguntas")
                    preguntas_seg = []
                    respuestas_seg = []
                    for indice in range(5):
                        preguntas_seg.append(gr.Markdown())
                        respuestas_seg.append(
                            gr.Radio([], label=f"Respuesta {indice + 1}")
                        )
                    enviar_seg = gr.Button("Calificar seguimiento", variant="primary")

            with gr.Tab("Resultados", id="resultados"):
                resultados = gr.Markdown(
                    "Aún no hay resultados. Completa una actividad para ver aquí el resumen."
                )
                with gr.Row():
                    volver_ruta = gr.Button("Volver a Mi ruta")
                    reintentar = gr.Button("Reintentar / elegir otra actividad")

        def abrir_inicio(estado_actual):
            if not estado_actual.get("simulacion_activa"):
                return gr.update(selected="diagnostico"), gr.update(), gr.update(), gr.update(), gr.update()
            md, figura, detalle, tema_update = _vista_ruta(motor, catalogo, estado_actual)
            return gr.update(selected="ruta"), md, figura, detalle, tema_update

        iniciar.click(
            fn=abrir_inicio, inputs=estado,
            outputs=[navegacion, resumen_ruta, grafo, detalle_grafo, tema_grafo],
        )

        def reiniciar_desde_interfaz():
            simulacion.reiniciar()
            nuevo = _estado_inicial(motor)
            return (
                nuevo, gr.update(selected="inicio"), "Progreso local: 0 intentos, 0 temas acreditados.",
                "Selecciona una meta y comienza.", gr.update(value=None), "",
                gr.update(value=motor.temas[0]), gr.update(value=[]),
                gr.update(value="Iniciar simulación"),
                gr.update(value="Principiante"), gr.update(value="Visual"),
                gr.update(value=motor.temas[0]), gr.update(value="Backend con Node.js"),
                gr.update(value=120), gr.update(value=50), gr.update(value=0),
                gr.update(value=False),
            )

        reiniciar_simulacion.click(
            fn=reiniciar_desde_interfaz,
            outputs=[estado, navegacion, resumen_inicio, resumen_ruta, grafo,
                     detalle_grafo, tema_grafo, completados, iniciar, nivel,
                     formato, tema, meta, tiempo, errores, fallos, abandono],
        )

        def generar_ruta(
            nivel_valor, formato_valor, tema_valor, tiempo_valor, errores_valor,
            completados_valor, meta_valor, fallos_valor, abandono_valor, estado_actual,
        ):
            nuevo = dict(estado_actual)
            nuevo["perfil"] = {
                "nivel": nivel_valor,
                "formato": formato_valor,
                "tema": tema_valor,
                "tiempo": tiempo_valor,
                "errores": errores_valor,
                "meta": meta_valor,
                "fallos": int(fallos_valor),
                "abandono": bool(abandono_valor),
            }
            try:
                guardado = _persistir_perfil(
                    nuevo["perfil"],
                    sorted(set(completados_valor or []) | set(nuevo["completados"])),
                )
            except (ErrorProgreso, ValueError) as exc:
                return (estado_actual, gr.update(), gr.update(), gr.update(), gr.update(),
                        f"No se guardó el perfil ni se actualizó el progreso: {exc}")
            nuevo["completados"] = temas_acreditados(guardado)
            nuevo["intentos"] = guardado["intentos"]
            nuevo["simulacion_activa"] = True
            _actualizar_recomendacion(motor, nuevo)
            md, figura, detalle, tema_update = _vista_ruta(motor, catalogo, nuevo)
            return (
                nuevo, md, figura, detalle, tema_update,
                f"Ruta actualizada. Siguiente tema: **{nuevo['recomendacion'].get('siguiente_tema') or 'Meta completada'}**.",
            )

        diagnosticar.click(
            fn=generar_ruta,
            inputs=[
                nivel, formato, tema, tiempo, errores, completados, meta, fallos,
                abandono, estado,
            ],
            outputs=[
                estado, resumen_ruta, grafo, detalle_grafo, tema_grafo,
                estado_diagnostico,
            ],
        )
        actualizar_ruta.click(
            fn=lambda actual: _vista_ruta(motor, catalogo, actual),
            inputs=estado,
            outputs=[resumen_ruta, grafo, detalle_grafo, tema_grafo],
        )

        def mostrar_tema(tema_valor, estado_actual):
            return (
                _detalle_tema(motor, catalogo, tema_valor, estado_actual["completados"]),
                _dibujar_grafo(motor, estado_actual["completados"], tema_valor),
            )

        tema_grafo.change(
            fn=mostrar_tema,
            inputs=[tema_grafo, estado],
            outputs=[detalle_grafo, grafo],
        )

        def seleccionar_actividad(seleccion, estado_actual):
            nuevo = dict(estado_actual)
            nuevo["tipo_actividad"] = seleccion
            nuevo["inicio_actividad"] = time.monotonic() if seleccion else None
            nuevo["variante_activa"] = None
            visibilidad = [
                gr.update(visible=seleccion == "POO · clases y objetos"),
                gr.update(visible=seleccion == "PostgreSQL · laboratorio"),
                gr.update(visible=seleccion == "PostgreSQL · seguimiento"),
            ]
            prompts = [gr.update(value="") for _ in range(5)]
            radios = [gr.update(choices=[], value=None) for _ in range(5)]
            if seleccion == "POO · clases y objetos":
                instruccion = "Responde los cuatro ejercicios. La entrega se acompaña de una lista de revisión, no de una nota automática."
            elif seleccion == "PostgreSQL · laboratorio":
                instruccion = "Resuelve los cuatro ejercicios SQL. El calificador verificará los resultados y la regla de acreditación."
            elif seleccion == "PostgreSQL · seguimiento":
                try:
                    variante, preguntas = obtener_variante_seguimiento(
                        nuevo["variantes_usadas"]
                    )
                except ValueError as exc:
                    instruccion = f"**No se puede iniciar el seguimiento:** {exc}"
                else:
                    nuevo["variante_activa"] = variante
                    for indice, pregunta in enumerate(preguntas):
                        prompts[indice] = gr.update(
                            value=f"**{pregunta['id']} · {pregunta['concepto']}**\n\n{pregunta['enunciado']}"
                        )
                        radios[indice] = gr.update(
                            choices=pregunta["opciones"], value=None,
                        )
                    instruccion = f"Variante asignada: **{variante}**. Se selecciona una variante no utilizada anteriormente."
            else:
                instruccion = "Selecciona una actividad para mostrar sus ejercicios."
            return (*visibilidad, *prompts, *radios, instruccion, nuevo)

        seleccion_outputs = [
            grupo_poo, grupo_laboratorio, grupo_seguimiento,
            *preguntas_seg, *respuestas_seg, instrucciones, estado,
        ]
        tipo_actividad.change(
            fn=seleccionar_actividad,
            inputs=[tipo_actividad, estado],
            outputs=seleccion_outputs,
        )

        def registrar_resultado(resultado, estado_actual):
            try:
                if resultado.get("tipo") == "poo":
                    persistible = {
                        "id": str(uuid4()),
                        "tema": "Programación Orientada a Objetos",
                        "tipo_actividad": "Práctica POO",
                        "puntaje": resultado["respondidos"],
                        "puntaje_maximo": resultado["total"],
                        "tiempo_segundos": 0,
                        "conceptos_con_error": [],
                        "aprobado": False,
                        "detalle": resultado.get("detalle", []),
                    }
                else:
                    persistible = normalizar_resultado_calificador(resultado)
                guardado = simulacion.persistir_intento(persistible)
            except (ErrorProgreso, ValueError, TypeError, OverflowError) as exc:
                md_ruta, figura, detalle, tema_update = _vista_ruta(
                    motor, catalogo, estado_actual
                )
                return (
                    estado_actual, f"## No se guardó el resultado\n\n{exc}",
                    md_ruta, figura, detalle, tema_update,
                    gr.update(value=estado_actual["completados"]),
                    gr.update(selected="resultados"),
                )

            nuevo = dict(estado_actual)
            nuevo["completados"] = temas_acreditados(guardado)
            nuevo["intentos"] = guardado["intentos"]
            nuevo["variantes_usadas"] = [
                item["variante"] for item in guardado["intentos"]
                if item.get("variante")
            ]
            nuevo["simulacion_activa"] = guardado["simulacion_activa"]
            nuevo["resultado"] = resultado
            _actualizar_recomendacion(motor, nuevo)
            md_ruta, figura, detalle, tema_update = _vista_ruta(motor, catalogo, nuevo)
            return (
                nuevo, _resultado_markdown(resultado, resultado.get("retroalimentacion")), md_ruta, figura, detalle,
                tema_update, gr.update(value=nuevo["completados"]),
                gr.update(selected="resultados"),
            )

        def entregar_poo(*valores):
            estado_actual = valores[-1]
            respuestas = [str(respuesta or "").strip() for respuesta in valores[:-1]]
            resultado = {
                "tipo": "poo",
                "respondidos": sum(bool(respuesta) for respuesta in respuestas),
                "total": len(respuestas),
                "acreditado": False,
                "detalle": [
                    {"id": f"POO-{indice + 1:02d}", "respuesta": respuesta}
                    for indice, respuesta in enumerate(respuestas)
                ],
            }
            return registrar_resultado(resultado, estado_actual)

        def calificar_lab(*valores):
            estado_actual = valores[-1]
            respuestas = {
                ejercicio["id"]: respuesta or ""
                for ejercicio, respuesta in zip(ejercicios_lab, valores[:-1])
            }
            inicio = estado_actual.get("inicio_actividad") or time.monotonic()
            resultado = calificar_laboratorio(
                respuestas, tiempo=max(0.0, time.monotonic() - inicio),
            )
            return registrar_resultado(resultado, estado_actual)

        def calificar_seg(*valores):
            estado_actual = valores[-1]
            variante = estado_actual.get("variante_activa")
            if not variante:
                raise ValueError("Selecciona una variante de seguimiento antes de calificar.")
            variante_actual, preguntas = obtener_variante_seguimiento(
                estado_actual["variantes_usadas"]
            )
            if variante_actual != variante:
                raise ValueError("La variante activa no coincide con la siguiente variante disponible.")
            respuestas = {
                pregunta["id"]: respuesta or ""
                for pregunta, respuesta in zip(preguntas, valores[:-1])
            }
            resultado = calificar_seguimiento(
                respuestas,
                tiempo=max(
                    0.0,
                    time.monotonic() - (estado_actual.get("inicio_actividad") or time.monotonic()),
                ),
                variante_usada=variante,
            )
            nuevo = dict(estado_actual)
            nuevo["variantes_usadas"] = list(nuevo["variantes_usadas"]) + [variante]
            return registrar_resultado(resultado, nuevo)

        resultado_outputs = [
            estado, resultados, resumen_ruta, grafo, detalle_grafo, tema_grafo,
            completados, navegacion,
        ]
        enviar_poo.click(
            fn=entregar_poo,
            inputs=[*respuestas_poo, estado],
            outputs=resultado_outputs,
        )
        enviar_lab.click(
            fn=calificar_lab,
            inputs=[*respuestas_lab, estado],
            outputs=resultado_outputs,
        )
        enviar_seg.click(
            fn=calificar_seg,
            inputs=[*respuestas_seg, estado],
            outputs=resultado_outputs,
        )

        volver_ruta.click(
            fn=lambda: gr.update(selected="ruta"),
            outputs=navegacion,
        )
        reintentar.click(
            fn=lambda: (gr.update(selected="actividad"), gr.update(value=None)),
            outputs=[navegacion, tipo_actividad],
        )

    return demo
