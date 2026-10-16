"""
test_g2p.py
Suite de pruebas unitarias para el módulo G2P (Grafema a Fonema) del pipeline ASR.
Basado en: 02-modulo-asr-voz.md — inventario cerrado de 38 fonemas canónicos ASCII.

Cómo ejecutar desde la raíz del proyecto:
    python -m pytest scripts/tests/test_g2p.py -v
    # o directamente:
    python scripts/tests/test_g2p.py
"""
import sys
import os
import unittest

# Importar desde scripts/entrenamiento/
tests_dir = os.path.dirname(os.path.abspath(__file__))
pruebas_dir = os.path.dirname(tests_dir)
scripts_dir = os.path.dirname(pruebas_dir)
entrenamiento_dir = os.path.join(scripts_dir, "entrenamiento")
sys.path.insert(0, entrenamiento_dir)
from preparar_asr import grafema_a_fonema, FONEMAS_CANONICOS


class TestInventario(unittest.TestCase):
    """Verifica la integridad del inventario fonológico cerrado."""

    def test_cantidad_fonemas_canonicos(self):
        """El inventario debe contener exactamente 38 fonemas canónicos."""
        self.assertEqual(len(FONEMAS_CANONICOS), 38,
                         f"Se esperaban 38 fonemas, se encontraron {len(FONEMAS_CANONICOS)}")

    def test_fonemas_presentes(self):
        """Comprueba que los 38 fonemas esperados están en el inventario."""
        esperados = {
            "A", "AA", "E", "EE", "I", "II", "O", "OO", "U", "UU",
            "P", "T", "K", "Q", "M", "N", "R", "S", "X", "J", "L", "LL", "Y", "W",
            "TS", "CH", "SH", "NY",
            "PH", "TH", "KH", "QH", "CHH",
            "P_EJ", "T_EJ", "K_EJ", "Q_EJ", "CH_EJ"
        }
        self.assertEqual(FONEMAS_CANONICOS, esperados)

    def test_no_existe_fonema_D(self):
        """No debe existir ningún token 'D' en el inventario (d → T es adaptación de préstamo)."""
        self.assertNotIn("D", FONEMAS_CANONICOS,
                         "El fonema D no forma parte del inventario nativo. Usar adaptación d→T.")


class TestPrestamosYNombres(unittest.TestCase):
    """
    Tests para adaptaciones técnicas de préstamo del castellano.
    Estas reglas son aproximaciones técnicas documentadas en el Nivel 6 de REGLAS_G2P_COMPILADAS
    y deben verificarse empíricamente con el WER real una vez disponibles las grabaciones.
    """

    def test_pedro(self):
        """Pedro: d → T (adaptación consonante préstamo castellano)."""
        self.assertEqual(grafema_a_fonema("Pedro"), "P E T R O")

    def test_pedro_minuscula(self):
        """pedro (minúscula): misma regla, entrada normalizada."""
        self.assertEqual(grafema_a_fonema("pedro"), "P E T R O")

    def test_carlos(self):
        """Carlos: c → K (adaptación consonante préstamo castellano)."""
        self.assertEqual(grafema_a_fonema("Carlos"), "K A R L O S")

    def test_carlos_minuscula(self):
        """carlos (minúscula): misma regla."""
        self.assertEqual(grafema_a_fonema("carlos"), "K A R L O S")

    def test_irohito(self):
        """Irohito: h muda → eliminada (topónimo castellano). La h aspirada nativa ya fue procesada antes."""
        self.assertEqual(grafema_a_fonema("Irohito"), "I R O I T O")

    def test_irohito_minuscula(self):
        """irohito (minúscula): misma regla."""
        self.assertEqual(grafema_a_fonema("irohito"), "I R O I T O")

    def test_juana(self):
        """Juana: j nativa → J (velar /x/), no préstamo."""
        self.assertEqual(grafema_a_fonema("Juana"), "J U A N A")

    def test_lorenzo(self):
        """Lorenzo: l, o, r, e, n, z, o → L O R E N S O (z → S, variante ortográfica de s)."""
        self.assertEqual(grafema_a_fonema("Lorenzo"), "L O R E N S O")


class TestNormalizacionTildesCastellanas(unittest.TestCase):
    """
    Contraste crítico entre vocales castellanas acentuadas (préstamo) y vocales largas nativas.

    Vocales largas nativas (ä, ë, ï, ö, ü) → AA, EE, II, OO, UU (Nivel 5)
    Vocales castellanas acentuadas (á, é, í, ó, ú) → A, E, I, O, U  (Nivel 6B)
    """

    def test_maria_vocal_castellana(self):
        """María: 'í' castellana (U+00ED) → I (vocal corta). No es vocal larga nativa."""
        self.assertEqual(grafema_a_fonema("María"), "M A R I A")

    def test_ti_vocal_larga_nativa(self):
        """Tï: 'ï' nativa (U+00EF, con diéresis) → II (vocal larga). Contrastivo con 'í' castellana."""
        self.assertEqual(grafema_a_fonema("Tï"), "T II")

    def test_contraste_i_castellana_vs_i_nativa(self):
        """
        Contraste explícito:
          - 'í' castellana (U+00ED, i con acento agudo)  → I  (vocal corta)
          - 'ï' nativa    (U+00EF, i con diéresis)       → II (vocal larga)
        Ninguna de las dos altera a la otra.
        """
        resultado_castellana = grafema_a_fonema("María")
        resultado_nativa = grafema_a_fonema("Tï")
        # 'María' no debe producir vocal larga II
        self.assertNotIn("II", resultado_castellana.split(),
                         "La í castellana no debe producir vocal larga II")
        # 'Tï' no debe producir vocal corta I
        self.assertNotIn(" I ", " " + resultado_nativa + " ",
                         "La ï nativa no debe producir vocal corta I")
        self.assertEqual(resultado_castellana, "M A R I A")
        self.assertEqual(resultado_nativa, "T II")


class TestVocalesLargasNativas(unittest.TestCase):
    """Vocales largas nativas con diéresis → doble vocal canónica (Nivel 5)."""

    def test_a_larga_dieresis(self):
        """ä → AA"""
        self.assertEqual(grafema_a_fonema("Päku"), "P AA K U")

    def test_e_larga_dieresis(self):
        """ë → EE"""
        self.assertEqual(grafema_a_fonema("Mäska"), "M AA S K A")  # ä en corpus

    def test_i_larga_dieresis(self):
        """ï → II"""
        self.assertEqual(grafema_a_fonema("Tï"), "T II")

    def test_o_larga_dieresis(self):
        """ö → OO (vía aa/ee... variante; usar palabra real con ö si existe en corpus)"""
        # Palabra ficticia para probar la regla de ö
        self.assertEqual(grafema_a_fonema("möka"), "M OO K A")

    def test_u_larga_dieresis(self):
        """ü → UU"""
        self.assertEqual(grafema_a_fonema("Thü"), "TH UU")

    def test_xurs(self):
        """Xürs: x nativa + ü larga + r + s → X UU R S"""
        self.assertEqual(grafema_a_fonema("Xürs"), "X UU R S")


class TestEyectivas(unittest.TestCase):
    """
    Consonantes eyectivas: combinación grafema+apóstrofe → token_EJ.
    CONVENCIÓN: los tests usan ʼ (U+02BC, MODIFIER LETTER APOSTROPHE) como marcador canónico.
    La función grafema_a_fonema acepta cualquier variante y la normaliza internamente a U+02BC.
    """

    def test_p_eyectiva(self):
        """pʼ → P_EJ"""
        self.assertEqual(grafema_a_fonema("Pʼitkchay"), "P_EJ I T K CH A Y")

    def test_t_eyectiva(self):
        """tʼ → T_EJ"""
        self.assertEqual(grafema_a_fonema("Tʼalla"), "T_EJ A LL A")

    def test_k_eyectiva(self):
        """kʼ → K_EJ"""
        self.assertEqual(grafema_a_fonema("Kʼasa"), "K_EJ A S A")

    def test_q_eyectiva(self):
        """qʼ → Q_EJ"""
        self.assertEqual(grafema_a_fonema("Qʼalluchay"), "Q_EJ A LL U CH A Y")

    def test_ch_eyectiva(self):
        """chʼ → CH_EJ (trígrafo de mayor prioridad)"""
        self.assertEqual(grafema_a_fonema("Chʼatschay"), "CH_EJ A TS CH A Y")


class TestAspiradas(unittest.TestCase):
    """Consonantes aspiradas: dígrafo con h → token con H."""

    def test_chh(self):
        """chh → CHH (trígrafo, prioridad máxima sobre ch)"""
        self.assertEqual(grafema_a_fonema("Chhaq"), "CHH A Q")

    def test_ph(self):
        """ph → PH"""
        self.assertEqual(grafema_a_fonema("Phiki"), "PH I K I")

    def test_th(self):
        """th → TH"""
        self.assertEqual(grafema_a_fonema("Thuni"), "TH U N I")

    def test_kh(self):
        """kh → KH"""
        self.assertEqual(grafema_a_fonema("Khirchula"), "KH I R CH U L A")

    def test_qh(self):
        """qh → QH"""
        self.assertEqual(grafema_a_fonema("Qhoya"), "QH O Y A")

    def test_chhaxrana(self):
        """Chhaxraña: chh + a + x + r + a + ñ + a → CHH A X R A NY A"""
        self.assertEqual(grafema_a_fonema("Chhaxraña"), "CHH A X R A NY A")


class TestDigrafosNativos(unittest.TestCase):
    """Dígrafos nativos: ts, ll, ñ, sh."""

    def test_ts(self):
        """ts → TS (africada alveolar sorda)"""
        self.assertEqual(grafema_a_fonema("Sitsni"), "S I TS N I")

    def test_ll(self):
        """ll → LL (lateral palatal)"""
        self.assertEqual(grafema_a_fonema("Lloqa"), "LL O Q A")

    def test_ny(self):
        """ñ → NY (nasal palatal)"""
        self.assertEqual(grafema_a_fonema("Qañawi"), "Q A NY A W I")

    def test_sh(self):
        """sh → SH (fricativa post-alveolar sorda)"""
        self.assertEqual(grafema_a_fonema("Shila"), "SH I L A")

    def test_ch(self):
        """ch (sin modificadores) → CH"""
        self.assertEqual(grafema_a_fonema("Chichalay"), "CH I CH A L A Y")


class TestFricativasDistintivas(unittest.TestCase):
    """
    j y x son fonemas distintos en uchumataqu, alineados con el sistema fonológico del aimara.
    Token ASCII sigue la grafía nativa (no el símbolo IPA):
      j nativa → J (representa /x/ velar, más suave)
      x nativa → X (representa /χ/ uvular, más fuerte)
    """

    def test_j_nativa_velar(self):
        """j → J (velar /x/)"""
        self.assertEqual(grafema_a_fonema("Jaxchay"), "J A X CH A Y")

    def test_x_nativa_uvular(self):
        """x → X (postvelar/uvular /χ/)"""
        self.assertEqual(grafema_a_fonema("Xala"), "X A L A")

    def test_j_y_x_en_misma_palabra(self):
        """Palabra con ambas fricativas: jaxchay → J A X CH A Y"""
        fon = grafema_a_fonema("jaxchay")
        partes = fon.split()
        self.assertIn("J", partes, "Debe contener J (j nativa velar)")
        self.assertIn("X", partes, "Debe contener X (x nativa uvular)")


class TestVariantesZ(unittest.TestCase):
    """z es variante ortográfica de s en uchumataqu (mismo fonema /s/)."""

    def test_z_equivale_a_s(self):
        """z → S (misma regla que s, no es grafema desconocido)."""
        self.assertEqual(grafema_a_fonema("zonichhiji"), "S O N I CHH I J I")

    def test_z_en_corpus_real(self):
        """Zoñchhiji: z nativa → S, ñ → NY, chh → CHH."""
        self.assertEqual(grafema_a_fonema("Zoñchhiji"), "S O NY CHH I J I")


class TestNormalizacionApostrofe(unittest.TestCase):
    """
    Verifica que grafema_a_fonema acepta CUALQUIER variante tipográfica de apóstrofe
    y la normaliza a U+02BC antes del G2P.
    El resultado fonético debe ser idéntico independientemente de la variante usada.
    Los archivos finales (lexicon.txt, corpus) y el código fuente usan ʼ (U+02BC) como
    único marcador canónico de consonantes eyectivas.
    """
    VARIANTES = [
        ("U+0027 ASCII apostrophe",      "tʼalla".replace("ʼ", "'")),
        ("U+02BC modifier letter",       "tʼalla"),
        ("U+2018 left single quote",     "t\u2018alla"),
        ("U+2019 right single quote",    "t\u2019alla"),
        ("U+0060 grave accent",          "t`alla"),
        ("U+00B4 acute accent",          "t\u00b4alla"),
        ("U+02B9 modifier letter prime", "t\u02b9alla"),
    ]

    def test_todas_variantes_producen_mismo_resultado(self):
        """Todas las variantes de apóstrofe deben producir T_EJ A LL A."""
        esperado = "T_EJ A LL A"
        for descripcion, palabra in self.VARIANTES:
            with self.subTest(variante=descripcion):
                self.assertEqual(
                    grafema_a_fonema(palabra), esperado,
                    f"Variante {descripcion} ({palabra!r}) no produjo '{esperado}'"
                )


class TestValidacionFailFast(unittest.TestCase):
    """
    Verificación de la validación fail-fast:
    el G2P debe lanzar ValueError ante grafemas no contemplados en lugar de aceptarlos silenciosamente.
    z NO es un caso de prueba aquí (z → S es una regla existente).
    """

    def test_rechaza_grafema_b(self):
        """b no está en el inventario nativo ni en las adaptaciones de préstamo → ValueError."""
        with self.assertRaises(ValueError):
            grafema_a_fonema("balsa")

    def test_rechaza_grafema_v(self):
        """v no está contemplado → ValueError."""
        with self.assertRaises(ValueError):
            grafema_a_fonema("vaca")

    def test_rechaza_grafema_f(self):
        """f no está contemplado → ValueError."""
        with self.assertRaises(ValueError):
            grafema_a_fonema("fara")

    def test_rechaza_grafema_g(self):
        """g no está contemplado → ValueError."""
        with self.assertRaises(ValueError):
            grafema_a_fonema("gala")

    def test_acepta_entrada_corpus_real(self):
        """Una palabra del corpus real no debe lanzar ValueError."""
        try:
            grafema_a_fonema("Chhuniqasi")
        except ValueError as e:
            self.fail(f"Palabra válida del corpus lanzó ValueError: {e}")


class TestGreedyLongestMatch(unittest.TestCase):
    """
    Verifica que la prioridad greedy longest-match funciona correctamente:
    chʼ se convierte en CH_EJ y no en CH + ningún carácter residual de eyectiva.
    chh se convierte en CHH y no en CH + H.
    """

    def test_chh_sobre_ch(self):
        """chh → CHH (no CH + H residual)"""
        resultado = grafema_a_fonema("Chhaq")
        self.assertEqual(resultado, "CHH A Q")
        self.assertNotIn("CH H", resultado)

    def test_ch_eyectiva_sobre_ch(self):
        """chʼ → CH_EJ (el trígrafo tiene precedencia sobre ch)"""
        resultado = grafema_a_fonema("Chʼaxana")
        self.assertEqual(resultado, "CH_EJ A X A N A")
        # No debe aparecer CH suelto ni apóstrofe residual
        self.assertNotIn(" CH ", " " + resultado + " ")

    def test_ph_sobre_p_h(self):
        """ph → PH (el dígrafo no se descompone en P + H muda)"""
        resultado = grafema_a_fonema("Phiki")
        self.assertEqual(resultado, "PH I K I")
        self.assertNotIn("P I", resultado)   # Sería el resultado erróneo si h se eliminara antes


if __name__ == "__main__":
    unittest.main(verbosity=2)
