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

    def test_total_pasos_con_cobertura_refuerzo(self):
        """Verifica que el total de pasos refleje la cobertura de refuerzo para todas las familias nuevas (879 pasos)."""
        total_pasos = sum(len(l.get("pasos", [])) for l in self.lecciones)
        self.assertLessEqual(total_pasos, 900, f"Total de pasos {total_pasos} excede el límite de 900")
        self.assertGreaterEqual(total_pasos, 800, f"Total de pasos {total_pasos} es menor a los 800 esperados con cobertura completa")

    def test_cobertura_26_lecciones_y_120_oraciones(self):
        """Verifica que las 26 lecciones existan y que las 120 oraciones curriculares estén cubiertas."""
        self.assertEqual(len(self.lecciones), 26)
        lids = [l["id"] for l in self.lecciones]
        esperados_lids = [f"L{i:02d}" for i in range(1, 27)]
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
        """Verifica que cada lección tenga una cantidad equilibrada de escritura libre acorde a sus familias nuevas (4 a 8 escrituras)."""
        for lec in self.lecciones:
            escrituras = [p for p in lec.get("pasos", []) if p["tipo"] in {"escribir_palabra", "escribir_forma", "escribir_oracion"}]
            total_esc = len(escrituras)
            self.assertTrue(4 <= total_esc <= 8,
                            f"En {lec['id']}: se esperaban 4-8 escrituras libres, se obtuvieron {total_esc}")

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

        self.assertEqual(dictados_totales, 26, f"Se esperaban 26 dictados escritos, se obtuvieron {dictados_totales}")

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
        """Verifica que cada una de las 26 lecciones tenga exactamente 2 emparejamientos (52 en total), entre 2 y 5 parejas."""
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

        self.assertEqual(total_emparejamientos, 52,
                         f"Se esperaban exactamente 52 emparejamientos, se obtuvieron {total_emparejamientos}")

    def test_prioridad_escritura_pronombres(self):
        """Verifica que en L05 (pronombres) los objetivos escritos sean de vocabulario nuevo y no repitan ana o chhuni_pichuchay."""
        l05 = next(l for l in self.lecciones if l["id"] == "L05")
        escrituras_palabra = [p["objetivo_id"] for p in l05.get("pasos", []) if p.get("tipo") == "escribir_palabra"]
        self.assertNotIn("ana", escrituras_palabra, "L05 no debe escribir 'ana' (repaso)")
        self.assertNotIn("chhuni_pichuchay", escrituras_palabra, "L05 no debe escribir 'chhuni_pichuchay' (repaso)")
        for obj in escrituras_palabra:
            self.assertIn(obj, l05["familias_nuevas"], f"L05 escribió {obj} que no es familia nueva")

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
        """Verifica que ninguna consigna en las 26 lecciones contenga barras '/' de ambigüedad."""
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

    def test_organizacion_dos_bloques_vocabulario_y_oraciones_finales(self):
        """
        Verifica automáticamente las 26 lecciones según los 6 criterios del nuevo contrato:
        1. Cada familia nueva tenga 1 presentación, 1 microactividad inicial y 1 actividad adicional (escritura o ASR).
        2. Cada bloque (A y B) tenga su actividad emparejar_uch_es.
        3. Las actividades de refuerzo aparezcan después del emparejamiento correspondiente.
        4. Todas las actividades de oraciones estén al final de la lección.
        5. No existan referencias a audios, palabras, formas u oraciones inexistentes.
        6. Los ejercicios ASR sean compatibles con los recursos reales del modelo.
        Y verifica que NUNCA existan dos actividades de escritura consecutivas.
        """
        import os
        dir_audio = os.path.join(os.path.dirname(__file__), "..", "..", "audios_palabras")
        audios_reales = {os.path.splitext(f)[0] for f in os.listdir(dir_audio)} if os.path.exists(dir_audio) else set()
        ruta_lex = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ASR", "datos_asr", "lexicon.txt")
        lexicon_reales = set()
        if os.path.exists(ruta_lex):
            with open(ruta_lex, "r", encoding="utf-8") as f:
                lexicon_reales = {line.split("\t")[0].strip() for line in f if "\t" in line}

        TIPOS_ORACIONES = {"ordenar_oracion", "escribir_oracion", "escucha_y_repite_oracion_asr"}
        TIPOS_ESCRITURA = {"escribir_palabra", "escribir_forma", "escribir_oracion"}
        palabras_map = {p["id"]: p for p in self.data_palabras.get("palabras", [])}

        for lec in self.lecciones:
            pasos = lec.get("pasos", [])
            fams = lec.get("familias_nuevas", [])
            n_nuevas = len(fams)
            mitad = (n_nuevas + 1) // 2
            fams_a = fams[:mitad]
            fams_b = fams[mitad:]

            # 1. Cada familia nueva tiene 1 presentación, 1 microactividad inicial y 1 refuerzo adicional
            for f in fams:
                pres = [p for p in pasos if p["tipo"] == "presentacion_familia" and p.get("objetivo_id") == f]
                self.assertEqual(len(pres), 1, f"En {lec['id']}: familia {f} tiene {len(pres)} presentaciones")

                ref = [
                    p for p in pasos
                    if (p.get("objetivo_id") == f or p.get("raiz_id") == f)
                    and p["tipo"] in {"escribir_palabra", "escribir_forma", "escucha_y_repite_asr"}
                ]
                self.assertEqual(len(ref), 1, f"En {lec['id']}: familia {f} tiene {len(ref)} refuerzos (esperado exactamente 1)")

            # 2. Emparejamientos de Bloque A y Bloque B
            emps = [p for p in pasos if p["tipo"] == "emparejar_uch_es"]
            self.assertEqual(len(emps), 2, f"En {lec['id']}: se esperaban 2 emparejamientos, hay {len(emps)}")
            idx_emp_a = pasos.index(emps[0])
            idx_emp_b = pasos.index(emps[1])

            # 3. Refuerzos de Bloque A aparecen después de Emparejamiento A, y los de B después de Emparejamiento B
            for f in fams_a:
                ref_p = next(
                    p for p in pasos
                    if (p.get("objetivo_id") == f or p.get("raiz_id") == f)
                    and p["tipo"] in {"escribir_palabra", "escribir_forma", "escucha_y_repite_asr"}
                )
                self.assertGreater(pasos.index(ref_p), idx_emp_a,
                                   f"En {lec['id']}: refuerzo de {f} (Bloque A) antes de emparejamiento 1")
                self.assertLess(pasos.index(ref_p), idx_emp_b,
                                f"En {lec['id']}: refuerzo de {f} (Bloque A) después de emparejamiento 2")

            for f in fams_b:
                ref_p = next(
                    p for p in pasos
                    if (p.get("objetivo_id") == f or p.get("raiz_id") == f)
                    and p["tipo"] in {"escribir_palabra", "escribir_forma", "escucha_y_repite_asr"}
                )
                self.assertGreater(pasos.index(ref_p), idx_emp_b,
                                   f"En {lec['id']}: refuerzo de {f} (Bloque B) antes de emparejamiento 2")

            # 4. Todas las actividades de oraciones al final
            idx_primer_oracion = min(i for i, p in enumerate(pasos) if p["tipo"] in TIPOS_ORACIONES)
            for p in pasos[idx_primer_oracion:]:
                self.assertIn(p["tipo"], TIPOS_ORACIONES,
                              f"En {lec['id']}: paso no-oracional después de oraciones: {p['tipo']}")

            # 5 & 6. Compatibilidad de audios y ASR con recursos reales del modelo
            for p in pasos:
                if p["tipo"] == "escucha_y_repite_asr":
                    obj = p["objetivo_id"]
                    self.assertIn(obj, audios_reales, f"En {lec['id']}: ASR de {obj} no tiene archivo de audio")
                    uch_p = palabras_map[obj]["uch"].lower().strip()
                    self.assertTrue(uch_p in lexicon_reales or obj in lexicon_reales,
                                    f"En {lec['id']}: palabra ASR '{uch_p}' ({obj}) no compatible con lexicon ASR")

            # 7. NUNCA dos actividades de escritura consecutivas
            for idx in range(len(pasos) - 1):
                t1 = pasos[idx]["tipo"]
                t2 = pasos[idx + 1]["tipo"]
                self.assertFalse(t1 in TIPOS_ESCRITURA and t2 in TIPOS_ESCRITURA,
                                 f"En {lec['id']}, pasos {idx} y {idx+1}: dos escrituras consecutivas ('{t1}' y '{t2}')")

    def test_capitalizacion_irohito_urus_en_l04(self):
        """Verifica que el nombre propio de la comunidad 'Irohito Urus' esté correctamente capitalizado en O_016 y O_018."""
        oraciones_map = {o["id"]: o for o in self.data_oraciones.get("oraciones", [])}
        self.assertIn("Irohito Urus", oraciones_map["O_016"]["uch"])
        self.assertNotIn("irohito urus", oraciones_map["O_016"]["uch"])
        self.assertIn("Irohito Urus", oraciones_map["O_018"]["uch"])
        self.assertNotIn("irohito urus", oraciones_map["O_018"]["uch"])

        # En lecciones_compiladas.json (L04)
        l04 = next(l for l in self.lecciones if l["id"] == "L04")
        for paso in l04.get("pasos", []):
            if paso.get("oracion_id") in ["O_016", "O_018"] and "respuesta_esperada_uch" in paso:
                self.assertIn("Irohito Urus", paso["respuesta_esperada_uch"],
                              f"L04: respuesta_esperada_uch sin capitalizar: {paso['respuesta_esperada_uch']}")
                self.assertNotIn("irohito urus", paso["respuesta_esperada_uch"])

    def test_intercalacion_actividades_oraciones(self):
        """Verifica que ordenar_oracion se intercale con escritura y ASR, eliminando ejercicios consecutivos innecesarios."""
        total_pares_consecutivos = 0
        for lec in self.lecciones:
            pasos = lec.get("pasos", [])
            consec = 0
            for i in range(len(pasos) - 1):
                if pasos[i]["tipo"] == "ordenar_oracion" and pasos[i + 1]["tipo"] == "ordenar_oracion":
                    consec += 1
            total_pares_consecutivos += consec

            # En lecciones con <= 4 oraciones reconstituibles, debe haber exactamente 0 pares consecutivos
            n_oraciones = len(lec.get("oraciones_ids", []))
            if n_oraciones <= 4:
                self.assertEqual(consec, 0,
                                 f"En {lec['id']} ({n_oraciones} oraciones): se esperaban 0 pares consecutivos de ordenar_oracion, se obtuvieron {consec}")

        # Total en las 26 lecciones reducido a <= 16 (máximo teórico residual en lecciones con 5-7 oraciones)
        self.assertLessEqual(total_pares_consecutivos, 16,
                             f"Total de pares consecutivos de ordenar_oracion {total_pares_consecutivos} excede 16")

    def test_verificacion_estricta_asr_audio_y_lexicon(self):
        """Verifica que cada palabra y oración seleccionada para ASR tenga audio existente y compatibilidad estricta con lexicon."""
        ruta_lex = os.path.join(PROJECT_ROOT, "ASR", "datos_asr", "lexicon.txt")
        self.assertTrue(os.path.exists(ruta_lex), "lexicon.txt debe existir para validar ASR")
        with open(ruta_lex, "r", encoding="utf-8") as f:
            lexicon_set = {line.split("\t")[0].strip() for line in f if "\t" in line}

        palabras_map = {p["id"]: p for p in self.data_palabras.get("palabras", [])}
        total_asr_lexico = 0
        total_asr_oracion = 0

        for lec in self.lecciones:
            for paso in lec.get("pasos", []):
                t = paso["tipo"]
                if t == "escucha_y_repite_asr":
                    total_asr_lexico += 1
                    fid = paso["objetivo_id"]
                    self.assertIn(fid, self.audios_palabras,
                                  f"En {lec['id']}: audio no encontrado para ASR léxico {fid}")
                    p_uch = palabras_map[fid]["uch"].lower().strip()
                    self.assertTrue(p_uch in lexicon_set or fid in lexicon_set,
                                    f"En {lec['id']}: ASR léxico '{p_uch}' no está en lexicon ASR")
                elif t == "escucha_y_repite_oracion_asr":
                    total_asr_oracion += 1
                    oid = paso["oracion_id"]
                    self.assertIn(oid, self.audios_oraciones,
                                  f"En {lec['id']}: audio no encontrado para ASR oración {oid}")

        self.assertEqual(total_asr_lexico, 118)
        self.assertEqual(total_asr_oracion, 26)


if __name__ == "__main__":
    unittest.main()

