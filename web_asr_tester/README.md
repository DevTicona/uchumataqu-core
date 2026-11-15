# Web ASR Tester — Servidor de Pruebas y Diagnóstico Fonético en Tiempo Real

Este directorio contiene una herramienta web interactiva para la prueba, diagnóstico y evaluación acústico-fonética en tiempo real de los modelos ASR de la lengua **Uchumataqu**.

Permite evaluar grabaciones de voz tanto de palabras individuales como de oraciones completas, mostrando métricas detalladas de pronunciación (PER, WER, CER), alineación fonética interactiva y diagnóstico de la señal de audio.

---

## 🚀 Inicio Rápido

Para iniciar el servidor local:

```bash
bash web_asr_tester/iniciar_servidor.sh
```

O directamente mediante Python:
```bash
python3 web_asr_tester/server.py --port 8080
```

Abra su navegador web en: **`http://localhost:8080`**

---

## ✨ Características Principales

1. **Gestor Multi-Modelo en Memoria**:
   - `scratch_int8`: **Modelo oficial en producción** (Zipformer 100 épocas cuantizado INT8 - 72 MB).
   - `scratch_fp32`: Zipformer 100 épocas Float32 completo (262 MB).
   - `finetune_int8`: Zipformer adaptado desde LibriSpeech (70 MB).
   - `finetune_fp32`: Zipformer adaptado Float32 (250 MB).
2. **Modos de Decodificación**:
   - `greedy_search`: Decodificación acústica pura frame a frame.
   - `con_restricciones`: Decodificación guiada con el léxico pedagógico cerrado para recuperar fonemas elididos en oraciones.
3. **Entrada de Audio Flexible**:
   - Grabación en vivo mediante micrófono web (HTML5 MediaRecorder API).
   - Carga de archivos locales en cualquier formato (WAV, MP3, WebM, Opus, M4A, OGG), transcodificados automáticamente con `ffmpeg` a 16 kHz Mono.
4. **Inspección y Diagnóstico Fonético**:
   - Motor G2P canónico (38 fonemas Uchumataqu).
   - Visualizador de alineación fonética (*Matches*, *Substitutions*, *Deletions*, *Insertions*).
   - Semáforo de aprobación pedagógica (Umbral configurable: 85% por defecto).
   - Diagnóstico acústico: duración exacta, silencios inicial y final, detección de recorte (*clipping*).
5. **Exportación de Reportes**:
   - Descarga de resultados y matrices de evaluación en formato CSV para análisis estadístico.

---

## 📡 Endpoints de la API REST

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Servidor frontend (HTML/CSS/JS) |
| `GET` | `/api/info` | Información del sistema, modelos disponibles y estado |
| `GET` | `/api/corpus` | Catálogo de palabras y oraciones curriculares |
| `POST` | `/api/g2p` | Conversión grafema a fonema (G2P) de texto en Uchumataqu |
| `POST` | `/api/evaluate` | Inferencia ASR y cálculo de métricas acústico-fonéticas |
| `POST` | `/api/export_csv` | Generación y exportación de reportes de evaluación |

---

## 🧪 Pruebas Automatizadas

```bash
# Pruebas de endpoints de la API:
python3 web_asr_tester/test_api_endpoints.py

# Pruebas de lógica fonética y métricas:
python3 web_asr_tester/test_server_logic.py
```
Ambas suites deben pasar exitosamente.
