"""
test_compilador_lecciones.py (Versión 11 Tipos - Suite de Pruebas Automatizadas)
Verifica rigurosamente todos los criterios de aceptación y casos de regresión de:
  - INSTRUCCIONES_AGENTE_RECOMPILACION_LECCIONES_UCHUMATAQU.md
  - 01-modulo-pln-texto.md
  - 02-modulo-asr-voz.md
  - 04-flujo-leccion-app.md
  - 05-guia-corpus-datos.md
  - 08-patron-arquitectonico-mvp.md
"""

import os
import sys
import json
import hashlib
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
    CATALOGO_11,
    TIPOS_RETIRADOS,
    MECANICA_POR_TIPO
)
from distractores_corpus import normalizar_texto, NOMBRES_PROPIOS_CONTEXTUALES


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
        """Verifica que lecciones_compiladas.json sea versión 4 para compatibilidad con Unity."""
        self.assertEqual(self.data_compiladas.get("version"), 4)

    def test_catalogo_cerrado_11_tipos(self):
        """Verifica que exactamente se emitan los 11 tipos permitidos y ningún tipo retirado."""
        tipos_emitidos = set()
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                t = paso.get("tipo")
                tipos_emitidos.add(t)

        self.assertTrue(tipos_emitidos.issubset(CATALOGO_11),
                        f"Tipos no permitidos emitidos: {tipos_emitidos - CATALOGO_11}")
        self.assertEqual(len(tipos_emitidos), 11,
                         f"Se esperaban exactamente 11 tipos generados, se obtuvieron {len(tipos_emitidos)}: {tipos_emitidos}")

        # Comprobar que ningún tipo retirado esté presente
        interseccion_retirados = tipos_emitidos & TIPOS_RETIRADOS
        self.assertEqual(len(interseccion_retirados), 0,
                         f"Se detectaron tipos retirados en el compilado: {interseccion_retirados}")

    def test_total_pasos_inferior_a_referencia_804(self):
        """Verifica que el total de pasos no exceda los 804 de la referencia v4 (reducción de redundancia)."""
        total_pasos = sum(len(l.get("pasos", [])) for l in self.lecciones)
        self.assertLessEqual(total_pasos, 804, f"Total de pasos {total_pasos} excede el límite de 804")
        self.assertGreaterEqual(total_pasos, 500, f"Total de pasos {total_pasos} es anormalmente bajo")

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

        # O_011 en L04 tiene 1 solo token ('Chhuñiqasichay'), excluida justificadamente de ordenar_oracion
        esperadas_oraciones = {f"O_{i:03d}" for i in range(1, 121)} - {"O_011"}
        self.assertTrue(esperadas_oraciones.issubset(oraciones_evaluadas),
                        f"Faltan oraciones curriculares por evaluar: {esperadas_oraciones - oraciones_evaluadas}")

    def test_presentacion_y_microactividad_inmediata(self):
        """Verifica que tras cada presentacion_familia haya inmediatamente una microactividad válida."""
        total_presentaciones = 0
        for lec in self.lecciones:
            pasos = lec.get("pasos", [])
            for idx, paso in enumerate(pasos):
                if paso["tipo"] == "presentacion_familia":
                    total_presentaciones += 1
                    fid = paso["objetivo_id"]
                    self.assertLess(idx + 1, len(pasos), f"En {lec['id']}, presentacion final sin microactividad")
                    siguiente = pasos[idx + 1]
                    self.assertNotEqual(siguiente["tipo"], "presentacion_familia",
                                        f"En {lec['id']}, dos presentaciones consecutivas")
                    # Verificar que la microactividad use la familia recién presentada o su forma
                    siguiente_obj = siguiente.get("objetivo_id") or siguiente.get("raiz_id")
                    self.assertEqual(siguiente_obj, fid,
                                     f"En {lec['id']}, microactividad inmediata no evalúa {fid}")

        self.assertEqual(total_presentaciones, 210, f"Se esperaban 210 presentaciones, se obtuvieron {total_presentaciones}")

    def test_proporcion_y_rango_escritura_libre(self):
        """Verifica que cada lección tenga entre 4 y 6 actividades de escritura libre."""
        for lec in self.lecciones:
            escrituras = [p for p in lec.get("pasos", []) if p["tipo"] in {"escribir_palabra", "escribir_forma", "escribir_oracion"}]
            total_esc = len(escrituras)
            self.assertTrue(4 <= total_esc <= 6,
                            f"En {lec['id']}: se esperaban 4-6 escrituras libres, se obtuvieron {total_esc}")

    def test_no_duplicacion_de_objetivos_escritos(self):
        """Verifica que ningún ID ni respuesta superficial normalizada se repita en escritura libre en la misma lección."""
        for lec in self.lecciones:
            escrituras = [p for p in lec.get("pasos", []) if p["tipo"] in {"escribir_palabra", "escribir_forma", "escribir_oracion"}]
            ids_vistos = set()
            respuestas_vistas = set()

            for paso in escrituras:
                obj_id = paso.get("objetivo_id") or paso.get("forma_id") or paso.get("oracion_id")
                resp_uch = normalizar_texto(paso.get("respuesta_esperada_uch", ""))

                self.assertNotIn(obj_id, ids_vistos,
                                 f"En {lec['id']}: ID '{obj_id}' duplicado en escritura libre")
                self.assertNotIn(resp_uch, respuestas_vistas,
                                 f"En {lec['id']}: Respuesta '{resp_uch}' duplicada en escritura libre")

                ids_vistos.add(obj_id)
                respuestas_vistas.add(resp_uch)

    def test_dictado_y_traduccion_distintos_oracion(self):
        """Verifica que en una misma lección el dictado y la traducción escrita no compartan oracion_id."""
        for lec in self.lecciones:
            pasos_oracion = [p for p in lec.get("pasos", []) if p["tipo"] == "escribir_oracion"]
            dictados = [p["oracion_id"] for p in pasos_oracion if p.get("fuente_estimulo") == "audio"]
            traducciones = [p["oracion_id"] for p in pasos_oracion if p.get("fuente_estimulo") == "texto_es"]

            interseccion = set(dictados) & set(traducciones)
            self.assertEqual(len(interseccion), 0,
                             f"En {lec['id']}: oración {interseccion} compartida entre dictado y traducción")

    def test_contrato_dictado_escrito(self):
        """Verifica que el dictado escrito tenga tipo escribir_oracion, fuente_estimulo audio y sin fichas."""
        dictados_totales = 0
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                if paso["tipo"] == "escribir_oracion" and paso.get("fuente_estimulo") == "audio":
                    dictados_totales += 1
                    self.assertIn("Escucha", paso["consigna"])
                    self.assertIn("respuesta_esperada_uch", paso)
                    self.assertNotIn("opciones_ids", paso)
                    self.assertNotIn("banco_palabras", paso)
                    self.assertNotIn("palabra_oculta_id", paso)

        self.assertEqual(dictados_totales, 27, f"Se esperaban 27 dictados escritos, se obtuvieron {dictados_totales}")

    def test_refuerzos_al_fallar_validos(self):
        """Verifica que ningún refuerzo_al_fallar apunte a un tipo retirado."""
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                ref = paso.get("refuerzo_al_fallar")
                if ref:
                    r_tipo = ref.get("tipo")
                    self.assertIn(r_tipo, CATALOGO_11,
                                  f"En {lec['id']}: refuerzo_al_fallar con tipo no permitido: {r_tipo}")
                    self.assertNotIn(r_tipo, TIPOS_RETIRADOS,
                                     f"En {lec['id']}: refuerzo_al_fallar con tipo retirado: {r_tipo}")

    def test_refuerzos_generacion_opciones_validas(self):
        """Verifica que todos los refuerzos tengan referencias válidas en el corpus y objetivos resolubles sin ambigüedad."""
        palabras_map = {p["id"]: p for p in self.data_palabras.get("palabras", [])}
        oraciones_map = {o["id"]: o for o in self.data_oraciones.get("oraciones", [])}

        total_refuerzos = 0
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                ref = paso.get("refuerzo_al_fallar")
                if not ref:
                    continue
                total_refuerzos += 1
                r_tipo = ref.get("tipo")
                if r_tipo in {"audio_a_uch", "uch_a_es"}:
                    obj = ref.get("objetivo_id")
                    self.assertIn(obj, palabras_map, f"En {lec['id']}: refuerzo {r_tipo} con objetivo {obj} no existe en palabras.json")
                elif r_tipo == "audio_a_forma":
                    frm = ref.get("forma_id")
                    raiz = ref.get("raiz_id")
                    self.assertIn(raiz, palabras_map, f"En {lec['id']}: raiz {raiz} no existe en palabras.json")
                    formas_raiz = [f["id"] for f in palabras_map[raiz].get("formas", [])]
                    self.assertIn(frm, formas_raiz, f"En {lec['id']}: forma {frm} no pertenece a raiz {raiz}")
                elif r_tipo == "ordenar_oracion":
                    oid = ref.get("oracion_id")
                    self.assertIn(oid, oraciones_map, f"En {lec['id']}: oracion {oid} no existe en oraciones.json")
                    self.assertGreaterEqual(len(oraciones_map[oid]["uch"].split()), 2,
                                            f"En {lec['id']}: refuerzo ordenar_oracion {oid} tiene < 2 tokens")

        self.assertGreater(total_refuerzos, 80, f"Se esperaban más de 80 refuerzos, se encontraron {total_refuerzos}")

    def test_asr_opcional_no_bloqueante(self):
        """Verifica que cada paso ASR de palabra y oración tenga opcional: True."""
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                if paso["tipo"] in {"escucha_y_repite_asr", "escucha_y_repite_oracion_asr"}:
                    self.assertTrue(paso.get("opcional", False),
                                    f"En {lec['id']}: paso ASR sin opcional=True")

    def test_dos_emparejamientos_por_leccion(self):
        """Verifica que cada una de las 27 lecciones tenga exactamente 2 emparejamientos (54 en total), entre 2 y 5 parejas."""
        total_emparejamientos = 0
        for lec in self.lecciones:
            pasos = lec.get("pasos", [])
            emps = [p for p in pasos if p.get("tipo") == "emparejar_uch_es"]
            self.assertEqual(len(emps), 2, f"En {lec['id']}: se esperaban 2 emparejamientos, se obtuvieron {len(emps)}")
            total_emparejamientos += len(emps)

            for i, emp in enumerate(emps):
                items = emp.get("items_ids", [])
                self.assertTrue(2 <= len(items) <= 5,
                                f"En {lec['id']}, emparejamiento {i+1}: items {len(items)} fuera de rango [2, 5]")
                self.assertEqual(len(set(items)), len(items),
                                 f"En {lec['id']}, emparejamiento {i+1}: IDs duplicados en {items}")

            # Posición de emparejamiento 1: después de floor(N/2) presentaciones
            n_nuevas = len(lec.get("familias_nuevas", []))
            mitad = n_nuevas // 2
            emp1_idx = pasos.index(emps[0])
            pres_antes_emp1 = sum(1 for p in pasos[:emp1_idx] if p.get("tipo") == "presentacion_familia")
            self.assertGreaterEqual(pres_antes_emp1, mitad,
                                    f"En {lec['id']}: emparejamiento 1 apareció antes de presentar {mitad} familias nuevas")

            # Posición de emparejamiento 2: después de todas las presentaciones
            emp2_idx = pasos.index(emps[1])
            pres_antes_emp2 = sum(1 for p in pasos[:emp2_idx] if p.get("tipo") == "presentacion_familia")
            self.assertEqual(pres_antes_emp2, n_nuevas,
                             f"En {lec['id']}: emparejamiento 2 apareció antes de completar todas las presentaciones")

        self.assertEqual(total_emparejamientos, 54,
                         f"Se esperaban exactamente 54 emparejamientos, se obtuvieron {total_emparejamientos}")

    def test_prioridad_escritura_l06(self):
        """Verifica que en L06 los objetivos escritos sean de vocabulario nuevo y no repitan ana o chhuni_pichuchay."""
        l06 = next(l for l in self.lecciones if l["id"] == "L06")
        escrituras_palabra = [p["objetivo_id"] for p in l06.get("pasos", []) if p.get("tipo") == "escribir_palabra"]
        self.assertNotIn("ana", escrituras_palabra, "L06 no debe escribir 'ana' (repaso)")
        self.assertNotIn("chhuni_pichuchay", escrituras_palabra, "L06 no debe escribir 'chhuni_pichuchay' (repaso)")
        for obj in escrituras_palabra:
            self.assertIn(obj, l06["familias_nuevas"], f"L06 escribió {obj} que no es familia nueva")

    def test_nombres_propios_excluidos_de_objetivos(self):
        """Verifica que ningún nombre propio contextual aparezca como objetivo_id, forma_id o en items_ids."""
        nombres_prohibidos = {normalizar_texto(np) for np in NOMBRES_PROPIOS_CONTEXTUALES}
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                obj = paso.get("objetivo_id")
                if obj:
                    self.assertNotIn(obj.lower(), nombres_prohibidos,
                                     f"En {lec['id']}: nombre propio '{obj}' como objetivo_id")
                frm = paso.get("forma_id")
                if frm:
                    self.assertNotIn(frm.lower(), nombres_prohibidos,
                                     f"En {lec['id']}: nombre propio '{frm}' como forma_id")
                for itm in paso.get("items_ids", []):
                    self.assertNotIn(itm.lower(), nombres_prohibidos,
                                     f"En {lec['id']}: nombre propio '{itm}' en items_ids")


    def test_consignas_sin_barras_ambiguas(self):
        """Verifica que ninguna consigna en las 27 lecciones contenga barras '/' de ambigüedad."""
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                consigna = paso.get("consigna", "")
                self.assertNotIn("/", consigna,
                                 f"En {lec['id']}, paso {paso.get('tipo')}: consigna con barra: '{consigna}'")

    def test_ningun_ordenar_oracion_con_un_solo_token(self):
        """Verifica que ninguna actividad ordenar_oracion tenga menos de dos tokens (e.g. O_011 excluida)."""
        oraciones_map = {o["id"]: o for o in self.data_oraciones.get("oraciones", [])}
        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                if paso.get("tipo") == "ordenar_oracion":
                    oid = paso["oracion_id"]
                    self.assertNotEqual(oid, "O_011", f"En {lec['id']}: O_011 (1 token) no debe estar en ordenar_oracion")
                    uch = oraciones_map[oid]["uch"]
                    tokens = uch.split()
                    self.assertGreaterEqual(len(tokens), 2,
                                            f"En {lec['id']}: {oid} tiene {len(tokens)} tokens, se requieren >= 2")

    def test_ausencia_repeticiones_entre_emparejamientos(self):
        """Verifica que no existan palabras repetidas entre los dos emparejamientos de una misma lección."""
        for lec in self.lecciones:
            emps = [p for p in lec.get("pasos", []) if p.get("tipo") == "emparejar_uch_es"]
            if len(emps) == 2:
                s1 = set(emps[0].get("items_ids", []))
                s2 = set(emps[1].get("items_ids", []))
                inter = s1 & s2
                self.assertEqual(len(inter), 0,
                                 f"En {lec['id']}: palabras repetidas entre Emp 1 y Emp 2: {inter}")


if __name__ == "__main__":
    unittest.main()
