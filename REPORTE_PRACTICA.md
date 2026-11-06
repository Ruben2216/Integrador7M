# Reporte de práctica: Recomendador de rutas de aprendizaje

## Datos generales

- **Proyecto:** Proyecto Integrador P2 — Equipo 4
- **Práctica:** Sistema de recomendación personalizada de recursos y rutas de aprendizaje
- **Integrantes:** Equipo 4

## Objetivo

Desarrollar un prototipo local que adapte las recomendaciones de estudio al perfil y avance del estudiante. El sistema combina un árbol de decisión, un grafo de conocimiento con búsqueda A*, reglas de producción y selección de recursos por formato. También incluye ejercicios de lógica y un módulo para calificar prácticas de SQL relacionadas con PostgreSQL.

## Desarrollo

### Recomendación y rutas

El motor carga telemetría simulada y un grafo de cinco temas. El árbol de decisión clasifica el tipo de apoyo requerido a partir del nivel previo, el formato preferido, el tema actual, el tiempo de interacción y la tasa de errores. El preprocesamiento imputa tiempos faltantes, codifica el nivel como variable ordinal y aplica codificación one-hot a las variables categóricas.

La búsqueda A* propone una ruta hacia la meta respetando los prerrequisitos y estima el costo según dificultad y nivel. Las reglas de producción atienden prerrequisitos pendientes, fallos repetidos y señales de abandono; el filtrado basado en contenido ordena los recursos según el formato preferido. El motor permite consultar recomendaciones, acreditar temas, cambiar de meta y recuperar una simulación.

### Interfaz

La aplicación presenta navegación Gradio entre inicio, diagnóstico, ruta, actividad y resultados. «Mi ruta» muestra la meta, el progreso, el siguiente tema y los pasos pendientes. El grafo distingue temas acreditados, disponibles y bloqueados; al seleccionar un tema se muestran su estado, prerrequisitos pendientes y enlaces del catálogo con título, formato y fuente.

La vista de actividades integra el laboratorio de cuatro ejercicios PostgreSQL, el seguimiento de cinco preguntas con variantes y la práctica asignada de POO (clases y objetos, comportamiento, encapsulamiento y colaboración entre `Pedido` y `Producto`). Los intentos PostgreSQL usan el calificador existente y sincronizan el progreso cuando se acredita el tema. La práctica abierta de POO se entrega para revisión y no se marca como acreditada automáticamente.

### Calificación PostgreSQL

El módulo de calificación contiene cuatro ejercicios de laboratorio sobre `WHERE`, `JOIN`, `GROUP BY` e integración. Ejecuta las consultas en una base SQLite temporal, compara sus resultados con las respuestas esperadas y genera un resultado serializable. Se acredita el laboratorio con al menos tres respuestas correctas, incluida la integradora. El banco también ofrece variantes de seguimiento sin repetir las ya utilizadas.

## Verificación y resultados

- La demostración del motor terminó correctamente e incluyó escenarios de rutas desde cero, acreditación y bloqueo por prerrequisitos, cierre de meta, coherencia entre árbol y grafo, cambio de meta, recuperación de simulación, ruta directa y ejercicios de lógica.
- Se probó la calificación integral del laboratorio: **4 de 4 ejercicios correctos; acreditado, puntaje 1.0**.
- La interfaz integrada se probó a través de su API local: consulta de ruta y detalle de tema, entrega de POO, acreditación del laboratorio y dos variantes de seguimiento consecutivas sin repetición.
- La ejecución inicial de la demostración en la consola Windows falló al imprimir caracteres Unicode con la codificación local. Se ejecutó satisfactoriamente con UTF-8 (`-X utf8`).
- No se ejecutó la suite `pytest`: el entorno virtual del proyecto no tiene instalado ese paquete. La verificación directa anterior no sustituye la ejecución de las pruebas automatizadas.

## Conclusiones

El prototipo integra técnicas de inteligencia artificial simbólica y aprendizaje automático para ofrecer recomendaciones explicables y rutas que respetan los prerrequisitos. La demostración valida los principales escenarios de navegación y el calificador reconoce el caso completo del laboratorio. Para una evaluación académica real se deberá reemplazar la telemetría simulada por datos apropiados y revisar los resultados con el docente; las recomendaciones son apoyo y no un diagnóstico definitivo.

## Ejecución local

Desde la carpeta `Integrador7M`, en PowerShell, iniciar la interfaz con:

```powershell
.\venv\Scripts\python.exe -X utf8 app.py
```

La aplicación abre Gradio en el navegador. Para iniciar el servidor sin abrirlo automáticamente:

```powershell
.\venv\Scripts\python.exe -X utf8 app.py --no-browser
```
