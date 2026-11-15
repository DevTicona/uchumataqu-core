# 🧪 Scripts de Pruebas e Inferencia ASR

Contiene las utilidades para pruebas unitarias fonológicas (G2P) e inferencia individual
offline sobre modelos exportados a ONNX (Sherpa-onnx / OnnxRuntime).

> 💡 **Nota sobre evaluación completa:**  
> En este proyecto, la evaluación exhaustiva del modelo (PER/WER sobre el conjunto de test con beam-search, greedy o modified beam-search) se ejecuta directamente mediante la **receta oficial de Icefall**:
> ```bash
> bash ASR/pipeline_icefall/run_decode.sh
> ```

---

## 📋 Scripts en esta carpeta

### `probar_inferencia.py`

**Propósito:** Inferencia rápida individual sobre un archivo WAV y evaluación fonética con semáforo de pronunciación.

**Qué hace:**
- Carga el modelo exportado a ONNX (o realiza análisis fonético comparativo si aún no hay modelo exportado).
- Decodifica la secuencia fonética del audio.
- Si se proporciona `--esperado`, calcula el porcentaje de **similitud fonética** mediante distancia Levenshtein normalizada.
- Emite la calificación visual según el sistema de semáforo del proyecto:
  - 🟢 **VERDE** (≥ 85%) — Excelente pronunciación.
  - 🟡 **AMARILLO** (60–84%) — Pronunciación aceptable / Aprobado.
  - 🔴 **ROJO** (< 60%) — Requiere práctica.

**Uso:**
```bash
python3 ASR/scripts/pruebas/probar_inferencia.py \
    --audio ASR/audios_palabras/pedro/chisi_01.wav \
    --esperado "ch'isi" \
    --model ASR/models/exported_onnx/model.onnx
```

| Argumento | Descripción | Default |
|---|---|---|
| `--audio` | Ruta al archivo de audio WAV | *(Requerido)* |
| `--esperado` | Texto esperado en Uchumataqu | `None` (solo transcribe) |
| `--model` | Ruta al modelo `.onnx` exportado | `models/exported_onnx/model.onnx` |

---

### `tests/test_g2p.py`

**Propósito:** Suite de pruebas unitarias exhaustiva (50 tests) para el sistema G2P (Grafema a Fonema).

**Qué valida:**
- Mapeo exacto de los **38 fonemas canónicos** ASCII (vocales cortas, largas, consonantes simples, complejas, aspiradas `PH TH KH QH CHH` y eyectivas `P_EJ T_EJ K_EJ Q_EJ CH_EJ`).
- Resolución voraz de trígrafos y dígrafos (`chh` sobre `ch`, `chʼ` sobre `ch`).
- Distinción fonológica entre fricativas `j` (velar) y `x` (uvular).
- Normalización robusta de apóstrofes (`' ’ ‘ ʹ ʼ`) y tildes castellanas vs. diéresis nativas (`ï` → `II`, `í` → `I`).
- Adaptación fonética de préstamos y nombres propios (`pedro` → `P E T R O`, `lorenzo` → `L O R E N S O`).

**Uso:**
```bash
python3 ASR/scripts/pruebas/tests/test_g2p.py
# o usando pytest:
pytest ASR/scripts/pruebas/tests/test_g2p.py -v
```
