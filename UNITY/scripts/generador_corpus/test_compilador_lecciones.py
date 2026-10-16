"""
test_compilador_lecciones.py
Suite integral de pruebas unitarias y de integración para el compilador de lecciones (versión 4).
Verifica todos los criterios de aceptación de:
  - UNITY/instrucciones-mejora-compilador-lecciones.md
  - UNITY/instrucciones-ajustes-finales-lecciones-compiladas.md
  - 01-modulo-pln-texto.md
  - 02-modulo-asr-voz.md
  - 04-flujo-leccion-app.md
  - 05-guia-corpus-datos.md
  - 08-patron-arquitectonico-mvp.md
"""

import os
import sys
import json
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UNITY_SCRIPTS_DIR = os.path.dirname(SCRIPT_DIR)
UNITY_DIR = os.path.dirname(UNITY_SCRIPTS_DIR)
PROJECT_ROOT = os.path.dirname(UNITY_DIR)
DATOS_APP = os.path.join(UNITY_DIR, "datos_app")

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if UNITY_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, UNITY_SCRIPTS_DIR)

from compilador_lecciones import (
    CATALOGO_22,
    MECANICA_POR_TIPO,
    RECONSTRUCCION_TIPOS
)
from distractores_corpus import NOMBRES_PROPIOS_CONTEXTUALES


class TestCompiladorLecciones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ruta_compiladas = os.path.join(DATOS_APP, "lecciones_compiladas.json")
        cls.ruta_palabras = os.path.join(DATOS_APP, "palabras.json")
        cls.ruta_oraciones = os.path.join(DATOS_APP, "oraciones.json")
        cls.ruta_lecciones = os.path.join(DATOS_APP, "lecciones.json")

        with open(cls.ruta_compiladas, "r", encoding="utf-8") as f:
            cls.data_compiladas = json.load(f)
        with open(cls.ruta_palabras, "r", encoding="utf-8") as f:
            cls.data_palabras = json.load(f)
        with open(cls.ruta_oraciones, "r", encoding="utf-8") as f:
            cls.data_oraciones = json.load(f)
        with open(cls.ruta_lecciones, "r", encoding="utf-8") as f:
            cls.data_lecciones = json.load(f)

        cls.lecciones = cls.data_compiladas.get("lecciones", [])

        cls.audios_palabras = {
            os.path.splitext(f)[0] for f in os.listdir(os.path.join(UNITY_DIR, "audios_palabras"))
        }
        cls.audios_oraciones = {
            os.path.splitext(f)[0] for f in os.listdir(os.path.join(UNITY_DIR, "audios_oraciones"))
        }

    def test_version_contrato_unity(self):
        """Verifica que lecciones_compiladas.json sea versión 4."""
        self.assertEqual(self.data_compiladas.get("version"), 4)

    def test_catalogo_22_tipos_y_retiro_memoria(self):
        """Verifica que solo se emitan tipos del catálogo 22 y que memoria_uch_es tenga 0 pasos."""
        tipos_emitidos = set()
        conteo_memoria = 0
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                t = paso.get("tipo")
                tipos_emitidos.add(t)
                if t == "memoria_uch_es":
                    conteo_memoria += 1

        self.assertEqual(conteo_memoria, 0, "memoria_uch_es no debe ser generada en lecciones_compiladas.json")
        tipos_desconocidos = tipos_emitidos - CATALOGO_22
        self.assertEqual(len(tipos_desconocidos), 0, f"Tipos desconocidos emitidos: {tipos_desconocidos}")
        self.assertEqual(len(tipos_emitidos), 22, f"Se esperaban exactamente 22 tipos generados, se obtuvieron {len(tipos_emitidos)}")

    def test_cobertura_27_lecciones_y_120_oraciones(self):
        """Verifica que las 27 lecciones existan y que las 120 oraciones curriculares estén cubiertas."""
        self.assertEqual(len(self.lecciones), 27)
        lids = [l["id"] for l in self.lecciones]
        esperados_lids = [f"L{i:02d}" for i in range(1, 28)]
        self.assertEqual(lids, esperados_lids)

        oraciones_evaluadas = set()
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                if paso.get("oracion_id"):
                    oraciones_evaluadas.add(paso["oracion_id"])

        esperadas_oraciones = {f"O_{i:03d}" for i in range(1, 121)}
        self.assertTrue(esperadas_oraciones.issubset(oraciones_evaluadas),
                        f"Faltan oraciones curriculares por evaluar: {esperadas_oraciones - oraciones_evaluadas}")

    def test_presentacion_y_microactividad_inmediata(self):
        """Verifica exactamente una presentación y microactividad inmediata compatible por familia nueva."""
        tipos_micro_validos = {
            "uch_a_es", "es_a_uch", "audio_a_uch", "audio_a_es",
            "forma_a_raiz", "forma_a_es", "es_a_forma", "audio_a_forma"
        }
        for lec in self.lecciones:
            lid = lec["id"]
            pasos = lec.get("pasos", [])
            fn_set = set(lec.get("familias_nuevas", []))

            pres_indices = []
            for idx, p in enumerate(pasos):
                if p.get("tipo") == "presentacion_familia":
                    pres_indices.append((idx, p.get("objetivo_id")))

            self.assertEqual(len(pres_indices), len(fn_set),
                             f"En {lid}, se esperaban {len(fn_set)} presentaciones y hay {len(pres_indices)}")

            for idx, fid in pres_indices:
                self.assertLess(idx + 1, len(pasos), f"En {lid}, presentacion en {idx} sin paso siguiente")
                siguiente = pasos[idx + 1]
                t_sig = siguiente.get("tipo")
                self.assertIn(t_sig, tipos_micro_validos,
                              f"En {lid}, paso {idx+1} tras presentacion no es microactividad: {t_sig}")

    def test_alternancia_reconstruccion_oraciones(self):
        """Verifica que no haya pares consecutivos de reconstrucción, excepto el caso inevitable de L27."""
        total_pares = 0
        for lec in self.lecciones:
            lid = lec["id"]
            pasos = lec.get("pasos", [])
            pares_en_lec = 0
            for i in range(len(pasos) - 1):
                t1 = pasos[i].get("tipo")
                t2 = pasos[i + 1].get("tipo")
                if t1 in RECONSTRUCCION_TIPOS and t2 in RECONSTRUCCION_TIPOS:
                    pares_en_lec += 1
            if lid != "L27":
                self.assertEqual(pares_en_lec, 0, f"En {lid}, se encontraron {pares_en_lec} pares de reconstrucción contiguos")
            else:
                self.assertLessEqual(pares_en_lec, 2, f"En L27, pares de reconstrucción exceden el límite de excepción: {pares_en_lec}")
            total_pares += pares_en_lec
        self.assertLessEqual(total_pares, 2, f"Pares de reconstrucción totales exceden el objetivo ({total_pares} > 2)")

    def test_espaciado_escritura_misma_forma(self):
        """Verifica separación de >=3 pasos entre evaluación de forma y escribir_forma en L08, L11 y L17."""
        casos_control = {
            "L08": "chhaqchay",
            "L11": "chhukchay",
            "L17": "chiwkisnaka"
        }
        lec_map = {l["id"]: l for l in self.lecciones}

        for lid, forma_id in casos_control.items():
            pasos = lec_map[lid]["pasos"]
            eval_idx = None
            escritura_idx = None

            for i, p in enumerate(pasos):
                t = p.get("tipo")
                fid = p.get("forma_id")
                if fid == forma_id:
                    if t != "escribir_forma" and eval_idx is None:
                        eval_idx = i
                    elif t == "escribir_forma" and escritura_idx is None:
                        escritura_idx = i

            if eval_idx is not None and escritura_idx is not None:
                distancia = escritura_idx - eval_idx - 1
                self.assertGreaterEqual(
                    distancia, 3,
                    f"En {lid}, forma '{forma_id}' evaluada en {eval_idx} y escrita en {escritura_idx} (distancia: {distancia} < 3)"
                )

    def test_seleccion_oracion_asr_l04(self):
        """Verifica que el ASR de oración en L04 no seleccione la oración unipalabra O_011."""
        lec_map = {l["id"]: l for l in self.lecciones}
        l04 = lec_map["L04"]
        asr_pasos = [p for p in l04["pasos"] if p.get("tipo") == "escucha_y_repite_oracion_asr"]
        self.assertEqual(len(asr_pasos), 1, "L04 debe tener exactamente 1 paso de ASR de oración")
        target_oid = asr_pasos[0].get("oracion_id")
        self.assertNotEqual(target_oid, "O_011", "ASR de oración en L04 no debe seleccionar O_011 (1 solo token)")
        self.assertIn(target_oid, ["O_012", "O_013", "O_014"], f"ASR de oración en L04 seleccionó {target_oid}")

    def test_validez_completar_oracion(self):
        """Verifica que todos los pasos de completar_oracion tengan estructura, pista en español y distractores curriculares válidos."""
        oraciones_dict = {o["id"]: o for o in self.data_oraciones["oraciones"]}
        vocabulario_acumulado = set()

        for lec in self.lecciones:
            lid = lec["id"]
            vocabulario_acumulado.update(lec.get("familias_nuevas", []))

            for idx, paso in enumerate(lec.get("pasos", [])):
                if paso.get("tipo") == "completar_oracion":
                    oculta = paso.get("palabra_oculta_id")
                    opciones = paso.get("opciones_ids", [])
                    oid = paso.get("oracion_id")
                    consigna = paso.get("consigna", "")

                    self.assertTrue(oculta, f"En {lid}, paso {idx} sin palabra_oculta_id")
                    self.assertIn(oculta, opciones, f"En {lid}, paso {idx} {oculta} no está en opciones_ids")
                    self.assertEqual(len(opciones), len(set(opciones)), f"En {lid}, paso {idx} opciones duplicadas")
                    self.assertTrue(2 <= len(opciones) <= 4, f"En {lid}, paso {idx} debe tener 2 a 4 opciones (tiene {len(opciones)})")
                    self.assertNotIn(oculta.lower(), NOMBRES_PROPIOS_CONTEXTUALES, f"En {lid} nombre propio oculto")

                    # Verificar pista en español de la misma oración
                    self.assertIn(oid, oraciones_dict, f"En {lid}, oración {oid} no encontrada")
                    es_esperado = oraciones_dict[oid]["es"]
                    self.assertIn(es_esperado, consigna, f"En {lid}, la consigna '{consigna}' no contiene la traducción '{es_esperado}'")

                    # En L01, verificar específicamente O_002 y wakpacha
                    if lid == "L01":
                        self.assertEqual(oid, "O_002", "L01 debe usar O_002 en completar_oracion")
                        self.assertEqual(oculta, "wakpacha", "L01 debe tener 'wakpacha' como palabra oculta")

                    # Verificar que todas las opciones pertenezcan al vocabulario ya introducido
                    for op in opciones:
                        self.assertIn(op, vocabulario_acumulado, f"En {lid}, opción '{op}' no ha sido introducida aún")


    def test_unicidad_par_tipo_objetivo(self):
        """Verifica que dentro de una misma lección no se evalúe dos veces el mismo par (tipo, objetivo)."""
        for lec in self.lecciones:
            lid = lec["id"]
            pares_vistos = set()
            for idx, paso in enumerate(lec.get("pasos", [])):
                tipo = paso.get("tipo")
                obj = paso.get("objetivo_id") or paso.get("forma_id") or paso.get("oracion_id")
                if tipo in ["presentacion_familia", "familia_completa", "emparejar_uch_es", "emparejar_audio_uch"]:
                    continue
                if obj:
                    par = (tipo, obj)
                    self.assertNotIn(par, pares_vistos, f"En {lid}, par duplicado {par} en paso {idx}")
                    pares_vistos.add(par)

    def test_distribucion_y_validez_asr(self):
        """Verifica que los pasos ASR tengan opcional: true, audio válido y estén intercalados."""
        for lec in self.lecciones:
            lid = lec["id"]
            pasos = lec.get("pasos", [])
            n_pasos = len(pasos)

            for idx, paso in enumerate(pasos):
                t = paso.get("tipo")
                if t == "escucha_y_repite_asr":
                    self.assertTrue(paso.get("opcional"), f"En {lid}, ASR en paso {idx} sin opcional: true")
                    self.assertIn(paso.get("objetivo_id"), self.audios_palabras,
                                  f"En {lid}, ASR léxico en paso {idx} sin audio en audios_palabras")
                    self.assertLess(idx, n_pasos - 2, f"En {lid}, ASR léxico colocado al final en paso {idx}/{n_pasos}")
                elif t == "escucha_y_repite_oracion_asr":
                    self.assertTrue(paso.get("opcional"), f"En {lid}, ASR oración en paso {idx} sin opcional: true")
                    self.assertIn(paso.get("oracion_id"), self.audios_oraciones,
                                  f"En {lid}, ASR oración en paso {idx} sin audio en audios_oraciones")

    def test_presupuestos_escritura_y_consignas(self):
        """Verifica cuotas de escritura, consignas explícitas y refuerzos al fallar válidos."""
        for lec in self.lecciones:
            lid = lec["id"]
            pasos = lec.get("pasos", [])
            fn_cnt = len(lec.get("familias_nuevas", []))

            esc_lexicas = [p for p in pasos if p.get("tipo") in ["escribir_palabra", "escribir_forma"]]
            esc_oracion = [p for p in pasos if p.get("tipo") == "escribir_oracion"]

            cuota_esperada = 1 if fn_cnt <= 4 else (2 if fn_cnt <= 8 else 3)
            self.assertEqual(len(esc_lexicas), cuota_esperada,
                             f"En {lid}, escrituras léxicas={len(esc_lexicas)}, esperadas={cuota_esperada}")
            self.assertLessEqual(len(esc_oracion), 1, f"En {lid}, más de 1 escribir_oracion")

            for p in esc_lexicas + esc_oracion:
                self.assertIn("consigna", p, f"En {lid}, paso de escritura sin consigna")
                self.assertIn("refuerzo_al_fallar", p, f"En {lid}, paso de escritura sin refuerzo_al_fallar")
                ref = p["refuerzo_al_fallar"]
                self.assertIn(ref["tipo"], CATALOGO_22, f"En {lid}, tipo de refuerzo inválido: {ref['tipo']}")

    def test_densidad_l08_y_l27(self):
        """Verifica que L08 y L27 cumplan los umbrales de densidad especificados."""
        lec_map = {l["id"]: l for l in self.lecciones}
        l08_pasos = len(lec_map["L08"]["pasos"])
        l27_pasos = len(lec_map["L27"]["pasos"])

        self.assertLessEqual(l08_pasos, 39, f"L08 excede el umbral de revisión (39): {l08_pasos}")
        self.assertLessEqual(l27_pasos, 48, f"L27 excede el umbral de revisión pedagógica (48): {l27_pasos}")


if __name__ == "__main__":
    unittest.main()
