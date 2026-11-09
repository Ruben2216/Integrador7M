# Integrante 2 — Interfaz principal, grafo y formularios

## Alcance implementado

- Navegación Gradio entre **Inicio**, **Diagnóstico**, **Mi ruta**, **Actividad** y **Resultados**.
- Perfil de diagnóstico conectado con `Motor.consultar()`, incluyendo meta, temas acreditados y estado de la recomendación.
- Ruta con progreso, siguiente tema, pasos pendientes y lista de temas bloqueados.
- Grafo de ancho completo con un nodo por tema, avance de cuatro etapas, estado, ruta resaltada y selector accesible para mostrar niveles, prerrequisitos y recursos.
- Resolución de todos los IDs del grafo a título, formato, fuente y enlace mediante `catalogo_recursos.json`.
- Cada tema tiene niveles Básico, Intermedio y Avanzado de cinco preguntas; cada nivel requiere al menos cuatro aciertos. El laboratorio o práctica integradora se abre tras aprobar los tres niveles.
- La práctica POO en `ejercicios_poo.json` analiza la estructura del código Python sin ejecutarlo. Este análisis no verifica el comportamiento real del programa.
- Después de un intento, se presenta el resultado y se puede regresar a la ruta o elegir otra actividad.

## Criterios de estado

Un intento aprobado registra su etapa. El tema se acredita y el motor recalcula la ruta solo al aprobar las tres etapas y la práctica integradora. Las acreditaciones del archivo de progreso anterior se conservan como históricas, sin atribuirles etapas que no constan. Los reintentos de un nivel muestran las mismas preguntas.

## Ejecución y comprobación

Desde esta carpeta, en PowerShell:

```powershell
.\venv\Scripts\python.exe -X utf8 app.py
```

La aplicación inicia Gradio en `http://127.0.0.1:7860`. Para probar el flujo completo: genera la ruta en **Diagnóstico**, abre un tema desde **Mi ruta**, selecciona una actividad, envía respuestas y revisa **Resultados**. Los intentos acreditados se reflejan al volver a la ruta y al grafo.
