"""Banco y calificación de las tres etapas formativas de cada tema."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from progreso import ETAPAS, TEMAS

BASE = Path(__file__).resolve().parent
FUENTES = {
    TEMAS[0]: "ejercicios_logica.json",
    TEMAS[1]: "ejercicios_poo.json",
    TEMAS[2]: "ejercicios_postgresql.json",
    TEMAS[3]: "ejercicios_node.json",
    TEMAS[4]: "ejercicios_mvc_php.json",
}


def _pregunta(identificador, enunciado, correcta, distractores, concepto):
    return {
        "id": identificador, "enunciado": enunciado,
        "opciones": [correcta, *distractores], "respuesta_correcta": correcta,
        "concepto": concepto,
    }


EXTRAS = {
    TEMAS[0]: [
        _pregunta("LOG-N3-01", "Una lista puede estar vacía. ¿Cómo calcular su promedio sin dividir entre cero?", "Comprobar si hay elementos antes de dividir la suma entre su cantidad", ["Dividir siempre entre uno", "Usar la suma como promedio", "Eliminar el caso de lista vacía"], "LISTAS"),
        _pregunta("LOG-N3-02", "Al filtrar calificaciones válidas, ¿cuándo debe incrementarse el contador usado para el promedio?", "Solo cuando la calificación esté entre 0 y 100", ["Antes de validar cada valor", "Solo cuando sea mayor que 100", "Después de calcular el promedio"], "CICLOS"),
        _pregunta("LOG-N3-03", "¿Qué prueba detecta mejor un error en un algoritmo que busca el máximo de una lista?", "Una lista con todos los valores negativos", ["Una lista con solo valores positivos", "Repetir siempre la misma lista", "Usar únicamente una lista ordenada"], "DEPURACION"),
    ],
    TEMAS[2]: [
        _pregunta("PSQL-N3-01", "¿Cómo obtener clientes sin pedidos conservando los clientes sin coincidencia?", "LEFT JOIN pedidos y WHERE pedidos.id IS NULL", ["INNER JOIN pedidos", "CROSS JOIN pedidos", "ORDER BY pedidos.id"], "JOIN"),
        _pregunta("PSQL-N3-02", "Tras agrupar ventas por producto, ¿dónde se filtran los grupos cuya suma supera 1000?", "HAVING SUM(total) > 1000", ["WHERE SUM(total) > 1000", "ORDER BY SUM(total) > 1000", "LIMIT SUM(total) > 1000"], "AGREGACION"),
        _pregunta("PSQL-N3-03", "Un UPDATE sin WHERE sobre productos, ¿qué riesgo tiene?", "Modificar todas las filas de productos", ["No modificar ninguna fila", "Borrar la tabla", "Crear automáticamente una transacción"], "SEGURIDAD_SQL"),
        _pregunta("PSQL-N3-04", "¿Qué consulta evita duplicar clientes cuando tienen varios pedidos?", "SELECT DISTINCT c.id FROM clientes c JOIN pedidos p ON p.cliente_id = c.id", ["SELECT c.id FROM clientes c JOIN pedidos p ON p.cliente_id = c.id", "SELECT ALL c.id FROM clientes c JOIN pedidos p ON p.cliente_id = c.id", "SELECT c.id FROM clientes c CROSS JOIN pedidos p"], "JOIN"),
        _pregunta("PSQL-N3-05", "En una transacción, ¿qué acción revierte todos los cambios aún no confirmados?", "ROLLBACK", ["COMMIT", "SELECT", "GROUP BY"], "TRANSACCIONES"),
    ],
    TEMAS[4]: [
        _pregunta("MVC-N2-01", "Una validación de reglas de negocio se repite en dos controladores. ¿Dónde debe centralizarse?", "En el modelo o servicio de dominio", ["En ambas vistas", "En el archivo CSS", "En cada enlace HTML"], "RESPONSABILIDADES_CAPA"),
    ],
    TEMAS[3]: [
        _pregunta("NODE-N3-01", "Una operación asincrónica falla dentro de una ruta Express. ¿Qué debe hacerse?", "Pasar el error al manejador y responder sin exponer detalles internos", ["Ignorar la promesa rechazada", "Responder siempre 200", "Enviar la traza completa al cliente"], "ERRORES"),
        _pregunta("NODE-N3-02", "¿Qué respuesta corresponde a un identificador válido cuyo recurso no existe?", "404 Not Found", ["200 OK", "201 Created", "500 Internal Server Error"], "HTTP"),
        _pregunta("NODE-N3-03", "Tras crear un recurso, ¿qué combinación es más adecuada?", "201 Created y ubicación del nuevo recurso", ["200 OK y ningún dato", "404 Not Found", "500 Internal Server Error"], "API"),
        _pregunta("NODE-N3-04", "¿Por qué validar datos antes de guardar en una API?", "Para impedir registros inválidos y devolver un error útil", ["Para que GET modifique datos", "Para evitar todas las fallas de red", "Para convertir errores en respuestas 200"], "VALIDACION"),
        _pregunta("NODE-N3-05", "Una ruta /libros/:id recibe /libros/abc pero espera un número. ¿Qué respuesta conviene?", "400 Bad Request con explicación del identificador", ["201 Created", "200 OK con un libro inventado", "500 Internal Server Error sin validar"], "RUTAS"),
    ],
    TEMAS[1]: [
        _pregunta("POO-N1-01", "¿Qué es un objeto?", "Una instancia de una clase", ["Un nombre alternativo para un módulo", "Un método sin parámetros", "Un archivo JSON"], "CLASES"),
        _pregunta("POO-N1-02", "¿Qué describe una clase?", "Atributos y comportamientos compartidos por sus objetos", ["Solo el valor de un objeto", "Una consulta SQL", "Una ruta HTTP"], "CLASES"),
        _pregunta("POO-N1-03", "En class Libro, ¿qué representa titulo?", "Un atributo del libro", ["Una subclase", "Una excepción", "Un módulo"], "ATRIBUTOS"),
        _pregunta("POO-N1-04", "¿Qué representa describir() dentro de Libro?", "Un método", ["Una instancia", "Una herencia", "Un archivo"], "METODOS"),
        _pregunta("POO-N1-05", "¿Pueden dos objetos Libro tener títulos distintos?", "Sí, cada instancia conserva su propio estado", ["No, comparten todos los valores", "Solo si están en archivos distintos", "Solo mediante una base de datos"], "OBJETOS"),
        _pregunta("POO-N2-01", "¿Qué operación debe cambiar el saldo de una cuenta bancaria?", "Un método de la cuenta que valide el monto", ["Una asignación externa sin validación", "La vista HTML", "La clase Producto"], "ENCAPSULAMIENTO"),
        _pregunta("POO-N2-02", "¿Qué debe pasar si retirar(50) se invoca con saldo 20?", "Rechazar la operación y conservar el saldo", ["Dejar saldo -30", "Duplicar el saldo", "Borrar el objeto"], "VALIDACION"),
        _pregunta("POO-N2-03", "¿Qué permite reutilizar una validación de depósito?", "Encapsularla en el método depositar", ["Copiarla en cada llamada", "Eliminar los métodos", "Guardarla en CSS"], "METODOS"),
        _pregunta("POO-N2-04", "Un Pedido contiene varios Producto. ¿Qué relación describe mejor el diseño?", "Composición o agregación de productos", ["Herencia de Producto a Pedido", "Dos clases sin relación", "Un método estático obligatorio"], "COLABORACION"),
        _pregunta("POO-N2-05", "¿Dónde conviene calcular el total de un pedido?", "En un método del Pedido que recorra sus productos", ["En cada Producto sumando todos los pedidos", "En el nombre de la clase", "En una constante global"], "COLABORACION"),
        _pregunta("POO-N3-01", "Si un Producto tiene precio y cantidad, ¿qué debe aportar al total del Pedido?", "precio por cantidad", ["precio más cantidad", "solo precio", "solo cantidad"], "COLABORACION"),
        _pregunta("POO-N3-02", "¿Qué prueba descubre un error al vender más unidades que el inventario?", "Vender una cantidad mayor que el stock y comprobar que no cambia", ["Consultar solo el nombre", "Crear un producto sin vender", "Cambiar el color de la vista"], "PRUEBAS"),
        _pregunta("POO-N3-03", "¿Qué debe ocurrir si un Pedido no contiene productos?", "Su total debe ser cero", ["Debe heredar Producto", "Su total debe ser negativo", "Debe crear un producto ficticio"], "CASOS_LIMITE"),
        _pregunta("POO-N3-04", "¿Cómo evitar que código externo modifique directamente el stock?", "Exponer operaciones controladas en Producto", ["Dejar el atributo público sin validar", "Duplicar el stock en Pedido", "Guardarlo en una variable global"], "ENCAPSULAMIENTO"),
        _pregunta("POO-N3-05", "Si cambia la regla de descuentos, ¿qué diseño facilita mantener el sistema?", "Concentrar la regla en la clase responsable", ["Repetirla en todas las vistas", "Repetirla en cada objeto", "Eliminar los métodos"], "DISENO"),
    ],
}

NODE_DISTRACTORES = {
    "node-q1-a": ["POST", "PUT", "DELETE"], "node-q2-a": ["201", "404", "500"],
    "node-q3-a": ["req.query.id", "req.body.id", "res.params.id"],
    "node-q4-a": ["No", "Solo después de guardar", "Solo para GET"],
    "node-q5-a": ["GET", "PUT", "DELETE"],
    "node-q1-b": ["POST", "PATCH", "DELETE"], "node-q2-b": ["200", "400", "404"],
    "node-q3-b": ["req.query", "req.body", "res.params"],
    "node-q4-b": ["Sí", "Solo si se usa GET", "Siempre se crea un registro vacío"],
    "node-q5-b": ["GET", "HEAD", "DELETE"],
}


def preguntas_nivel(tema: str, etapa: str) -> list[dict]:
    """Devuelve cinco preguntas estables; no consume variantes al reintentar."""
    if tema not in TEMAS or etapa not in ETAPAS[:3]:
        raise ValueError("Tema o nivel desconocido")
    with (BASE / FUENTES[tema]).open(encoding="utf-8") as archivo:
        banco = json.load(archivo)
    if tema == TEMAS[1]:
        indice = ETAPAS.index(etapa)
        preguntas = EXTRAS[tema][indice * 5:(indice + 1) * 5]
    elif tema == TEMAS[3]:
        if etapa == "avanzado":
            preguntas = EXTRAS[tema]
        else:
            indice = ETAPAS.index(etapa)
            preguntas = []
            for q in banco["seguimiento"]["variantes"][indice]:
                preguntas.append(_pregunta(q["id"], q["pregunta"], q["respuesta"],
                                           NODE_DISTRACTORES[q["id"]], q["concepto"]))
    else:
        todas = [q for variante in banco["seguimiento"].values() for q in variante]
        def dificultad(q):
            valor = q["dificultad"].lower()
            return "basico" if valor in ("principiante", "básico") else (
                "avanzado" if valor in ("avanzado", "integrador") else "intermedio")
        preguntas = [q for q in todas if dificultad(q) == etapa][:5]
        preguntas += EXTRAS[tema][:5 - len(preguntas)]
    if len(preguntas) != 5 or len({q["id"] for q in preguntas}) != 5:
        raise ValueError(f"Banco incompleto para {tema}: {etapa}")
    return [{**q, "enunciado": q.get("enunciado", q.get("pregunta", ""))} for q in preguntas]


def calificar_nivel(tema: str, etapa: str, respuestas: dict[str, str], tiempo: float) -> dict:
    preguntas = preguntas_nivel(tema, etapa)
    detalle = [{"id": q["id"], "concepto": q["concepto"],
                "correcto": str(respuestas.get(q["id"], "")).strip() == q["respuesta_correcta"].strip()}
               for q in preguntas]
    correctas = sum(item["correcto"] for item in detalle)
    return {
        "intento": str(uuid4()), "tema": tema, "tipo": "nivel", "etapa": etapa,
        "puntaje": correctas / 5, "tiempo": max(0.0, tiempo),
        "correctas": correctas, "total_preguntas": 5,
        "criterios_cumplidos": [d["id"] for d in detalle if d["correcto"]],
        "criterios_incumplidos": [d["id"] for d in detalle if not d["correcto"]],
        "conceptos_con_errores": sorted({d["concepto"] for d in detalle if not d["correcto"]}),
        "acreditado": correctas >= 4, "detalle": detalle,
    }
