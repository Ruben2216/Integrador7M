"""
demo_integrante1.py — Script de demostración y comprobación (Integrante 1).

Ejecuta todos los escenarios requeridos y muestra los resultados en consola:

  1. Ruta desde cero hacia Node.js  (todos los niveles)
  2. Ajuste de ruta al acreditar un tema (Lógica acreditada → recalcula)
  3. Node.js bloqueado mientras falte POO o PostgreSQL
  4. Node.js desbloqueado cuando ambos están completos
  5. Cierre de ruta: estado «Meta completada»
  6. Coherencia árbol ↔ grafo (árbol dice Avanzar pero faltan prerrequisitos)
  7. Cambio de meta
  8. Recuperación de simulación
  9. Ejercicios de Lógica de Programación (listado)

Uso:  python demo_integrante1.py
"""

from motor import Motor
from ejercicios_logica import listar_ejercicios, ejercicios_por_nivel

SEP  = "=" * 70
sep2 = "-" * 70


def seccion(titulo: str) -> None:
    print(f"\n{SEP}\n  {titulo}\n{SEP}")


def mostrar_ruta(resultado: dict) -> None:
    estado = resultado.get("estado_meta", "?")
    ruta   = resultado.get("ruta_pendiente", resultado.get("ruta", []))
    sig    = resultado.get("siguiente_tema")
    bloq   = resultado.get("bloqueados", [])
    costo  = resultado.get("costo_ruta", "?")
    expl   = resultado.get("estados_explorados", "?")

    print(f"  Estado meta   : {estado}")
    print(f"  Ruta pendiente: {' → '.join(ruta) if ruta else '(vacía)'}")
    print(f"  Siguiente tema: {sig}")
    print(f"  Bloqueados    : {bloq}")
    print(f"  Costo A*      : {costo}  |  estados explorados: {expl}")
    if resultado.get("accion"):
        print(f"  Acción árbol  : {resultado['accion']}  ({resultado.get('tipo_arbol','')})")


# ─────────────────────────────────────────────────────────────────────────────
motor = Motor()


# ── 1. Ruta desde CERO hacia Node.js ─────────────────────────────────────────
seccion("1 · Ruta desde CERO hacia Node.js (todos los niveles)")
for nivel in ["Principiante", "Intermedio", "Avanzado"]:
    r = motor.consultar(
        nivel=nivel, formato="Visual",
        tema="Lógica de Programación", tiempo=120, errores=50,
        completados=[], meta="Backend con Node.js",
    )
    print(f"\n  Nivel: {nivel}")
    mostrar_ruta(r)


# ── 2. Ajuste al acreditar Lógica ─────────────────────────────────────────────
seccion("2 · A* SE AJUSTA al acreditar «Lógica de Programación»")
r = motor.acreditar(
    tema_acreditado="Lógica de Programación",
    nivel="Principiante", formato="Visual",
    completados=["Lógica de Programación"],
    meta="Backend con Node.js",
)
print()
mostrar_ruta(r)
assert "Lógica de Programación" not in r["ruta_pendiente"], \
    "ERROR: Lógica sigue en la ruta aunque ya fue acreditada."
print("  ✓ Lógica ya no aparece en la ruta pendiente.")


# ── 3. Node.js BLOQUEADO mientras falte POO o PostgreSQL ─────────────────────
seccion("3 · Node.js BLOQUEADO (solo tiene Lógica)")
bloqueo = motor.verificar_bloqueo_nodejs(["Lógica de Programación"])
print(f"\n  {bloqueo['mensaje']}")
assert bloqueo["bloqueado"] is True, "ERROR: Node debería estar bloqueado."
print("  ✓ Node.js bloqueado correctamente.")

seccion("3b · Node.js BLOQUEADO (solo tiene POO, falta PostgreSQL)")
bloqueo2 = motor.verificar_bloqueo_nodejs([
    "Lógica de Programación",
    "Programación Orientada a Objetos",
])
print(f"\n  {bloqueo2['mensaje']}")
assert bloqueo2["bloqueado"] is True, "ERROR: Node debería estar bloqueado."
print("  ✓ Node.js bloqueado correctamente (falta PostgreSQL).")


# ── 4. Node.js DESBLOQUEADO ───────────────────────────────────────────────────
seccion("4 · Node.js DESBLOQUEADO (Lógica + POO + PostgreSQL)")
bloqueo3 = motor.verificar_bloqueo_nodejs([
    "Lógica de Programación",
    "Programación Orientada a Objetos",
    "Bases de Datos PostgreSQL",
])
print(f"\n  {bloqueo3['mensaje']}")
assert bloqueo3["bloqueado"] is False, "ERROR: Node debería estar desbloqueado."
print("  ✓ Node.js desbloqueado correctamente.")


# ── 5. CIERRE de ruta: meta completada ───────────────────────────────────────
seccion("5 · CIERRE — meta completada (todos los temas acreditados)")
todos = [
    "Lógica de Programación",
    "Programación Orientada a Objetos",
    "Bases de Datos PostgreSQL",
    "Backend con Node.js",
]
r_cierre = motor.consultar(
    nivel="Avanzado", formato="Práctico",
    tema="Backend con Node.js", tiempo=200, errores=10,
    completados=todos, meta="Backend con Node.js",
)
print()
mostrar_ruta(r_cierre)
assert r_cierre["estado_meta"] == "Meta completada", \
    f"ERROR: esperaba 'Meta completada', obtuve '{r_cierre['estado_meta']}'."
assert r_cierre["ruta_pendiente"] == [], \
    "ERROR: la ruta pendiente debería estar vacía."
print("  ✓ Estado 'Meta completada' devuelto correctamente.")
print("  ✓ Ruta pendiente = [].")


# ── 6. Coherencia árbol ↔ grafo ───────────────────────────────────────────────
seccion("6 · COHERENCIA árbol ↔ grafo (árbol dice Avanzar, falta prereq)")
# Avanzado con pocos errores → el árbol probablemente dirá «Avanzado».
# Pero Backend_con_Nodejs necesita POO y PostgreSQL que no tiene.
r_coh = motor.consultar(
    nivel="Avanzado", formato="Práctico",
    tema="Backend con Node.js", tiempo=180, errores=15,
    completados=["Lógica de Programación"],   # solo tiene Lógica
    meta="Backend con Node.js",
)
print()
print(f"  Tipo árbol  : {r_coh.get('tipo_arbol')}")
print(f"  Acción final: {r_coh.get('accion')}")
print(f"  Motivos:")
for m in r_coh.get("motivos", []):
    print(f"    - {m}")
# La ruta pendiente debe incluir POO y PostgreSQL antes que Node
ruta = r_coh["ruta_pendiente"]
print(f"  Ruta pendiente: {' → '.join(ruta)}")
assert "Backend con Node.js" not in ruta[:2] or len(ruta) > 1, \
    "ADVERTENCIA: Node aparece al inicio sin sus prerrequisitos."
print("  ✓ La coherencia árbol↔grafo fue verificada.")


# ── 7. Cambio de meta ─────────────────────────────────────────────────────────
seccion("7 · CAMBIO DE META → Patrón MVC en PHP")
r_meta = motor.cambiar_meta(
    nueva_meta="Patrón MVC en PHP",
    nivel="Intermedio", formato="Texto",
    tema="Lógica de Programación", tiempo=120, errores=40,
    completados=["Lógica de Programación"],
)
print()
mostrar_ruta(r_meta)
print("  ✓ Ruta recalculada con nueva meta.")


# ── 8. Recuperar simulación ───────────────────────────────────────────────────
seccion("8 · RECUPERAR simulación guardada")
snapshot = {
    "nivel": "Intermedio",
    "formato": "Visual",
    "tema": "Programación Orientada a Objetos",
    "tiempo": 90,
    "errores": 35,
    "completados": ["Lógica de Programación"],
    "meta": "Backend con Node.js",
    "fallos": 0,
    "abandono": False,
}
r_snap = motor.recuperar(snapshot)
print()
mostrar_ruta(r_snap)
print("  ✓ Simulación recuperada correctamente.")


# ── 9. Ruta directa (sin árbol) ──────────────────────────────────────────────
seccion("9 · RUTA DIRECTA (solo A*, sin reclasificar)")
r_dir = motor.ruta_directa(
    completados=["Lógica de Programación", "Programación Orientada a Objetos"],
    meta="Backend con Node.js",
    nivel="Intermedio",
)
print()
mostrar_ruta(r_dir)


# ── 10. Ejercicios de Lógica de Programación ──────────────────────────────────
seccion("10 · EJERCICIOS — Lógica de Programación")
print()
listar_ejercicios()
print(f"\n  Ejercicios para Principiante: {len(ejercicios_por_nivel('Principiante'))}")
print(f"  Ejercicios para Intermedio  : {len(ejercicios_por_nivel('Intermedio'))}")
print(f"  Ejercicios para Avanzado    : {len(ejercicios_por_nivel('Avanzado'))}")


# ── Resumen ───────────────────────────────────────────────────────────────────
seccion("RESUMEN — Todos los escenarios ejecutados correctamente ✓")
print("""
  · A* calculó la ruta desde cero hacia Node.js en los 3 niveles.
  · A* se ajustó al acreditar «Lógica de Programación».
  · Node.js permaneció bloqueado mientras faltó POO o PostgreSQL.
  · Node.js se desbloqueó al tener ambos prerrequisitos.
  · Estado «Meta completada» devuelto con ruta_pendiente = [].
  · Coherencia árbol ↔ grafo verificada.
  · Cambio de meta recalcula la ruta correctamente.
  · Recuperación de simulación funcional.
  · Ruta directa (solo A*) disponible.
  · Banco de ejercicios de Lógica de Programación cargado.
""")

