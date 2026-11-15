# 🏋️ Scripts de Preparación de Datos ASR

Contiene el pipeline de preparación de datos, inventario fonológico canónico y particiones
del corpus Uchumataqu (Uru de Irohito). Es la fuente de datos canónica que alimenta las
**recetas oficiales de `pipeline_icefall/`**.

---

## 📋 Scripts en esta carpeta

### `lector_xlsx.py`

**Propósito:** Utilidad auxiliar para leer archivos Excel `.xlsx` sin dependencias externas pesadas.

**Uso:** Importado internamente por `preparar_asr.py` y `preparar_dataset.py`.

```python
from lector_xlsx import leer_xlsx
filas = leer_xlsx("excel/palabras_pln.xlsx")
```

---

### `preparar_asr.py`

**Propósito:** Genera los archivos canónicos del inventario fonológico de Uchumataqu.

**Qué hace:**
- Implementa el sistema **G2P (Grafema a Fonema)** para el idioma Uchumataqu con 38 fonemas canónicos en codificación ASCII.
- Genera `datos_asr/tokens.txt` — inventario de 42 tokens (4 especiales + 38 fonemas).
- Genera `datos_asr/lexicon.txt` — diccionario de pronunciación (palabra → fonemas).
- Genera `datos_asr/corpus_asr_texto.txt` — corpus textual de referencia.

**Entradas:**
```
excel/palabras_pln.xlsx
excel/oraciones.xlsx
```

**Salidas:**
```
ASR/datos_asr/tokens.txt            # 42 tokens: <blk> <sos/eos> <unk> <sil> + 38 fonemas
ASR/datos_asr/lexicon.txt           # ~326 entradas léxicas fonetizadas
ASR/datos_asr/corpus_asr_texto.txt  # 482 líneas normalizadas
```

**Uso:**
```bash
python3 ASR/scripts/entrenamiento/preparar_asr.py
```

**Inventario fonológico (38 fonemas canónicos ASCII):**

| Categoría | Fonemas |
|---|---|
| Vocales cortas | `A E I O U` |
| Vocales largas | `AA EE II OO UU` |
| Consonantes simples | `P T K Q M N R S X J L Y W` |
| Consonantes complejas | `TS CH SH LL NY` |
| Aspiradas | `PH TH KH QH CHH` |
| Eyectivas | `P_EJ T_EJ K_EJ Q_EJ CH_EJ` |

---

### `preparar_dataset.py`

**Propósito:** Escanea todos los audios individuales normalizados en `audios_palabras/` y `audios_oraciones/`, los valida acústicamente (16 kHz, mono, duración mínima) y genera los splits de entrenamiento estratificados.

**Salidas:**
```
ASR/data/manifests/
├── all_manifest.json     # Todos los audios validados con metadatos
├── train_manifest.json   # Partición de entrenamiento (~80%)
├── val_manifest.json     # Partición de validación (~10%)
├── test_manifest.json    # Partición de prueba (~10%)
└── kaldi/                # Formato Kaldi (wav.scp, text, utt2spk, spk2utt)
```

**Uso:**
```bash
python3 ASR/scripts/entrenamiento/preparar_dataset.py
```

---

## 📌 Flujo de Ejecución Hacia las Recetas Oficiales

```bash
# 1. Generar inventario fonológico y léxico canónico:
python3 ASR/scripts/entrenamiento/preparar_asr.py

# 2. Validar audios y generar particiones del dataset:
python3 ASR/scripts/entrenamiento/preparar_dataset.py

# 3. Convertir los manifests al formato Lhotse requerido por Icefall:
python3 ASR/pipeline_icefall/uchumataqu/prepare_uchumataqu.py

# 4. Iniciar entrenamiento con las recetas oficiales clonadas de Icefall:
bash ASR/pipeline_icefall/run_train_scratch.sh    # Desde cero
# o
bash ASR/pipeline_icefall/run_finetune.sh          # Fine-tuning con checkpoint
```
