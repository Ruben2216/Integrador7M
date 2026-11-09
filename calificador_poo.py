"""Rúbrica estructural de POO: analiza AST y nunca ejecuta código entregado."""
from __future__ import annotations

import ast
from uuid import uuid4

TEMA = "Programación Orientada a Objetos"


def _clase(arbol: ast.AST, nombre: str):
    return next((n for n in ast.walk(arbol)
                 if isinstance(n, ast.ClassDef) and n.name == nombre), None)


def _metodo(clase: ast.ClassDef | None, nombre: str):
    return next((n for n in clase.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nombre), None) if clase else None


def _atributo(metodo: ast.AST | None, nombre: str) -> bool:
    return bool(metodo and any(isinstance(n, ast.Attribute) and n.attr == nombre
                               and isinstance(n.value, ast.Name) and n.value.id == "self"
                               for n in ast.walk(metodo)))


def _compara(metodo: ast.AST | None) -> bool:
    return bool(metodo and any(isinstance(n, ast.If) and
                any(isinstance(c, ast.Compare) for c in ast.walk(n.test))
                for n in ast.walk(metodo)))


def _comprobar(identificador: str, arbol: ast.AST) -> dict[str, bool]:
    if identificador == "POO-01":
        libro = _clase(arbol, "Libro")
        inicio = _metodo(libro, "__init__")
        describir = _metodo(libro, "describir")
        llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == "Libro"]
        return {"Clase Libro": libro is not None,
                "Atributos titulo y autor": _atributo(inicio, "titulo") and _atributo(inicio, "autor"),
                "Método describir devuelve ambos datos": bool(
                    describir and _atributo(describir, "titulo") and _atributo(describir, "autor")
                    and any(isinstance(n, ast.Return) for n in ast.walk(describir))),
                "Dos instancias": len(llamadas) >= 2}
    if identificador == "POO-02":
        cuenta = _clase(arbol, "CuentaBancaria")
        depositar, retirar = _metodo(cuenta, "depositar"), _metodo(cuenta, "retirar")
        return {"Clase y saldo": cuenta is not None and _atributo(_metodo(cuenta, "__init__"), "saldo"),
                "Métodos depositar y retirar": depositar is not None and retirar is not None,
                "Validación de depósito": _compara(depositar),
                "Validación de retiro": _compara(retirar)}
    if identificador == "POO-03":
        producto = _clase(arbol, "Producto")
        vender = _metodo(producto, "vender")
        consultar = _metodo(producto, "consultar_stock")
        return {"Clase Producto": producto is not None,
                "Stock interno": _atributo(_metodo(producto, "__init__"), "_stock"),
                "Métodos vender y consultar_stock": vender is not None and consultar is not None,
                "Control de stock": _compara(vender)}
    if identificador == "POO-04":
        pedido = _clase(arbol, "Pedido")
        calcular = _metodo(pedido, "calcular_total")
        return {"Clases Pedido y Producto": pedido is not None and _clase(arbol, "Producto") is not None,
                "Método calcular_total": calcular is not None,
                "Recorrido de productos": bool(calcular and any(isinstance(n, (ast.For, ast.comprehension)) for n in ast.walk(calcular))),
                "Cálculo de importes": bool(calcular and any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult)
                                              for n in ast.walk(calcular)) and
                                              any(isinstance(n, ast.Return) for n in ast.walk(calcular)))}
    raise ValueError(f"Ejercicio POO desconocido: {identificador}")


def calificar_laboratorio_poo(respuestas: dict[str, str], tiempo: float) -> dict:
    detalle, cumplidos, incumplidos = [], [], []
    for identificador in ("POO-01", "POO-02", "POO-03", "POO-04"):
        try:
            codigo = str(respuestas.get(identificador, ""))
            if len(codigo) > 20000:
                raise ValueError("El código supera el límite de 20 000 caracteres.")
            arbol = ast.parse(codigo)
            criterios = _comprobar(identificador, arbol)
            error = None
        except (SyntaxError, ValueError, RecursionError) as exc:
            criterios = {"Código Python válido": False}
            error = (f"Error de sintaxis en línea {exc.lineno}." if isinstance(exc, SyntaxError)
                     else str(exc))
        buenos = [f"{identificador}: {nombre}" for nombre, ok in criterios.items() if ok]
        malos = [f"{identificador}: {nombre}" for nombre, ok in criterios.items() if not ok]
        cumplidos.extend(buenos)
        incumplidos.extend(malos)
        detalle.append({"id": identificador, "concepto": identificador,
                        "correcto": not malos, "criterios_cumplidos": buenos,
                        "criterios_incumplidos": malos, "error": error})
    correctos = sum(item["correcto"] for item in detalle)
    return {"intento": str(uuid4()), "tema": TEMA, "tipo": "laboratorio",
            "etapa": "integradora", "puntaje": correctos / 4, "tiempo": max(0.0, tiempo),
            "ejercicios_correctos": correctos, "total_ejercicios": 4,
            "criterios_cumplidos": cumplidos, "criterios_incumplidos": incumplidos,
            "conceptos_con_errores": [item["id"] for item in detalle if not item["correcto"]],
            "acreditado": correctos >= 3 and detalle[-1]["correcto"], "detalle": detalle}
