# Integrante 2 — Interfaz principal, grafo y formularios

## Alcance implementado

- Navegación Gradio entre **Inicio**, **Diagnóstico**, **Mi ruta**, **Actividad** y **Resultados**.
- Perfil de diagnóstico conectado con `Motor.consultar()`, incluyendo meta, temas acreditados y estado de la recomendación.
- Ruta con progreso, siguiente tema, pasos pendientes y lista de temas bloqueados.
- Grafo interactivo mediante el selector de tema: colores para temas acreditados, disponibles y bloqueados; al seleccionar un tema se muestran su estado, prerrequisitos pendientes y recursos.
- Resolución de todos los IDs del grafo a título, formato, fuente y enlace mediante `catalogo_recursos.json`.
- Laboratorio de cuatro ejercicios PostgreSQL y seguimiento de cinco preguntas con variantes sin repetición, calificados con `calificador.py`.
- Práctica asignada de POO en `ejercicios_poo.json`: clases y objetos, comportamiento, encapsulamiento y colaboración entre `Pedido` y `Producto`.
- Después de un intento, se presenta el resultado y se puede regresar a la ruta o elegir otra actividad.

## Criterios de estado

Los intentos PostgreSQL actualizan el tema acreditado y recalculan la ruta cuando cumplen la regla del calificador. La práctica abierta de POO muestra su lista de revisión y queda marcada como entrega para revisión; no acredita el tema automáticamente porque no hay un evaluador de código POO en el proyecto.

## Ejecución y comprobación

Desde esta carpeta, en PowerShell:

```powershell
.\venv\Scripts\python.exe -X utf8 app.py
```

La aplicación inicia Gradio en `http://127.0.0.1:7860`. Para probar el flujo completo: genera la ruta en **Diagnóstico**, abre un tema desde **Mi ruta**, selecciona una actividad, envía respuestas y revisa **Resultados**. Los intentos acreditados se reflejan al volver a la ruta y al grafo.
