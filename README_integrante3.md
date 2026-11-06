# Integrante 3 — Calificador y contenido de PostgreSQL

## Archivos creados

| Archivo | Descripción |
|---|---|
| `calificador.py` | Módulo principal de calificación (laboratorio + seguimiento) |
| `ejercicios_postgresql.json` | Banco de ejercicios: 4 de laboratorio + 3 variantes de seguimiento (5 preguntas c/u) |
| `catalogo_recursos.json` | Recursos de apoyo por concepto, con enlaces reales verificados |
| `tests/test_calificador.py` | 33 pruebas automatizadas con pytest |
| `README_integrante3.md` | Este archivo |

## Conceptos evaluados

La constante `CONCEPTOS_POSTGRESQL` define la lista canónica:

```python
from calificador import CONCEPTOS_POSTGRESQL
# ["WHERE", "JOIN", "GROUP_BY", "INTEGRADORA"]
```

## Formato de ejercicio (laboratorio)

```json
{
    "id": "PSQL-LAB01",
    "tema": "Bases_de_Datos_PostgreSQL",
    "tipo": "laboratorio",
    "concepto": "WHERE",
    "dificultad": "Principiante",
    "enunciado": "Escribe una consulta SQL que...",
    "esquema_sql": "CREATE TABLE ...; INSERT INTO ...;",
    "respuesta_esperada_sql": "SELECT ... WHERE ...;",
    "criterios": [
        {"id": "C01-WHERE", "descripcion": "Filtra solo...", "verificacion": "resultado_coincide"}
    ]
}
```

> **Nota:** El campo `tema` usa la clave con guion bajo del grafo (`Bases_de_Datos_PostgreSQL`), no el nombre legible del CSV, para que A* pueda consumirla sin traducción.

## Formato de resultado (calificación)

```json
{
    "intento": "uuid4 único",
    "tema": "Bases_de_Datos_PostgreSQL",
    "tipo": "laboratorio",
    "puntaje": 0.75,
    "tiempo": 245.5,
    "ejercicios_correctos": 3,
    "total_ejercicios": 4,
    "criterios_cumplidos": ["C01-WHERE", "C01-COLS", "..."],
    "criterios_incumplidos": ["C04-LEFT"],
    "conceptos_con_errores": ["INTEGRADORA"],
    "acreditado": false,
    "detalle": [
        {
            "id": "PSQL-LAB01",
            "concepto": "WHERE",
            "correcto": true,
            "criterios_cumplidos": ["C01-WHERE", "C01-COLS"],
            "criterios_incumplidos": [],
            "error": null
        }
    ]
}
```

## Funciones públicas

### `calificar_laboratorio(respuestas, tiempo, ...) -> dict`

```python
from calificador import calificar_laboratorio

resultado = calificar_laboratorio(
    respuestas={
        "PSQL-LAB01": "SELECT nombre, correo FROM clientes WHERE ciudad='Guadalajara';",
        "PSQL-LAB02": "SELECT c.nombre, p.total FROM clientes c LEFT JOIN pedidos p ON c.id = p.cliente_id;",
        "PSQL-LAB03": "SELECT ciudad, COUNT(*) AS cantidad FROM clientes GROUP BY ciudad ORDER BY cantidad DESC;",
        "PSQL-LAB04": "SELECT c.nombre, COUNT(p.id), COALESCE(SUM(p.total),0) FROM clientes c LEFT JOIN pedidos p ON c.id=p.cliente_id GROUP BY c.nombre ORDER BY 3 DESC;",
    },
    tiempo=245.5,
)
print(resultado["acreditado"])       # True / False
print(resultado["conceptos_con_errores"])  # ["JOIN"] / []
```

### `calificar_seguimiento(respuestas, tiempo, variante_usada, ...) -> dict`

```python
from calificador import calificar_seguimiento

resultado = calificar_seguimiento(
    respuestas={
        "PSQL-SEG-V1-01": "SELECT * FROM productos WHERE precio > 100;",
        "PSQL-SEG-V1-02": "LEFT JOIN",
        "PSQL-SEG-V1-03": "GROUP BY departamento",
        "PSQL-SEG-V1-04": "SELECT * FROM clientes WHERE nombre LIKE 'A%';",
        "PSQL-SEG-V1-05": "Se excluyen del resultado",
    },
    tiempo=120.0,
    variante_usada="variante_1",
)
```

### `obtener_variante_seguimiento(variantes_usadas) -> (nombre, preguntas)`

```python
from calificador import obtener_variante_seguimiento

nombre, preguntas = obtener_variante_seguimiento(variantes_usadas=[])
# nombre = "variante_1", preguntas = [5 dicts]

nombre2, preguntas2 = obtener_variante_seguimiento(variantes_usadas=["variante_1"])
# nombre2 = "variante_2", preguntas2 = [5 dicts distintos]
```

### `obtener_ejercicios_laboratorio() -> list[dict]`
### `obtener_conceptos() -> list[str]`

## Regla de acreditación del laboratorio

```python
from calificador import MIN_EJERCICIOS_APROBADOS, INTEGRADORA_OBLIGATORIA

# Actual: >= 3 de 4 correctos + integradora obligatoria
# Configurable cambiando las constantes en calificador.py
```

> **Para que el equipo apruebe:** actualmente se requieren ≥ 3/4 ejercicios correctos **incluyendo la integradora (PSQL-LAB04)**. Si prefieren otro criterio, solo hay que cambiar las constantes `MIN_EJERCICIOS_APROBADOS` e `INTEGRADORA_OBLIGATORIA` al inicio de `calificador.py`.

## Cómo correr las pruebas

```bash
# Desde la raíz del proyecto
python -m pytest tests/test_calificador.py -v
```

Se esperan **33 pruebas pasadas**, incluyendo:
- Laboratorio aprobado / reprobado
- 3/4 correctos sin integradora → reprobado
- LEFT JOIN vs INNER JOIN → distintos criterios
- SQL inválido y peligroso → puntaje 0 sin romper el programa
- Dos intentos de seguimiento con 3/5: mismo puntaje, distintos conceptos con errores
- Variantes sin repetición
- IDs de intento únicos (uuid4)

## Calificación SQL — Cómo funciona

1. Se crea una base SQLite3 **en memoria** con datos de ejemplo (definidos en cada ejercicio).
2. Se ejecuta la consulta del estudiante y la respuesta esperada.
3. Se comparan los resultados **sin importar el orden de las filas**.
4. Cada criterio se verifica de forma independiente.
5. La base se **reconstruye en cada calificación** — sin efectos secundarios.
6. Consultas inválidas, vacías o peligrosas dan puntaje 0 sin romper el programa.
7. Solo se permite SQL común a SQLite y PostgreSQL (WHERE, JOIN, GROUP BY, agregaciones).

## Recursos del catálogo

El archivo `catalogo_recursos.json` contiene recursos de apoyo por concepto, usando los IDs del grafo como llaves:

| Recurso | Concepto | Fuente |
|---|---|---|
| `Recurso_Video_DB` | JOIN | PostgreSQL Documentation |
| `Recurso_Practica_DB` | GROUP_BY | PostgreSQL Documentation |
| `Recurso_Lectura_WHERE` | WHERE | PostgreSQL Tutorial |
| `Recurso_Lectura_JOIN` | JOIN | PostgreSQL Tutorial |
| `Recurso_Lectura_LEFT_JOIN` | JOIN | PostgreSQL Tutorial |
| `Recurso_Lectura_GROUP_BY` | GROUP_BY | PostgreSQL Tutorial |
| `Recurso_Referencia_SELECT` | WHERE | PostgreSQL Documentation |
| `Recurso_Referencia_TABLE_EXPR` | INTEGRADORA | PostgreSQL Documentation |
| `Recurso_Referencia_SELECT_LIST` | WHERE | PostgreSQL Documentation |

Todos los enlaces han sido verificados como accesibles.

