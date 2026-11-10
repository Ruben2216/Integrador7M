"""Datos simulados de presentación: no llaman a Gemini ni guardan progreso."""
from html import escape
from html.parser import HTMLParser

import pytest

from ui.resultados import renderizar_retroalimentacion, solicitud_explicacion_html


class Documento(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.etiquetas = []
        self.textos = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.etiquetas.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.textos.append(data)


@pytest.mark.parametrize("datos", [None, {}, [], {"acierto": None, "mejora": "  ", "pista": []},
                                         {"acierto": {}, "mejora": 4, "pista": False}])
def test_campos_invalidos_no_inventan_secciones(datos):
    html = renderizar_retroalimentacion(datos)
    assert "No hay una explicación disponible para este intento." in html
    assert 'class="feedback-section"' not in html
    assert 'class="feedback-resource"' not in html


@pytest.mark.parametrize("origen,etiqueta", [("gemini", "Generada con IA"),
    ("local", "Basada en la rúbrica"), (None, None), ("otro", None), ({}, None)])
def test_origen_solo_del_dato_real(origen, etiqueta):
    html = renderizar_retroalimentacion({"origen": origen, "acierto": "Texto recibido"})
    assert ('class="feedback-origin"' in html) is bool(etiqueta)
    if etiqueta:
        assert etiqueta in html


@pytest.mark.parametrize("datos", [
    {"acierto": "Resolviste todos los criterios.", "mejora": "No hay criterios pendientes.", "pista": "Continúa."},
    {"acierto": "Identificaste la condición.", "mejora": "Revisa el ciclo.", "pista": "Prueba cero."},
    {"acierto": "No se registraron criterios cumplidos.", "mejora": "Revisa las condiciones."},
    {"acierto": "Actividad entregada.", "mejora": "Contrasta tus respuestas con la lista de revisión."},
])
def test_no_reinterpreta_perfecto_errores_sin_aciertos_o_practica(datos):
    html = renderizar_retroalimentacion(datos)
    for campo, texto in datos.items():
        assert escape(texto) in html
    assert "aprobada" not in html and "dominas" not in html


def test_campos_independientes_y_orden_de_claves():
    datos = {"pista": "Paso recibido", "acierto": " ", "mejora": "Mejora recibida"}
    html = renderizar_retroalimentacion(datos)
    assert "Lo que hiciste bien" not in html
    assert html.index("Qué puedes reforzar") < html.index("Tu siguiente paso")
    assert html == renderizar_retroalimentacion(dict(reversed(list(datos.items()))))


def test_respaldo_y_modelo_solo_en_detalles_cerrados():
    html = renderizar_retroalimentacion({"origen": "local", "motivo_respaldo": "HTTP 503 <error>",
                                       "modelo": "modelo-tecnico", "acierto": "Acierto recibido"})
    assert "Mostramos la retroalimentación de la rúbrica." in html
    previo, tecnico = html.split('<details class="feedback-details">')
    assert "HTTP 503" not in previo and "modelo-tecnico" not in previo
    assert "HTTP 503 &lt;error&gt;" in tecnico
    doc = Documento(html)
    assert all("open" not in attrs for tag, attrs in doc.etiquetas if tag == "details")
    local = renderizar_retroalimentacion({"origen": "local", "acierto": "Texto recibido"})
    assert 'role="status"' not in local


@pytest.mark.parametrize("recurso", [None, {}, {"id": "x"}, {"titulo": " "}, {"fuente": []}])
def test_recurso_sin_datos_se_omite(recurso):
    assert "Material recomendado" not in renderizar_retroalimentacion({"recurso": recurso})


@pytest.mark.parametrize("recurso", [
    {"titulo": "Referencia", "fuente": "Python Documentation", "formato": "Lectura",
     "enlace": "https://docs.python.org/3/tutorial/controlflow.html?a=1&b=2"},
    {"titulo": "Referencia sin enlace"}, {"fuente": "Fuente disponible"}, "Recurso de texto heredado",
])
def test_recursos_completos_e_incompletos(recurso):
    html = renderizar_retroalimentacion({"recurso": recurso})
    assert "Material recomendado" in html and "Documentación oficial" not in html
    enlaces = [attrs for tag, attrs in Documento(html).etiquetas if tag == "a"]
    if isinstance(recurso, dict) and recurso.get("enlace"):
        assert enlaces[0]["href"] == recurso["enlace"]
        assert enlaces[0]["rel"] == "noopener noreferrer"
    else:
        assert not enlaces


@pytest.mark.parametrize("url", ['javascript:alert(1)', 'data:text/html,<script>alert(1)</script>',
    '//example.org', 'https://', 'https://[', 'https://example.org/\nfoo', None, {}])
def test_enlaces_no_utilizables_sin_boton_vacio(url):
    html = renderizar_retroalimentacion({"recurso": {"titulo": "Se conserva el título", "enlace": url}})
    assert "Se conserva el título" in html and "Abrir recurso" not in html


def test_html_y_markdown_no_inyectan_codigo():
    ataque = '<script>alert(1)</script><img src=x onerror="alert(2)"> & á >\n[javascript](javascript:alert(3))'
    datos = {c: ataque for c in ("acierto", "mejora", "pista", "modelo", "motivo_respaldo", "tema")}
    datos["recurso"] = {"titulo": ataque, "fuente": ataque, "formato": ataque}
    html = renderizar_retroalimentacion(datos)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    for tag, attrs in Documento(html).etiquetas:
        assert tag not in ("script", "img", "iframe")
        assert not any(nombre.startswith("on") for nombre in attrs)


def test_texto_largo_y_saltos_se_conservan_completos():
    texto = ("Condición y ciclo: < > & ñ.\n\n" * 350) + "FINAL VISIBLE"
    html = renderizar_retroalimentacion({"acierto": texto})
    assert html.count("Condición y ciclo: &lt; &gt; &amp; ñ.") == 350
    assert "FINAL VISIBLE" in html


def test_markdown_controlado_conserva_enfasis_codigo_y_parrafos():
    html = renderizar_retroalimentacion({"pista": "**Comprueba** `n == 0`.\n\nDespués, repite."})
    assert "<strong>Comprueba</strong>" in html and "<code>n == 0</code>" in html
    assert "<p>Después, repite.</p>" in html


def test_solicitud_inicial_sin_resultados_ficticios():
    html = solicitud_explicacion_html("configuracion-tecnica")
    assert "Retroalimentación de tu actividad" in html
    assert "Solicita una explicación para comprender tus aciertos y lo que puedes reforzar." in html
    assert "Tu resultado ya está guardado." in html
    assert "Material recomendado" not in html and "Lo que hiciste bien" not in html
    assert 'class="feedback-details"' in html and " open" not in html
