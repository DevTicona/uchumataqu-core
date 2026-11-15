# 🧹 Scripts de Limpieza y Preprocesamiento de Audio

Contiene los scripts para procesar las **grabaciones crudas** (archivos originales con múltiples repeticiones) y transformarlas en audios individuales normalizados, listos para el pipeline de entrenamiento ASR.

---

## 📋 Scripts en esta carpeta

### `limpiar_palabras.py`

**Propósito:** Segmenta y normaliza grabaciones crudas de **palabras** individuales.

**Qué hace:**
- Detecta automáticamente los segmentos de voz usando umbrales de silencio adaptativos.
- Extrae hasta 4 repeticiones por palabra (`_01`, `_02`, `_03`, `_04`).
- Normaliza el audio a **-3 dBFS, 16 kHz mono 16-bit**.
- Añade márgenes de silencio al inicio y final.
- Opcionalmente, copia la toma `_01` a la carpeta de Unity (`--app`).

**Entradas:**
```
audios_originales/palabras/{locutor}/  ← grabaciones crudas
```

**Salidas:**
```
ASR/audios_palabras/{locutor}/{id}_01.wav
ASR/audios_palabras/{locutor}/{id}_02.wav
ASR/audios_palabras/{locutor}/{id}_03.wav
```

**Uso:**
```bash
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor pedro
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor eva --max_chunks 4
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor sofia --app
```

| Argumento | Descripción | Default |
|---|---|---|
| `--locutor` | Nombre del locutor | `eva` |
| `--input` | Carpeta con grabaciones originales | `audios_originales/palabras/{locutor}` |
| `--output` | Carpeta de destino | `ASR/audios_palabras/{locutor}` |
| `--max_chunks` | Repeticiones esperadas por archivo | automático por locutor |
| `--app` | Copiar toma 1 a carpeta Unity | desactivado |

---

### `limpiar_oraciones.py`

**Propósito:** Segmenta y normaliza grabaciones crudas de **oraciones completas**.

**Qué hace:**
- Similar a `limpiar_palabras.py` pero optimizado para oraciones más largas.
- Detecta 3 repeticiones por oración (`_01`, `_02`, `_03`).
- Pausa interna mínima de 500 ms para no fragmentar una oración en dos.
- Fusiona pausas internas < 800 ms (para no partir palabras de la oración).

**Entradas:**
```
audios_originales/oraciones/{locutor}/
```

**Salidas:**
```
ASR/audios_oraciones/{locutor}/{slug}_01.wav
ASR/audios_oraciones/{locutor}/{slug}_02.wav
ASR/audios_oraciones/{locutor}/{slug}_03.wav
```

**Uso:**
```bash
python3 ASR/scripts/limpieza/limpiar_oraciones.py --locutor pedro
python3 ASR/scripts/limpieza/limpiar_oraciones.py --locutor pedro --app
```

---

### `verificar_audios_asr.py`

**Propósito:** Auditoría de cobertura — compara los audios procesados contra el Excel PLN.

**Qué hace:**
- Lee `excel/palabras_pln.xlsx` y `excel/oraciones.xlsx`.
- Compara item por item qué locutores tienen 3 tomas completas, parciales o sin audio.
- Detecta audios sobrantes (archivos en carpeta sin entrada en Excel).
- Genera reporte detallado en `ASR/reportes/reporte_audios_asr.txt`.

**Uso:**
```bash
python3 ASR/scripts/limpieza/verificar_audios_asr.py
```

**Salida:** `ASR/reportes/reporte_audios_asr.txt`

---

### `renombrar_audios_oraciones_id.py`

**Propósito:** Sincronización de nombres de archivo — renombra los audios de oraciones en `ASR/audios_oraciones/` al ID de `oraciones.xlsx` (`O_xxx_yy.wav`) y elimina audios sobrantes.

**Uso:**
```bash
python3 ASR/scripts/limpieza/renombrar_audios_oraciones_id.py --dry-run
python3 ASR/scripts/limpieza/renombrar_audios_oraciones_id.py
```

---

## 🔗 Dependencias

```
pydub >= 0.25.1
ffmpeg  (instalado en el sistema: sudo apt install ffmpeg)
```

## 📌 Orden de ejecución recomendado

```bash
# 1. Limpiar palabras para cada locutor
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor pedro
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor sofia
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor eva
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor lorenzo
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor roberto

# 2. Limpiar oraciones
python3 ASR/scripts/limpieza/limpiar_oraciones.py --locutor pedro

# 3. Verificar cobertura
python3 ASR/scripts/limpieza/verificar_audios_asr.py
```

Una vez completada la limpieza, continúa con los scripts de **`../entrenamiento/`**.
