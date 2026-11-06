"""Composición y navegación visual; las respuestas conservan sus eventos originales."""
from __future__ import annotations

import gradio as gr

from ui import vistas


class VistaActividad:
    """Muestra un ejercicio a la vez sin recrear ni vaciar sus controles."""

    def __init__(self, titulo, items, montar_respuesta, texto_envio,
                 montar_ayuda=None, seguimiento=False):
        self.items = items
        self.seguimiento = seguimiento
        self.paginas = []
        self.ayudas = []
        self.respuestas = []
        self.tamanos = []
        self.indice = gr.State(0)
        etiqueta = "Pregunta" if seguimiento else "Ejercicio"
        gr.HTML(
            '<header class="activity-lead">'
            f'<p class="activity-eyebrow">{etiqueta}s · práctica</p>'
            f'<h2>{vistas.e(titulo)}</h2>'
            '<p class="activity-caption">Responde a tu ritmo. Puedes volver a los pasos anteriores.</p>'
            '</header>'
        )
        with gr.Row(elem_classes=["activity-layout"]):
            with gr.Column(min_width=0, elem_classes=["activity-card", "activity-main"]):
                for numero, item in enumerate(items):
                    with gr.Group(visible=numero == 0, elem_classes=["activity-question"]) as pagina:
                        gr.HTML(f'<p class="activity-meta">{etiqueta} {numero + 1} de {len(items)}</p>')
                        controles = montar_respuesta(item, numero)
                        self.respuestas.extend(controles)
                        self.tamanos.append(len(controles))
                    self.paginas.append(pagina)
                with gr.Row(elem_classes=["activity-actions"]):
                    self.anterior = gr.Button("Anterior", interactive=False, scale=0)
                    self.siguiente = gr.Button("Siguiente", variant="primary", scale=0)
                with gr.Row(elem_classes=["activity-submit"]):
                    self.enviar = gr.Button(texto_envio, variant="primary")
            with gr.Column(min_width=0, elem_classes=["activity-sidebar"]):
                with gr.Group(elem_classes=["activity-card", "activity-progress"]):
                    self.avance = gr.HTML(self._avance(0, [None] * len(self.respuestas)))
                if montar_ayuda:
                    for numero, item in enumerate(items):
                        with gr.Group(visible=numero == 0, elem_classes=["activity-card", "activity-help"]) as ayuda:
                            montar_ayuda(item)
                        self.ayudas.append(ayuda)

        self.salidas = [self.indice, *self.paginas, *self.ayudas,
                        self.anterior, self.siguiente, self.avance]
        entradas = [self.indice, *self.respuestas]
        self.anterior.click(
            lambda indice, *valores: self._mostrar(indice - 1, valores),
            entradas, self.salidas, show_progress="hidden",
        )
        self.siguiente.click(
            lambda indice, *valores: self._mostrar(indice + 1, valores),
            entradas, self.salidas, show_progress="hidden",
        )
        for control in self.respuestas:
            control.input(
                lambda indice, *valores: self._avance(indice, valores),
                entradas, self.avance, show_progress="hidden",
            )

    def _avance(self, indice, valores):
        respondidos = []
        inicio = 0
        for cantidad in self.tamanos:
            respondidos.append(all(str(v or "").strip() for v in valores[inicio:inicio + cantidad]))
            inicio += cantidad
        return vistas.actividad_avance_html(respondidos, indice, self.seguimiento)

    def _mostrar(self, indice, valores):
        indice = max(0, min(int(indice), len(self.items) - 1))
        return (
            indice,
            *(gr.update(visible=i == indice) for i in range(len(self.paginas))),
            *(gr.update(visible=i == indice) for i in range(len(self.ayudas))),
            gr.update(interactive=indice > 0),
            gr.update(interactive=indice < len(self.items) - 1),
            self._avance(indice, valores),
        )

    def reiniciar_navegacion(self, *valores):
        # La selección original decide qué respuestas reiniciar y qué variante cargar.
        return self._mostrar(0, valores)
