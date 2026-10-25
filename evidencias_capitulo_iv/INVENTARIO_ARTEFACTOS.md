# Inventario de Artefactos — Repositorio Lingüístico Uchumataqu
**Proyecto de Grado:** Aplicación móvil educativa offline para la revitalización del idioma Uchumataqu integrando procesamiento de lenguaje natural y realidad aumentada. Caso: FUNPROEIB ANDES  
**Universidad:** Universidad Pública de El Alto (UPEA) — Carrera de Ingeniería de Sistemas  
**Fecha de Inspección:** 24 de Octubre de 2026  
**Entorno de Ejecución:** Linux x86_64 (WSL2 Ubuntu 24.04 LTS), Python 3.12.3, OnnxRuntime 1.19.2, Sherpa-ONNX 1.10.30  

---

## 1. Corpus Primario y Datos de la Aplicación

| Artefacto | Ruta en Repositorio | Versión / Formato | Tamaño (Bytes) | Hash SHA-256 |
| :--- | :--- | :--- | :---: | :--- |
| **Lecciones Compiladas** | `UNITY/datos_app/lecciones_compiladas.json` | v4 (11 modalidades) | 343,239 | `ac854f207b9301cfdad9cec72d4baa395a7fc39ed9f1e98ed896dcac5bbd2f07` |
| **Vocabulario Canónico** | `UNITY/datos_app/palabras.json` | v1 (266 familias) | 40,932 | `8ae33d355010e9a871235a3856712ed4748b82c858833808a355677e89388595` |
| **Oraciones Curriculares** | `UNITY/datos_app/oraciones.json` | v1 (137 oraciones) | 16,085 | `0823cb212a2c4420bd63167120a1e4df585c9339d100c9b4edbd8e2aa4ec6268` |
| **Estructura Curricular** | `UNITY/datos_app/lecciones.json` | v1 (26 lecciones) | 5,282 | `9dcc73f7a8d5b289b165b84c20010a03661762cbce1c07ccaee27457aaa6d6d4` |
| **Escenarios RA** | `UNITY/datos_app/escenarios_ra.json` | v1 (6 escenarios) | 59,602 | `0b291f29a7250ef5bdb7fd616f8059c8c67725ebb7d297440db869524a72386c` |
| **Oraciones PLN Fuente** | `PLN/oraciones.json` | v1 (137 oraciones) | 16,085 | `b12e32fe013bafd75b842f9ffda81811fdbc7cb2d0b4634dc36541d4e3fc236e` |
| **Palabras PLN Fuente** | `PLN/palabras.json` | v1 (266 familias) | 40,932 | `8ae33d355010e9a871235a3856712ed4748b82c858833808a355677e89388595` |

---

## 2. Artefactos del Módulo PLN / HFST

| Artefacto | Ruta en Repositorio | Descripción / Motor | Tamaño (Bytes) | Hash SHA-256 |
| :--- | :--- | :--- | :---: | :--- |
| **Gramática Lexc** | `PLN/hfst/grammar/lexicon.lexc` | Lexc acíclico documentado | 22,912 | `a9afebe194e88e6431d8bb9c49ff20cd1a7a98af9b8a9c1e16d33cd7b9204dd0` |
| **Exportación Análisis** | `PLN/hfst/export/pln-hfst-v1/analyses.json` | 326 formas analizadas | 152,819 | `0533ede6a5262e7f6719afbd900b307384cdb7703e43182a520a98120705e70f` |
| **Índice Precompilado** | `PLN/hfst/export/pln-hfst-v1/lookup-index.json` | Índice O(1) de formas | 17,041 | `bdf278933b16955809b10a804dacaf59cfe0380f0be260f494ee186f40d0d90c` |
| **Transductor Optimizado** | `PLN/hfst/export/pln-hfst-v1/analyzer.hfstol` | Formato HFST Optimized Lookup | 37,677 | `dfb1350e70d7d242ba25c35a92549320e92620bb49624353d443ef77e26ee6e2` |
| **Generador Morfológico** | `PLN/hfst/export/pln-hfst-v1/generator.hfst` | Transductor generador acíclico | 57,869 | `1fe1278dd1a32e6ab6210d04918810783383eb69e15f36f3e73cce3e02df24c5` |
| **Verificación de Integridad** | `PLN/hfst/export/pln-hfst-v1/SHA256SUMS` | Hashes oficiales del paquete v1 | 632 | `f3152d0fa578912d09dfad7c050a4176313364f77c68a41031c518ca86e00181` |

---

## 3. Artefactos del Módulo ASR (Reconocimiento Automático del Habla)

| Artefacto | Ruta en Repositorio | Descripción / Formato | Tamaño (Bytes) | Hash SHA-256 |
| :--- | :--- | :--- | :---: | :--- |
| **Modelo ONNX INT8** | `ASR/models/exported_onnx/model.int8.onnx` | Zipformer CTC cuantizado INT8 | 72,584,427 | `4db84814c24822f257c8b649c5a621a17437edd051aebea82fe5151d2a4f5fda` |
| **Modelo ONNX FP32** | `ASR/models/exported_onnx/model.onnx` | Zipformer CTC FP32 sin cuantizar | 262,141,559 | `f6dee2ea850ddd29eea6f1de9839bc5ea8c6d4afdb4bf4a9b18b0ed51ac1f167` |
| **Tokens Fonéticos** | `ASR/datos_asr/tokens.txt` | 42 tokens canónicos (0 a 41) | 252 | `f48ecf95f55d2b10367d3e858c75a131731422f7af34c308a0d8e05b42bf6de7` |
| **Lexicón ASR** | `ASR/datos_asr/lexicon.txt` | 325 entradas Uchumataqu -> Fonemas | 7,382 | `860aa3105b1fe21dfcfbceeb1c47b8554bb7d5c378a4b5882502abf30da294bf` |
| **Corpus ASR Texto** | `ASR/datos_asr/corpus_asr_texto.txt` | 460 transcripciones normalizadas | 6,553 | `3f5bb71bade705bab90d97903adb142d9c1ad78caa12981be91776c6d4b03813` |
| **Manifiesto Global** | `ASR/data/manifests/all_manifest.json` | 4,739 grabaciones originales | 2,171,630 | `a83d94731db82e0b7f586936d0a77818a64c47ca7cef3295d69206b68d67f5c7` |
| **Manifiesto Train** | `ASR/data/manifests/train_manifest.json` | 4,860 tomas (Speed + MUSAN) | 2,277,889 | `25e6ad33c931ec1bf024f1ec9f013c24308a39af8cb44a9fbf4c0987a8b1385c` |
| **Manifiesto Val** | `ASR/data/manifests/val_manifest.json` | 459 tomas de validación | 213,813 | `4cb6be296993f41a73aa78795c31328b5deccc348bc0fd7d47b63971627494da` |
| **Manifiesto Test** | `ASR/data/manifests/test_manifest.json` | 460 tomas de prueba independiente | 214,008 | `9570029d14836451ef936d2afe3e4aa93936b408a660d7de94b25de00da4c39b` |

---

## 4. Banco Acústico de Referencia (Audios WAV 16 kHz Mono)

| Directorio | Contenido | Archivos | Estado Acústico |
| :--- | :--- | :---: | :--- |
| `UNITY/audios_palabras/` | Pronunciaciones canónicas de vocabulario | 326 | 16 kHz, Mono, PCM 16-bit, normalizado pico -3.0 dBFS |
| `UNITY/audios_oraciones/` | Lecturas orales de oraciones (`O_001` .. `O_135`) | 136 | 16 kHz, Mono, PCM 16-bit, normalizado pico -3.0 dBFS |
| `ASR/audios_palabras/` | Grabaciones de palabras por locutor (*eva, lorenzo, pedro, roberto, sofia*) | 3,115 | 16 kHz, Mono, PCM 16-bit (tomas múltiples) |
| `ASR/audios_oraciones/` | Grabaciones de oraciones por locutor (*eva, lorenzo, pedro, roberto, sofia, gaby*) | 1,489 | 16 kHz, Mono, PCM 16-bit (tomas múltiples) |
| `ASR/audios_originales/` | Tomas originales brutas (archivo histórico patrimonial) | 4,604 | Formato WAV/MP3 original preservado |
