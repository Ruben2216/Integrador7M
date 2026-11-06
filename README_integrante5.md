# Integrante 5 — Refuerzo por concepto, Gemini y respaldo local

## Archivos

| Archivo | Descripción |
|---|---|
| `retroalimentacion.py` | Plan B (rúbrica local) y Plan A (Gemini Flash con respaldo) |
| `rubrica_retroalimentacion.json` | Acierto, punto por mejorar, pista y recurso por concepto y por criterio |
| `ejercicios_mvc_php.json` | Tema **Patrón MVC en PHP**: 4 ejercicios de laboratorio + 3 variantes de seguimiento (5 preguntas) |
| `calificador_mvc.py` | Calificación del tema MVC con el mismo resultado uniforme que `calificador.py` |
| `catalogo_recursos.json` | +9 recursos reales de MVC (enlaces verificados) |
| `tests/test_retroalimentacion.py` | 36 pruebas con pytest |
| `.env.example` | Plantilla de configuración de Gemini |

Cambios de integración: `interfaz.py` (actividades MVC, retroalimentación al calificar y botón
«Pedir explicación con IA»), `ui/resultados.py` (misma pantalla para la retroalimentación local y la de
Gemini), `simulacion.py` y `grafo_conocimiento.json` (recurso práctico de MVC).

## Instalación y arranque

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                     # abre http://127.0.0.1:7860
python -m pytest -q               # corre todas las pruebas
```

## Gemini (opcional)

1. Entra a <https://aistudio.google.com/apikey> con una cuenta de Google y crea una API key. Es gratis y no pide tarjeta.
2. Copia `.env.example` como `.env` y pega la clave: `GEMINI_API_KEY=tu_clave`.
3. Reinicia la app. En la pestaña **Resultados** debe decir «Gemini configurado».
4. Prueba rápida sin abrir la app: `python retroalimentacion.py --gemini`.

`.env` está en `.gitignore`: **nunca subas tu clave a GitHub**. Sin clave, la app funciona igual con el Plan B.

| Variable | Por defecto | Uso |
|---|---|---|
| `GEMINI_API_KEY` | — | Clave de Google AI Studio |
| `GEMINI_MODELO` | `gemini-3.5-flash,gemini-3.6-flash,gemini-flash-lite-latest` | Modelos en orden; si uno está saturado (503) o ya no existe (404), se usa el siguiente |
| `GEMINI_TIMEOUT` | `20` | Segundos máximos en total (cada modelo usa como máximo el 60 %); si se superan, se usa el Plan B |
| `GEMINI_DESACTIVADO` | — | `1` fuerza el Plan B aunque haya clave |

## Contrato

```python
from retroalimentacion import generar_retroalimentacion, solicitar_explicacion

retro = generar_retroalimentacion(resultado, formato_preferido="Texto")   # Plan B, inmediato
retro = solicitar_explicacion(resultado, formato_preferido="Texto")       # Plan A con respaldo
```

`resultado` puede ser la salida cruda de `calificador.py` o `calificador_mvc.py`, o la versión normalizada
que guarda `progreso.json`. Las dos funciones devuelven el mismo formato:

```json
{
  "origen": "local | gemini",
  "motivo_respaldo": "null o por qué no se usó Gemini",
  "tema": "Bases de Datos PostgreSQL",
  "concepto": "JOIN",
  "concepto_nombre": "Uniones con JOIN",
  "fallos_por_concepto": {"JOIN": 2},
  "acierto": "Filtras correctamente las filas con WHERE…",
  "mejora": "La unión de tablas no conserva todas las filas…",
  "pista": "Si faltan clientes sin pedidos, revisa cómo conservar las filas de la tabla de clientes…",
  "recurso": {"id": "Recurso_Lectura_LEFT_JOIN", "titulo": "…", "fuente": "…", "formato": "Lectura", "concepto": "JOIN", "enlace": "https://…"}
}
```

## Plan B: criterio reproducible

1. **Fallos por concepto**: en el laboratorio se cuentan los criterios incumplidos; en el seguimiento, las preguntas falladas.
2. **Concepto a reforzar**: el de más fallos. Si hay empate, gana el que aparece primero en la rúbrica (WHERE → JOIN → GROUP_BY → INTEGRADORA).
3. **Texto**: se usa el primer criterio incumplido *específico* de ese concepto. Los criterios marcados `generico` («el resultado coincide») solo se usan si no falló otro. Si la consulta no se pudo ejecutar, se explica el error.
4. **Acierto**: un concepto sin errores; si no lo hay, un criterio cumplido.
5. **Recurso**: el recurso del catálogo etiquetado con ese concepto, priorizando el formato preferido del estudiante (Visual → Video/Tutorial, Texto → Lectura/Referencia, Práctico → Práctica).

Ejemplo comprobable: dos seguimientos con **3 de 5**. El que falla JOIN recibe la pista «revisa cómo conservar las
filas de la tabla de clientes» y el recurso de LEFT JOIN. El que falla WHERE recibe la pista y el recurso de WHERE.

## Plan A: Gemini

- **Una solicitud por tema evaluado**, cuando el estudiante pulsa «Pedir explicación del intento con IA». Incluye los
  ejercicios con su rúbrica, los criterios cumplidos e incumplidos verificados y las respuestas del estudiante.
- Gemini solo redacta `acierto`, `mejora` y `pista` (JSON con esquema). El **concepto y el recurso los decide el
  sistema** desde el catálogo, así que el enlace siempre es real.
- Se usa el Plan B si: no hay clave, Gemini está desactivado, hay un error HTTP o de red, se supera el tiempo de espera,
  la respuesta llega cortada, falta un campo o es demasiado larga. El motivo se muestra en pantalla.
- La calificación, el guardado del intento y la ruta A\* ya están listos antes de pedir la explicación.

## Tema: Patrón MVC en PHP

| ID | Concepto | Dificultad | Qué evalúa |
|---|---|---|---|
| MVC-LAB01 | Responsabilidades por capa | Principiante | Clasificar fragmentos en Modelo, Vista o Controlador |
| MVC-LAB02 | Flujo de una petición | Intermedio | Ordenar enrutador → controlador → modelo → vista |
| MVC-LAB03 | Responsabilidad mal asignada | Avanzado | Corregir un controlador que mezcla SQL y HTML |
| MVC-LAB04 | Operación completa MVC | Integrador | Registrar un producto con validación (caso válido y con error) |

- Cada ejercicio tiene criterios verificables (opción correcta por criterio) y un `criterio_evaluacion`.
- **Acreditación**: la misma regla del equipo. Laboratorio: 3 de 4 con la integradora aprobada. Seguimiento: 4 de 5.
- **Seguimiento**: `mvc_variante_1..3`. Los nombres no chocan con las variantes de PostgreSQL y el reintento no repite variante.
- **Recursos**: CodeIgniter, Laravel, Symfony, PHP Manual, MDN, PHP: The Right Way y Wikipedia, todos etiquetados por concepto.
