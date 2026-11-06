"""
ejercicios_logica.py — Banco de ejercicios: Lógica de Programación
Tema asignado a Integrante 1.

Categorías:
  1. Condiciones (if / elif / else)
  2. Ciclos (for / while)
  3. Corrección de errores lógicos
  4. Problema integrador (condiciones + ciclos)

Cada ejercicio es un dict con:
  id          : identificador único
  categoria   : nombre de la categoría
  titulo      : enunciado breve
  descripcion : contexto completo
  pistas      : lista de pistas progresivas
  solucion    : código de referencia (como string)
  nivel       : Principiante | Intermedio | Avanzado
"""

EJERCICIOS: list[dict] = [

    # ─────────────────────────────────────────────
    # CATEGORÍA 1 — CONDICIONES
    # ─────────────────────────────────────────────
    {
        "id": "LOGICA-C01",
        "categoria": "Condiciones",
        "titulo": "Clasificar una calificación",
        "descripcion": (
            "Escribe un programa que lea una calificación (0–100) e imprima:\n"
            "  · 'Excelente'   si calificación >= 90\n"
            "  · 'Aprobado'    si calificación >= 60\n"
            "  · 'Reprobado'   en cualquier otro caso."
        ),
        "pistas": [
            "Usa if / elif / else con operadores de comparación.",
            "El orden importa: evalúa primero la condición más restrictiva.",
        ],
        "solucion": """\
calificacion = int(input("Calificación (0-100): "))
if calificacion >= 90:
    print("Excelente")
elif calificacion >= 60:
    print("Aprobado")
else:
    print("Reprobado")
""",
        "nivel": "Principiante",
    },
    {
        "id": "LOGICA-C02",
        "categoria": "Condiciones",
        "titulo": "Número par, impar y divisible por 3",
        "descripcion": (
            "Dado un número entero, determina e imprime:\n"
            "  · Si es par o impar.\n"
            "  · Si es divisible por 3.\n"
            "  · Si es par Y divisible por 3 al mismo tiempo."
        ),
        "pistas": [
            "El operador módulo (%) te da el resto de la división.",
            "Puedes combinar condiciones con 'and'.",
        ],
        "solucion": """\
n = int(input("Número entero: "))
print("Par" if n % 2 == 0 else "Impar")
print("Divisible por 3" if n % 3 == 0 else "No divisible por 3")
if n % 2 == 0 and n % 3 == 0:
    print("Par Y divisible por 3")
""",
        "nivel": "Principiante",
    },
    {
        "id": "LOGICA-C03",
        "categoria": "Condiciones",
        "titulo": "Semáforo con condiciones anidadas",
        "descripcion": (
            "Un semáforo tiene tres estados: 'rojo', 'amarillo', 'verde'.\n"
            "Pide el color al usuario e imprime la instrucción correspondiente.\n"
            "Si el color no es válido, muestra un mensaje de error."
        ),
        "pistas": [
            "Usa elif para manejar cada color.",
            "Convierte la entrada a minúsculas con .lower() para evitar problemas de mayúsculas.",
        ],
        "solucion": """\
color = input("Color del semáforo: ").lower()
if color == "rojo":
    print("Detente")
elif color == "amarillo":
    print("Precaución")
elif color == "verde":
    print("Avanza")
else:
    print("Color inválido")
""",
        "nivel": "Principiante",
    },

    # ─────────────────────────────────────────────
    # CATEGORÍA 2 — CICLOS
    # ─────────────────────────────────────────────
    {
        "id": "LOGICA-L01",
        "categoria": "Ciclos",
        "titulo": "Tabla de multiplicar",
        "descripcion": (
            "Pide al usuario un número entero entre 1 y 10 e imprime\n"
            "su tabla de multiplicar (del 1 al 10).\n"
            "Formato esperado:  3 × 1 = 3"
        ),
        "pistas": [
            "Usa for con range(1, 11) para iterar del 1 al 10.",
            "El operador × se puede escribir con el símbolo * en el print.",
        ],
        "solucion": """\
n = int(input("Número (1-10): "))
for i in range(1, 11):
    print(f"{n} × {i} = {n * i}")
""",
        "nivel": "Principiante",
    },
    {
        "id": "LOGICA-L02",
        "categoria": "Ciclos",
        "titulo": "Suma de los primeros N números",
        "descripcion": (
            "El usuario introduce un número N.\n"
            "Calcula e imprime la suma de todos los enteros positivos del 1 al N.\n"
            "Muestra también cuántas iteraciones realizó el ciclo."
        ),
        "pistas": [
            "Puedes usar un acumulador (variable suma = 0) e irla sumando en cada iteración.",
            "range(1, N+1) genera los números del 1 al N inclusive.",
        ],
        "solucion": """\
n = int(input("N: "))
suma = 0
for i in range(1, n + 1):
    suma += i
print(f"Suma = {suma}  (N iteraciones: {n})")
""",
        "nivel": "Principiante",
    },
    {
        "id": "LOGICA-L03",
        "categoria": "Ciclos",
        "titulo": "Validar entrada con while",
        "descripcion": (
            "Pide al usuario que ingrese un número entre 1 y 100.\n"
            "Si el número está fuera del rango, muestra 'Valor inválido' y\n"
            "vuelve a pedirlo. Termina cuando el usuario ingrese un valor válido."
        ),
        "pistas": [
            "Un ciclo while es ideal cuando no sabes cuántas veces repetirás.",
            "Usa una condición que sea True mientras el valor sea inválido.",
        ],
        "solucion": """\
numero = None
while numero is None or not (1 <= numero <= 100):
    try:
        numero = int(input("Ingresa un número entre 1 y 100: "))
        if not (1 <= numero <= 100):
            print("Valor inválido, intenta de nuevo.")
    except ValueError:
        print("Debes ingresar un número entero.")
print(f"Valor aceptado: {numero}")
""",
        "nivel": "Intermedio",
    },
    {
        "id": "LOGICA-L04",
        "categoria": "Ciclos",
        "titulo": "Búsqueda en una lista",
        "descripcion": (
            "Dada la lista nombres = ['Ana', 'Luis', 'María', 'Carlos'],\n"
            "pide al usuario un nombre y recorre la lista con un ciclo for.\n"
            "Imprime en qué posición se encontró el nombre, o 'No encontrado'\n"
            "si no existe. No uses el método .index()."
        ),
        "pistas": [
            "Usa enumerate() para obtener índice y valor en cada iteración.",
            "Una variable booleana 'encontrado' te ayuda a saber si debes imprimir 'No encontrado'.",
        ],
        "solucion": """\
nombres = ['Ana', 'Luis', 'María', 'Carlos']
buscado = input("Nombre a buscar: ")
encontrado = False
for i, nombre in enumerate(nombres):
    if nombre == buscado:
        print(f"Encontrado en posición {i}")
        encontrado = True
        break
if not encontrado:
    print("No encontrado")
""",
        "nivel": "Intermedio",
    },

    # ─────────────────────────────────────────────
    # CATEGORÍA 3 — CORRECCIÓN DE ERRORES LÓGICOS
    # ─────────────────────────────────────────────
    {
        "id": "LOGICA-E01",
        "categoria": "Corrección de errores",
        "titulo": "Ciclo infinito por condición mal escrita",
        "descripcion": (
            "El siguiente código tiene un error lógico que provoca un ciclo infinito.\n"
            "Encuéntralo y corrígelo.\n\n"
            "CÓDIGO CON ERROR:\n"
            "    contador = 10\n"
            "    while contador > 0:\n"
            "        print(contador)\n"
            "        contador += 1   # ← aquí está el error\n\n"
            "El programa debe imprimir los números del 10 al 1 en orden decreciente."
        ),
        "pistas": [
            "El contador debe disminuir, no aumentar, para que la condición eventualmente sea falsa.",
            "Cambia += por -=.",
        ],
        "solucion": """\
# CÓDIGO CORREGIDO
contador = 10
while contador > 0:
    print(contador)
    contador -= 1  # resta 1 en cada iteración → el ciclo termina cuando contador llega a 0
""",
        "nivel": "Principiante",
    },
    {
        "id": "LOGICA-E02",
        "categoria": "Corrección de errores",
        "titulo": "Condición fuera de orden (clasificación de edades)",
        "descripcion": (
            "El código de abajo nunca imprime 'Adolescente' aunque la edad sea 15.\n"
            "Identifica el error y corrígelo.\n\n"
            "CÓDIGO CON ERROR:\n"
            "    edad = 15\n"
            "    if edad >= 0:\n"
            "        print('Niño/a')\n"
            "    elif edad >= 13:\n"
            "        print('Adolescente')\n"
            "    elif edad >= 18:\n"
            "        print('Adulto')\n\n"
            "Reglas: 0–12 → Niño/a, 13–17 → Adolescente, 18+ → Adulto."
        ),
        "pistas": [
            "El primer if captura todos los valores >= 0, incluyendo 15.",
            "Ordena las condiciones de más restrictiva a menos restrictiva.",
        ],
        "solucion": """\
# CÓDIGO CORREGIDO
edad = 15
if edad >= 18:
    print('Adulto')
elif edad >= 13:
    print('Adolescente')
elif edad >= 0:
    print('Niño/a')
else:
    print('Edad inválida')
""",
        "nivel": "Principiante",
    },
    {
        "id": "LOGICA-E03",
        "categoria": "Corrección de errores",
        "titulo": "Acumulador que no acumula",
        "descripcion": (
            "El siguiente código intenta sumar los números pares del 1 al 10,\n"
            "pero siempre imprime 10 (solo el último número par).\n\n"
            "CÓDIGO CON ERROR:\n"
            "    for numero in range(1, 11):\n"
            "        if numero % 2 == 0:\n"
            "            suma = numero   # ← error aquí\n"
            "    print('Suma de pares:', suma)\n\n"
            "El resultado correcto es 30 (2+4+6+8+10)."
        ),
        "pistas": [
            "El acumulador debe inicializarse ANTES del ciclo, en 0.",
            "Dentro del ciclo debe sumarse (+=) no asignarse (=).",
        ],
        "solucion": """\
# CÓDIGO CORREGIDO
suma = 0  # inicializar ANTES del ciclo
for numero in range(1, 11):
    if numero % 2 == 0:
        suma += numero  # acumular, no reemplazar
print('Suma de pares:', suma)  # imprime 30
""",
        "nivel": "Principiante",
    },

    # ─────────────────────────────────────────────
    # CATEGORÍA 4 — PROBLEMA INTEGRADOR
    # ─────────────────────────────────────────────
    {
        "id": "LOGICA-I01",
        "categoria": "Integrador",
        "titulo": "Mini calificador con ciclo y condiciones",
        "descripcion": (
            "Escribe un programa que simule un mini examen de 5 preguntas.\n"
            "Para cada pregunta (definida por ti en el código), el usuario\n"
            "introduce su respuesta. Al final:\n"
            "  · Cuenta cuántas respuestas fueron correctas.\n"
            "  · Calcula el porcentaje de aciertos.\n"
            "  · Imprime 'Aprobado' si el porcentaje >= 60 %, 'Reprobado' si no.\n\n"
            "Combina: ciclo for para iterar las preguntas +\n"
            "         condición if/else para verificar respuesta +\n"
            "         acumulador para contar aciertos +\n"
            "         condición final para el resultado."
        ),
        "pistas": [
            "Guarda las preguntas y respuestas correctas en dos listas paralelas (o en una lista de dicts).",
            "Usa enumerate() para numerar cada pregunta al imprimirla.",
            "El porcentaje es: (aciertos / total_preguntas) * 100.",
        ],
        "solucion": """\
preguntas = [
    ("¿Cuánto es 2 + 2?", "4"),
    ("¿Cuál es la capital de México?", "ciudad de mexico"),
    ("¿Cuántos días tiene una semana?", "7"),
    ("¿Cuánto es 10 // 3 en Python?", "3"),
    ("¿Qué imprime print(type(1))?", "<class 'int'>"),
]

aciertos = 0
for i, (pregunta, correcta) in enumerate(preguntas, 1):
    respuesta = input(f"Pregunta {i}: {pregunta} → ").strip().lower()
    if respuesta == correcta.lower():
        print("  ✓ Correcto")
        aciertos += 1
    else:
        print(f"  ✗ Incorrecto. Respuesta correcta: {correcta}")

porcentaje = (aciertos / len(preguntas)) * 100
print(f"\\nResultado: {aciertos}/{len(preguntas)} ({porcentaje:.0f} %)")
print("Aprobado" if porcentaje >= 60 else "Reprobado")
""",
        "nivel": "Intermedio",
    },
    {
        "id": "LOGICA-I02",
        "categoria": "Integrador",
        "titulo": "Calculadora de promedios con validación",
        "descripcion": (
            "Escribe un programa que:\n"
            "  1. Pida al usuario cuántas calificaciones quiere ingresar (N, entre 1 y 10).\n"
            "     Si N está fuera del rango, pídelo de nuevo con while.\n"
            "  2. Con un ciclo for, pida cada calificación (0–100).\n"
            "     Si la calificación no está en rango, muestra error y pídela de nuevo.\n"
            "  3. Al final, muestre: promedio, calificación máxima, mínima\n"
            "     y si el promedio es 'Excelente' (>=90), 'Aprobado' (>=60) o 'Reprobado'."
        ),
        "pistas": [
            "Usa un while para validar N antes de entrar al ciclo for.",
            "Dentro del for, usa otro while para validar cada calificación.",
            "Guarda las calificaciones en una lista para calcular max() y min().",
        ],
        "solucion": """\
# 1. Pedir N con validación
n = 0
while not (1 <= n <= 10):
    try:
        n = int(input("¿Cuántas calificaciones? (1-10): "))
        if not (1 <= n <= 10):
            print("Número fuera de rango.")
    except ValueError:
        print("Ingresa un número entero.")

# 2. Pedir cada calificación con validación
calificaciones = []
for i in range(1, n + 1):
    cal = -1
    while not (0 <= cal <= 100):
        try:
            cal = float(input(f"Calificación {i}: "))
            if not (0 <= cal <= 100):
                print("Calificación fuera de rango (0-100).")
        except ValueError:
            print("Ingresa un número válido.")
    calificaciones.append(cal)

# 3. Resultados
promedio = sum(calificaciones) / len(calificaciones)
print(f"\\nPromedio : {promedio:.2f}")
print(f"Máxima   : {max(calificaciones)}")
print(f"Mínima   : {min(calificaciones)}")
if promedio >= 90:
    print("Excelente")
elif promedio >= 60:
    print("Aprobado")
else:
    print("Reprobado")
""",
        "nivel": "Avanzado",
    },
]


def listar_ejercicios() -> None:
    """Imprime un resumen de todos los ejercicios disponibles."""
    print(f"{'ID':<15} {'Categoría':<25} {'Nivel':<15} Título")
    print("─" * 80)
    for ej in EJERCICIOS:
        print(f"{ej['id']:<15} {ej['categoria']:<25} {ej['nivel']:<15} {ej['titulo']}")


def obtener_ejercicio(id_ejercicio: str) -> dict | None:
    """Devuelve el dict del ejercicio dado su ID, o None si no existe."""
    for ej in EJERCICIOS:
        if ej["id"] == id_ejercicio:
            return ej
    return None


def ejercicios_por_nivel(nivel: str) -> list[dict]:
    """Filtra ejercicios por nivel."""
    return [ej for ej in EJERCICIOS if ej["nivel"] == nivel]


def ejercicios_por_categoria(categoria: str) -> list[dict]:
    """Filtra ejercicios por categoría."""
    return [ej for ej in EJERCICIOS if ej["categoria"].lower() == categoria.lower()]


if __name__ == "__main__":
    listar_ejercicios()

