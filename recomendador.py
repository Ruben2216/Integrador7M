"""
Sistema de recomendación personalizada de recursos y rutas de aprendizaje.
Prototipo funcional del componente inteligente.

Componentes de IA (ejecución local, sin clave de API):
  1. Árbol de decisión (scikit-learn)  -> clasifica el tipo de apoyo: Refuerzo / Avanzado
  2. Grafo de conocimiento + búsqueda A* (networkx / heapq) -> ruta de aprendizaje
  3. Reglas de producción SI-ENTONCES  -> ajustes por fallos repetidos, abandono, prerrequisitos
  4. Filtrado basado en contenido      -> ordena recursos según el formato preferido

Datos: telemetría simulada. No corresponde a registros reales de estudiantes.
"""
import heapq
import itertools
import json

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder
from sklearn.tree import DecisionTreeClassifier

# --------------------------------------------------------------------------
# 0. Parámetros y correspondencias
# --------------------------------------------------------------------------
NIVELES = ["Principiante", "Intermedio", "Avanzado"]
FORMATOS = ["Visual", "Texto", "Práctico"]

# El CSV usa nombres legibles y el JSON del grafo usa claves con guion bajo.
TEMA_A_NODO = {
    "Lógica de Programación": "Logica_de_Programacion",
    "Programación Orientada a Objetos": "Programacion_Orientada_a_Objetos",
    "Bases de Datos PostgreSQL": "Bases_de_Datos_PostgreSQL",
    "Backend con Node.js": "Backend_con_Nodejs",
    "Patrón MVC en PHP": "Patron_MVC_en_PHP",
}
NODO_A_TEMA = {v: k for k, v in TEMA_A_NODO.items()}

# Formato preferido (CSV) -> tipo de recurso (JSON)
FORMATO_A_RECURSO = {"Visual": "Video", "Texto": "Lectura", "Práctico": "Practica"}
# Si el tema no tiene recurso en el formato preferido, orden de sustitución
SUSTITUTOS = {
    "Visual": ["Práctico", "Texto"],
    "Texto": ["Visual", "Práctico"],
    "Práctico": ["Visual", "Texto"],
}

# Parámetros de diseño (fijados manualmente, no aprendidos): esfuerzo base por
# tema y factor según el nivel del estudiante. Determinan el costo en el algoritmo A*.
DIFICULTAD = {
    "Logica_de_Programacion": 2,
    "Programacion_Orientada_a_Objetos": 3,
    "Bases_de_Datos_PostgreSQL": 3,
    "Backend_con_Nodejs": 4,
    "Patron_MVC_en_PHP": 3,
}
FACTOR_NIVEL = {"Principiante": 1.5, "Intermedio": 1.0, "Avanzado": 0.7}

# Umbrales de las reglas de producción
UMBRAL_FALLOS = 2          # SI fallas_repetidas > 2 ENTONCES retroceder
UMBRAL_TIEMPO_BAJO = 30    # SI tiempo < 30 s Y abandono ENTONCES evitar textos largos


# --------------------------------------------------------------------------
# 1. Datos y preprocesamiento
# --------------------------------------------------------------------------
def cargar_datos(ruta_csv):
    """Lee el CSV simulado y deriva el tipo de apoyo (primer token del ID)."""
    df = pd.read_csv(ruta_csv)
    # 'Avanzado_Visual_LÓGI' -> 'Avanzado' ; 'Refuerzo_Texto_BACK' -> 'Refuerzo'
    df["Tipo_Apoyo"] = df["Recurso_Recomendado_ID"].str.split("_").str[0]
    return df


def construir_preprocesador():
    """Preprocesamiento: imputación de nulos, codificación ordinal y one-hot."""
    return ColumnTransformer([
        # El tiempo de interacción presenta ~5 % de nulos -> imputación con la mediana
        ("tiempo", SimpleImputer(strategy="median"), ["Tiempo_Interaccion_Segundos"]),
        ("errores", "passthrough", ["Tasa_Errores"]),
        # El nivel posee un orden natural
        ("nivel", OrdinalEncoder(categories=[NIVELES]), ["Nivel_Previo"]),
        # Formato y tema son nominales -> one-hot (sin orden artificial)
        ("cat", OneHotEncoder(categories=[FORMATOS, list(TEMA_A_NODO)],
                              handle_unknown="ignore"),
         ["Formato_Preferido", "Tema_Actual"]),
    ])


COLUMNAS_X = ["Nivel_Previo", "Formato_Preferido", "Tema_Actual",
              "Tiempo_Interaccion_Segundos", "Tasa_Errores"]


def construir_modelo(max_depth=4):
    """Pipeline = preprocesamiento + árbol de decisión (COMPONENTE DE IA #1)."""
    return Pipeline([
        ("prep", construir_preprocesador()),
        ("arbol", DecisionTreeClassifier(max_depth=max_depth, random_state=42)),
    ])


def entrenar(df, max_depth=4):
    """Entrena con 80 % y evalúa con 20 % estratificado. Devuelve modelo final
    (entrenado con todo), el modelo de evaluación y los conjuntos de prueba."""
    X, y = df[COLUMNAS_X], df["Tipo_Apoyo"]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)
    modelo_eval = construir_modelo(max_depth).fit(X_tr, y_tr)
    modelo_final = construir_modelo(max_depth).fit(X, y)
    return modelo_final, modelo_eval, (X_tr, X_te, y_tr, y_te)


# --------------------------------------------------------------------------
# 2. Grafo de conocimiento + búsqueda A*
# --------------------------------------------------------------------------
def cargar_grafo(ruta_json):
    """Devuelve (dict del JSON, lista de aristas prerrequisito -> tema)."""
    with open(ruta_json, encoding="utf-8") as f:
        grafo = json.load(f)
    aristas = [(p, t) for t, d in grafo.items() for p in d["prerrequisitos"]]
    return grafo, aristas


def ancestros(grafo, nodo):
    """Todos los prerrequisitos directos e indirectos de un nodo."""
    vistos, pila = set(), list(grafo[nodo]["prerrequisitos"])
    while pila:
        n = pila.pop()
        if n not in vistos:
            vistos.add(n)
            pila.extend(grafo[n]["prerrequisitos"])
    return vistos


def desbloqueados(grafo, completados):
    """Temas aún no completados cuyos prerrequisitos ya están cumplidos."""
    return [n for n, d in grafo.items()
            if n not in completados and all(p in completados for p in d["prerrequisitos"])]


def costo_tema(nodo, nivel):
    return DIFICULTAD[nodo] * FACTOR_NIVEL[nivel]


def ruta_a_estrella(grafo, completados, meta, nivel):
    """
    Búsqueda A* en el espacio de estados.
      Estado   : conjunto de temas completados.
      Acción   : estudiar un tema desbloqueado.
      Costo g  : suma del esfuerzo (dificultad * factor de nivel).
      Heurística h: (# de temas faltantes para la meta) * (costo mínimo entre ellos).
                    Es admisible porque cada tema faltante cuesta al menos ese mínimo.
    Devuelve (ruta, costo_total, estados_explorados).
    """
    inicio = frozenset(completados)
    if meta in inicio:
        return [], 0.0, 0
    necesarios = (ancestros(grafo, meta) | {meta}) - inicio
    costo_min = min(costo_tema(n, nivel) for n in necesarios)

    def h(estado):
        faltan = necesarios - estado
        return len(faltan) * costo_min

    contador = itertools.count()               # desempate estable
    frontera = [(h(inicio), next(contador), 0.0, inicio, [])]
    mejor_g = {inicio: 0.0}
    explorados = 0
    while frontera:
        _, _, g, estado, ruta = heapq.heappop(frontera)
        explorados += 1
        if meta in estado:
            return ruta, round(g, 2), explorados
        # Solo expande temas útiles para la meta; ordena por costo para desempatar
        for n in sorted(desbloqueados(grafo, estado), key=lambda x: costo_tema(x, nivel)):
            if n not in necesarios:
                continue
            nuevo = estado | {n}
            g2 = g + costo_tema(n, nivel)
            if g2 < mejor_g.get(nuevo, float("inf")):
                mejor_g[nuevo] = g2
                heapq.heappush(frontera, (g2 + h(nuevo), next(contador), g2, nuevo, ruta + [n]))
    return None, float("inf"), explorados


# --------------------------------------------------------------------------
# 3. Sistema completo: IA + reglas + recomendación de recursos
# --------------------------------------------------------------------------
class Recomendador:
    def __init__(self, ruta_csv, ruta_json, max_depth=4):
        self.df = cargar_datos(ruta_csv)
        self.grafo, self.aristas = cargar_grafo(ruta_json)
        self.modelo, self.modelo_eval, self.particion = entrenar(self.df, max_depth)

    # ---- recursos disponibles de un tema, por formato ----
    def recursos_por_formato(self, nodo):
        res = {}
        for r in self.grafo[nodo]["recursos"]:
            tipo = r.split("_")[1]                     # Video / Lectura / Practica
            for fmt, t in FORMATO_A_RECURSO.items():
                if t == tipo:
                    res[fmt] = r
        return res

    def ordenar_recursos(self, nodo, formato, evitar_texto=False):
        """Filtrado basado en contenido: puntúa cada recurso del tema."""
        disp = self.recursos_por_formato(nodo)
        puntajes = {}
        for fmt, rid in disp.items():
            if fmt == formato:
                p = 1.0
            else:
                p = 0.6 - 0.1 * SUSTITUTOS[formato].index(fmt)
            if evitar_texto and fmt == "Texto":
                p -= 0.5                                # regla de abandono
            puntajes[fmt] = (p, rid)
        orden = sorted(puntajes.items(), key=lambda kv: -kv[1][0])
        salida = []
        for i, (fmt, (p, rid)) in enumerate(orden):
            if i == 0 and fmt == formato:
                rol = "Principal (coincide con su formato preferido)"
            elif i == 0:
                rol = f"Principal (sustituto: el tema no tiene recurso en formato {formato})"
            else:
                rol = "Alternativa (diversificación contra burbuja de filtro)"
            salida.append({"recurso": rid, "formato": fmt, "puntaje": round(p, 2), "rol": rol})
        return salida

    # ---- inferencia principal ----
    def recomendar(self, nivel, formato, tema, tiempo, errores,
                   completados=(), meta="Backend con Node.js",
                   fallos=0, abandono=False):
        motivos, reglas = [], []
        nodo_actual = TEMA_A_NODO[tema]
        nodo_meta = TEMA_A_NODO[meta]
        comp = {TEMA_A_NODO[c] for c in completados}

        # (1) COMPONENTE DE IA #1 - árbol de decisión
        fila = pd.DataFrame([{
            "Nivel_Previo": nivel, "Formato_Preferido": formato, "Tema_Actual": tema,
            "Tiempo_Interaccion_Segundos": tiempo, "Tasa_Errores": errores}])
        tipo = self.modelo.predict(fila)[0]
        tipo_arbol = tipo
        proba = float(self.modelo.predict_proba(fila).max())
        motivos.append(f"El árbol de decisión clasificó el caso como «{tipo}» "
                       f"(confianza {proba:.0%}) con tasa de errores {errores:.0f} %.")

        # (2) Grafo: ¿el tema actual está desbloqueado?
        efectivo = nodo_actual
        if nodo_actual not in comp:
            faltan = [p for p in self.grafo[nodo_actual]["prerrequisitos"] if p not in comp]
            if faltan:
                ruta_pre, _, _ = ruta_a_estrella(self.grafo, comp, nodo_actual, nivel)
                efectivo = ruta_pre[0]
                reglas.append("R1: prerrequisitos pendientes → se redirige al primer tema "
                              "desbloqueado de la ruta.")
                motivos.append(
                    f"«{tema}» está bloqueado: faltan "
                    f"{', '.join(NODO_A_TEMA[f] for f in faltan)}. "
                    f"Se recomienda empezar por «{NODO_A_TEMA[efectivo]}».")

        accion = "Reforzar" if tipo == "Refuerzo" else "Avanzar"

        # (3) Reglas de producción
        if fallos > UMBRAL_FALLOS:
            pre = self.grafo[efectivo]["prerrequisitos"]
            if pre:
                efectivo = pre[0]
                accion = "Retroceder"
                tipo = "Refuerzo"
                reglas.append(f"R2: fallos repetidos ({fallos} > {UMBRAL_FALLOS}) → "
                              "recomendar_retroceso al prerrequisito.")
                motivos.append(f"Con {fallos} fallos seguidos se regresa a «{NODO_A_TEMA[efectivo]}» "
                               "para cubrir brechas de conocimiento.")
            else:
                accion = "Reforzar"
                reglas.append(f"R2: fallos repetidos ({fallos}) y el tema no tiene prerrequisitos → "
                              "reforzar el mismo tema.")
        evitar_texto = False
        if tiempo < UMBRAL_TIEMPO_BAJO and abandono:
            evitar_texto = True
            reglas.append(f"R3: tiempo < {UMBRAL_TIEMPO_BAJO} s y abandono → "
                          "ajustar_perfil(Evita_Textos_Largos).")
            motivos.append("Se detectó abandono con poco tiempo de interacción: se penalizan "
                           "las lecturas largas.")
        if not reglas:
            reglas.append("Ninguna regla de excepción se activó; se usó solo la clasificación del árbol.")

        # (4) Filtrado basado en contenido
        recursos = self.ordenar_recursos(efectivo, formato, evitar_texto)

        # (5) Ruta del grafo hasta la meta (A*). Si se retrocede, el tema completado
        #     no cambia: solo se recalcula la ruta desde lo que ya domina.
        ruta, costo, explorados = ruta_a_estrella(self.grafo, comp, nodo_meta, nivel)

        # (6) Ruta con recurso por paso: cada tema de la ruta recibe su recurso principal
        #     (mismo filtrado por contenido). Si hubo retroceso, el repaso va primero.
        pasos = [(n, "Estudiar") for n in (ruta or [])]
        if efectivo in comp:
            pasos.insert(0, (efectivo, "Repaso"))
        ruta_detalle = []
        for k, (n, tipo_paso) in enumerate(pasos, 1):
            rec_n = self.ordenar_recursos(n, formato, evitar_texto)
            ruta_detalle.append({
                "orden": k, "tema": NODO_A_TEMA[n], "paso": tipo_paso,
                "recurso": rec_n[0]["recurso"], "formato": rec_n[0]["formato"],
                "alternativas": [x["recurso"] for x in rec_n[1:]]})
        return {
            "tipo_apoyo": tipo, "tipo_arbol": tipo_arbol, "accion": accion, "confianza": proba,
            "tema_recomendado": NODO_A_TEMA[efectivo],
            "recursos": recursos, "ruta_detalle": ruta_detalle,
            "ruta": [NODO_A_TEMA[n] for n in ruta] if ruta is not None else [],
            "costo_ruta": costo, "estados_explorados": explorados,
            "desbloqueados": [NODO_A_TEMA[n] for n in desbloqueados(self.grafo, comp)],
            "reglas": reglas, "motivos": motivos,
            "_nodo_actual": efectivo, "_completados": comp, "_meta": nodo_meta,
        }


# --------------------------------------------------------------------------
# 4. Presentación: texto, figura del grafo e interfaz Gradio
# --------------------------------------------------------------------------
def formatear(r):
    """Resultado de la recomendación en formato Markdown."""
    md = [f"### Acción sugerida: **{r['accion']}**",
          f"**Tema recomendado:** {r['tema_recomendado']}  \n"
          f"**Clasificación del árbol de decisión:** {r['tipo_arbol']} "
          f"· confianza {r['confianza']:.0%}", "", "#### Recursos recomendados"]
    for i, x in enumerate(r["recursos"], 1):
        md.append(f"{i}. `{x['recurso']}` — {x['formato']} (puntaje {x['puntaje']}) · {x['rol']}")
    md += ["", "#### Ruta de aprendizaje hacia la meta, con recurso por paso (A*)"]
    if r["ruta_detalle"]:
        md += ["| Paso | Tema | Recurso principal | Formato |", "|---|---|---|---|"]
        for p in r["ruta_detalle"]:
            etiqueta = f"{p['orden']} ({p['paso']})" if p["paso"] == "Repaso" else str(p["orden"])
            md.append(f"| {etiqueta} | {p['tema']} | `{p['recurso']}` | {p['formato']} |")
        md.append(f"\n_Costo de la ruta: {r['costo_ruta']} · estados explorados: "
                  f"{r['estados_explorados']}_")
    else:
        md.append("La meta ya está completada.")
    md += ["", "#### Reglas activadas"] + [f"- {x}" for x in r["reglas"]]
    md += ["", "#### ¿Por qué esta recomendación?"] + [f"- {x}" for x in r["motivos"]]
    md.append("\n> Sugerencia adaptativa: el docente puede revisarla o modificarla. "
              "No constituye una calificación ni diagnóstico definitivo.")
    return "\n".join(md)


def dibujar_grafo(rec, r=None, ax=None):
    """Dibuja el grafo: completado (verde), actual (azul), ruta (naranja), bloqueado (gris)."""
    import matplotlib.pyplot as plt
    import networkx as nx
    G = nx.DiGraph()
    G.add_nodes_from(rec.grafo)
    G.add_edges_from(rec.aristas)
    for i, gen in enumerate(nx.topological_generations(G)):
        for n in gen:
            G.nodes[n]["capa"] = i
    pos = nx.multipartite_layout(G, subset_key="capa")
    comp = r["_completados"] if r else set()
    ruta = {TEMA_A_NODO[t] for t in r["ruta"]} if r else set()
    actual = r["_nodo_actual"] if r else None
    colores = []
    for n in G.nodes:
        if n == actual: colores.append("#4C8BF5")
        elif n in comp: colores.append("#7BC67E")
        elif n in ruta: colores.append("#F5A623")
        else: colores.append("#D0D0D0")
    if ax is None:
        fig, ax = plt.subplots(figsize=(9.5, 5.2))
    else:
        fig = ax.figure
    nx.draw_networkx_edges(G, pos, ax=ax, arrows=True, arrowsize=18, width=1.6,
                           edge_color="#777777", node_size=7500)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=colores, node_size=7500,
                           edgecolors="#333333")
    import textwrap
    orden = {TEMA_A_NODO[p["tema"]]: p for p in r["ruta_detalle"]} if r else {}
    etiquetas = {}
    for n in G.nodes:
        txt = textwrap.fill(NODO_A_TEMA[n], 13)
        if n in orden:
            p = orden[n]
            cab = f"PASO {p['orden']}" + (" (repaso)" if p["paso"] == "Repaso" else "")
            txt = cab + "\n" + txt
        etiquetas[n] = txt
    nx.draw_networkx_labels(G, pos, etiquetas, ax=ax, font_size=7.5)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#4C8BF5", label="Tema recomendado ahora"),
                       Patch(color="#7BC67E", label="Completado"),
                       Patch(color="#F5A623", label="En la ruta a la meta"),
                       Patch(color="#D0D0D0", label="Pendiente")],
              loc="lower center", ncol=4, fontsize=8, frameon=False,
              bbox_to_anchor=(0.5, -0.12))
    ax.margins(0.18, 0.2)
    ax.set_axis_off()
    ax.set_title("Grafo de conocimiento: flechas = prerrequisito · PASO n = orden de estudio", fontsize=10)
    fig.tight_layout()
    return fig


def construir_interfaz(rec):
    """Interfaz Gradio: formulario de entrada + resultado + grafo."""
    import gradio as gr
    temas = list(TEMA_A_NODO)

    def ejecutar(nivel, formato, tema, tiempo, errores, completados, meta, fallos, abandono):
        r = rec.recomendar(nivel, formato, tema, tiempo, errores,
                           completados or [], meta, int(fallos), abandono)
        fig = dibujar_grafo(rec, r)
        return formatear(r), fig

    with gr.Blocks(title="Recomendador de rutas de aprendizaje") as demo:
        gr.Markdown("# Recomendador personalizado de recursos y rutas de aprendizaje\n"
                    "Prototipo con **datos simulados**. Las recomendaciones son sugerencias "
                    "adaptativas; no sustituyen al docente.")
        with gr.Row():
            with gr.Column(scale=1):
                nivel = gr.Radio(NIVELES, value="Principiante", label="Nivel previo")
                formato = gr.Radio(FORMATOS, value="Visual", label="Formato preferido")
                tema = gr.Dropdown(temas, value=temas[0], label="Tema que está estudiando")
                tiempo = gr.Slider(5, 300, value=120, step=1, label="Tiempo de interacción (s)")
                errores = gr.Slider(0, 100, value=50, step=1, label="Tasa de errores (%)")
                completados = gr.CheckboxGroup(temas, value=[], label="Temas ya completados")
                meta = gr.Dropdown(temas, value="Backend con Node.js", label="Meta de aprendizaje")
                fallos = gr.Slider(0, 6, value=0, step=1, label="Fallos consecutivos en el tema")
                abandono = gr.Checkbox(label="Abandonó la actividad a la mitad")
                boton = gr.Button("Recomendar", variant="primary")
            with gr.Column(scale=2):
                salida = gr.Markdown()
                figura = gr.Plot(show_label=False)
        entradas = [nivel, formato, tema, tiempo, errores, completados, meta, fallos, abandono]
        boton.click(ejecutar, entradas, [salida, figura])
    return demo
