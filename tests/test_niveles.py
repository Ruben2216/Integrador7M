"""Flujos completos de niveles, migración y acreditación."""
import json

import pytest

from calificador_poo import calificar_laboratorio_poo
from integracion_calificador import normalizar_resultado_calificador
from niveles import calificar_nivel, preguntas_nivel
from progreso import AlmacenProgreso, ETAPAS, TEMAS, etapas_aprobadas, siguiente_etapa


@pytest.mark.parametrize("tema", TEMAS)
@pytest.mark.parametrize("etapa", ETAPAS[:3])
def test_banco_tiene_cinco_preguntas_estables_y_calificables(tema, etapa):
    preguntas = preguntas_nivel(tema, etapa)
    assert preguntas == preguntas_nivel(tema, etapa)
    assert len(preguntas) == len({p["id"] for p in preguntas}) == 5
    assert all(p["respuesta_correcta"] in p["opciones"] and
               len(set(p["opciones"])) == 4 for p in preguntas)
    respuestas = {p["id"]: p["respuesta_correcta"] for p in preguntas[:4]}
    aprobado = calificar_nivel(tema, etapa, respuestas, 30)
    assert aprobado["correctas"] == 4
    assert aprobado["acreditado"] is True
    respuestas.pop(preguntas[3]["id"])
    assert calificar_nivel(tema, etapa, respuestas, 30)["acreditado"] is False


def _intento(tema, etapa, aprobado=True):
    return {"id": f"{tema}-{etapa}-{aprobado}", "tema": tema,
            "tipo_actividad": "Nivel de aprendizaje", "etapa": etapa,
            "puntaje": 4 if aprobado else 3, "tiempo_segundos": 20,
            "conceptos_con_error": [], "aprobado": aprobado}


def test_solo_cuatro_etapas_acreditan_y_reapertura_conserva_avance(tmp_path):
    almacen = AlmacenProgreso(tmp_path / "progreso.json")
    tema = TEMAS[0]
    almacen.iniciar(tema, "Texto")
    with pytest.raises(ValueError, match="etapas anteriores"):
        almacen.guardar_intento(_intento(tema, "integradora"))
    almacen.guardar_intento(_intento(tema, "basico", False))
    assert siguiente_etapa(almacen.cargar(), tema) == "basico"
    for etapa in ETAPAS[:3]:
        estado = almacen.guardar_intento(_intento(tema, etapa))
        assert tema not in estado["temas_acreditados"]
    assert siguiente_etapa(almacen.cargar(), tema) == "integradora"
    estado = almacen.guardar_intento(_intento(tema, "integradora"))
    assert estado["temas_acreditados"][tema]["origen"] == "ruta por niveles"
    assert siguiente_etapa(AlmacenProgreso(almacen.ruta).cargar(), tema) is None
    assert etapas_aprobadas(estado, tema) == set(ETAPAS)
    assert len(almacen.guardar_intento(_intento(tema, "integradora"))["intentos"]) == 5


def test_acreditacion_previa_se_conserva_sin_fabricar_etapas(tmp_path):
    ruta = tmp_path / "progreso.json"
    antiguo = AlmacenProgreso(ruta).iniciar(TEMAS[0], "Texto")
    antiguo["version"] = 1
    antiguo["temas_acreditados"][TEMAS[0]] = {"origen": "diagnóstico", "intento_id": "viejo"}
    ruta.write_text(json.dumps(antiguo), encoding="utf-8")
    estado = AlmacenProgreso(ruta).cargar()
    assert estado["version"] == 2
    assert estado["temas_acreditados"][TEMAS[0]]["legado"] is True
    assert etapas_aprobadas(estado, TEMAS[0]) == set()
    assert siguiente_etapa(estado, TEMAS[0]) is None
    assert json.loads(ruta.read_text(encoding="utf-8"))["version"] == 1


def test_poo_se_califica_por_estructura_sin_ejecutar_codigo():
    respuestas = {
        "POO-01": "class Libro:\n def __init__(self, titulo, autor):\n  self.titulo=titulo\n  self.autor=autor\n def describir(self):\n  return self.titulo + self.autor\na=Libro('a','x')\nb=Libro('b','y')",
        "POO-02": "class CuentaBancaria:\n def __init__(self, saldo):\n  self.saldo=saldo\n def depositar(self, monto):\n  if monto>0: self.saldo+=monto\n def retirar(self, monto):\n  if monto<=self.saldo: self.saldo-=monto",
        "POO-03": "class Producto:\n def __init__(self, stock):\n  self._stock=stock\n def vender(self, unidades):\n  if unidades<=self._stock: self._stock-=unidades\n def consultar_stock(self):\n  return self._stock",
        "POO-04": "class Producto:\n def __init__(self, precio, cantidad):\n  self.precio=precio\n  self.cantidad=cantidad\nclass Pedido:\n def calcular_total(self):\n  total=0\n  for p in self.productos:\n   total+=p.precio*p.cantidad\n  return total\nraise RuntimeError('nunca ejecutar')",
    }
    resultado = calificar_laboratorio_poo(respuestas, 30)
    assert resultado["acreditado"] is True
    assert resultado["ejercicios_correctos"] == 4
    assert normalizar_resultado_calificador(resultado)["etapa"] == "integradora"
