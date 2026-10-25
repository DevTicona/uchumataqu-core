# Resumen de Integración para Unity — Repositorio Lingüístico Uchumataqu
**Proyecto de Grado:** Aplicación móvil educativa offline para la revitalización del idioma Uchumataqu integrando procesamiento de lenguaje natural y realidad aumentada. Caso: FUNPROEIB ANDES  
**Destinatario:** Equipo de desarrollo del frontend y runtime en Unity (C# / Android)  
**Fecha:** 24 de Octubre de 2026  
**Versión de Contrato:** v4 (Estructura de 11 modalidades curriculares)  

---

## 1. Propósito y Alcance del Documento

Este documento define el **contrato formal de integración técnica** entre los artefactos producidos y validados en el repositorio lingüístico (WSL2/Linux) y la aplicación cliente interactiva desarrollada en **Unity (C#)** para dispositivos móviles Android.

> [!IMPORTANT]
> Este documento describe estrictamente los modelos, esquemas JSON, tokens y convenciones que Unity debe **consumir**. Las validaciones aquí descritas corresponden exclusivamente a las pruebas de software e inferencia realizadas en este repositorio; no asumen ni declaran ejecución en el motor Unity.

---

## 2. Mapa de Archivos a Consumir por Unity

Todos los artefactos se transfieren desde el repositorio hacia la estructura de assets del proyecto Unity mediante el script automatizado `sincronizar_unity.py`:

| Componente | Archivo en Repositorio (WSL) | Destino en Unity | Formato / Motor |
| :--- | :--- | :--- | :--- |
| **Currículo Compilado** | `UNITY/datos_app/lecciones_compiladas.json` | `Assets/Content/Data/lecciones_compiladas.json` | JSON v4 (UTF-8) |
| **Vocabulario Canónico** | `UNITY/datos_app/palabras.json` | `Assets/Content/Data/palabras.json` | JSON v1 (UTF-8) |
| **Oraciones y Traducciones**| `UNITY/datos_app/oraciones.json` | `Assets/Content/Data/oraciones.json` | JSON v1 (UTF-8) |
| **Escenarios RA** | `UNITY/datos_app/escenarios_ra.json` | `Assets/Content/Data/escenarios_ra.json` | JSON v1 (UTF-8) |
| **PLN - Análisis Morfológicos**| `PLN/hfst/export/pln-hfst-v1/analyses.json` | `Assets/Content/Data/PLN/analyses.json` | JSON estático (326 formas) |
| **PLN - Índice Rápido O(1)** | `PLN/hfst/export/pln-hfst-v1/lookup-index.json` | `Assets/Content/Data/PLN/lookup-index.json` | JSON de mapeo superficial |
| **Audios de Palabras** | `UNITY/audios_palabras/*.wav` (326 archivos) | `Assets/Content/Audio/Palabras/` | WAV 16 kHz Mono PCM-16 (-3 dBFS) |
| **Audios de Oraciones** | `UNITY/audios_oraciones/*.wav` (136 archivos) | `Assets/Content/Audio/Oraciones/` | WAV 16 kHz Mono PCM-16 (-3 dBFS) |
| **Modelo ASR Cuantizado** | `ASR/models/exported_onnx/model.int8.onnx` | `Assets/StreamingAssets/sherpa/model.int8.onnx` | ONNX INT8 (72.58 MB) |
| **Tokens ASR** | `ASR/datos_asr/tokens.txt` | `Assets/StreamingAssets/sherpa/tokens.txt` | Texto plano (42 tokens) |

---

## 3. Contrato del Compilador Curricular (`lecciones_compiladas.json`)

### 3.1 Estructura Pedagógica de Cada Lección
Cada una de las 26 lecciones (`L01` .. `L26`) está organizada estrictamente en **tres bloques consecutivos**:
1. **Bloque A (Vocabulario - Primera Mitad):**
   - Presentación de familia (`presentacion_familia`) seguida inmediatamente por su microactividad de reconocimiento (`uch_a_es`, `audio_a_uch` o `audio_a_forma`).
   - Actividad colectiva de emparejamiento 1 (`emparejar_uch_es`).
   - Refuerzo individual de la primera mitad (intercalación estricta de `escribir_palabra`/`escribir_forma` y `escucha_y_repite_asr`).
2. **Bloque B (Vocabulario - Segunda Mitad):**
   - Presentación de familias restantes con su microactividad inmediata.
   - Actividad colectiva de emparejamiento 2 (`emparejar_uch_es`).
   - Refuerzo individual de la segunda mitad.
3. **Bloque Final (Práctica de Oraciones):**
   - Intercalación balanceada para evitar monotonía:
     $$\text{ordenar\_oracion} \longrightarrow \text{escribir\_oracion (traducción)} \longrightarrow \text{ordenar\_oracion} \longrightarrow \text{ASR oral} \longrightarrow \text{ordenar\_oracion} \longrightarrow \text{escribir\_oracion (dictado)} \longrightarrow \dots$$

### 3.2 Catálogo Cerrado de 11 Modalidades de Actividad
Unity solo debe implementar los controladores para los siguientes 11 tipos (cualquier otro tipo está prohibido):
1. `presentacion_familia`: Muestra la ficha de la palabra/raíz con sus formas morfológicas y audio de ejemplo.
2. `uch_a_es`: Selección múltiple (texto Uchumataqu $\to$ 4 opciones en español).
3. `audio_a_uch`: Discriminación auditiva (audio Uchumataqu $\to$ 4 opciones textuales en Uchumataqu).
4. `audio_a_forma`: Reconocimiento morfológico (audio de forma flexionada $\to$ selección entre formas de la familia).
5. `emparejar_uch_es`: Mini-juego de emparejar entre 2 y 5 pares de palabras Uchumataqu-Español.
6. `escribir_palabra`: Escritura en teclado en pantalla de la raíz (fuente: traducción en español o dictado).
7. `escribir_forma`: Escritura en teclado de una forma morfológica derivada documentada.
8. `escucha_y_repite_asr`: Práctica de pronunciación de palabra mediante micrófono (opcional, no bloqueante).
9. `ordenar_oracion`: Reconstrucción sintáctica mediante fichas o bloques de palabras desordenadas.
10. `escribir_oracion`: Escritura libre de oración (traducción desde español o dictado auditivo).
11. `escucha_y_repite_oracion_asr`: Pronunciación oral de oración completa (opcional, no bloqueante).

---

## 4. Contrato de Integración PLN / HFST

Para evitar compilar transductores nativos C++ en Android, el repositorio provee dos opciones de integración:

### Opción A (Recomendada - Tiempo de Ejecución O(1)): Ingesta de JSON Precompilado
- **Carga:** Cargar en memoria `lookup-index.json` (17 KB) y `analyses.json` (152 KB) en el arranque de la lección.
- **Búsqueda:** Ante la respuesta escrita del usuario (ej. `"achasinaka"`):
  1. Aplicar normalización de cadena (ver sección 6).
  2. Buscar la clave en `lookup-index.json`.
  3. Si existe, extraer el registro correspondiente en `analyses.json`:
     ```json
     {
       "id": "p_achasinaka",
       "surface": "achasinaka",
       "lemma": "achasi",
       "pos": "N",
       "translation": "Almohadas",
       "segments": ["achasi", "naka"],
       "suffixes": ["naka"]
     }
     ```
  4. Si no existe, clasificar como `unknown` (palabra no registrada en el corpus documentado).

### Opción B: Transductor Nativo HFST (`analyzer.hfstol`)
- Si se dispone del binding C# nativo de `hfst-optimized-lookup`, consumir directamente `analyzer.hfstol` (37.6 KB).
- **Entrada:** `string` normalizado.
- **Salida:** Cadena con lema y etiquetas (ej. `achasi+N+Pl`).

---

## 5. Contrato de Integración ASR (Sherpa-ONNX)

### 5.1 Parámetros de Audio Requeridos
- **Frecuencia de muestreo:** 16,000 Hz (16 kHz).
- **Canales:** 1 (Mono).
- **Formato:** PCM 16-bit con signo (valores entre -32768 y 32767 normalizados a float `[-1.0, 1.0]`).
- **Nivel de grabación:** Se recomienda orientar al usuario a hablar a 15-20 cm del micrófono.

### 5.2 Inicialización del Motor en C# (Sherpa-ONNX)
```csharp
// Configuración para OfflineRecognizer Zipformer CTC
var config = new OfflineRecognizerConfig();
config.ModelConfig.ZipformerCtc.Model = Application.streamingAssetsPath + "/sherpa/model.int8.onnx";
config.ModelConfig.Tokens = Application.streamingAssetsPath + "/sherpa/tokens.txt";
config.ModelConfig.NumThreads = 2; // Óptimo para dispositivos móviles
config.ModelConfig.Debug = 0;

var recognizer = new OfflineRecognizer(config);
```

### 5.3 Decodificación y Evaluación Fonética Semáforo
1. La salida directa de `stream.Result.Tokens` es una lista de fonemas (ej. `["A", "CH", "A", "S", "I"]`).
2. Para evaluar la pronunciación del alumno frente al objetivo de la actividad:
   - Extraer la secuencia fonémica esperada desde `lexicon.txt` o desde la tabla fonética del corpus.
   - Calcular la distancia de Levenshtein a nivel de fonemas:
     $$\text{PER} = \frac{\text{DistanciaEdición}(\text{RefFon}, \text{HypFon})}{\text{Longitud}(\text{RefFon})}$$
     $$\text{Precisión} = \max(0.0, 100.0 - (\text{PER} \times 100))$$
3. **Lógica de Semáforo Pedagógico:**
   - **Verde (Aprobado Excelente):** $\text{Precisión} \ge 85.0\%$ $\longrightarrow$ Permite continuar con felicitación auditiva.
   - **Amarillo (Aceptable con Observación):** $70.0\% \le \text{Precisión} < 85.0\%$ $\longrightarrow$ Sugiere escuchar el audio modelo nuevamente.
   - **Rojo (Reintento Sugerido):** $\text{Precisión} < 70.0\%$ $\longrightarrow$ Permite reintentar o presionar "Continuar" (debido a `opcional: true`).

---

## 6. Reglas de Normalización de Texto Compartidas

Para asegurar que la evaluación en Unity coincida exactamente con los validadores del repositorio:
1. **Minúsculas:** Convertir texto con `ToLowerInvariant()`.
2. **Espacios en blanco:** Reemplazar tabulaciones, saltos de línea y espacios múltiples por un solo espacio (`" "`).
3. **Apostrofes y Eyectivas:**
   - Estandarizar cualquier variante tipográfica (`'`, `’`, `\u2018`, `\u2019`, `\u02bc`) al apóstrofe canónico del proyecto (`ʼ` U+02BC o `'` según el archivo de datos).
4. **Diacríticos Vocálicos:**
   - **No remover** las diéresis (`ä`, `ë`, `ï`, `ö`, `ü`) ni la virgulilla (`ñ`), ya que representan fonemas distintos (vocal larga o timbre velarizado).

---

## 7. Limitaciones y Casos de Borde Documentados

1. **Topónimo Comunal en L04:**
   - Las oraciones `O_016` y `O_018` contienen la comunidad `"Irohito Urus"` con mayúsculas iniciales. Las actividades de escritura y teclado deben contemplar esta capitalización como respuesta esperada canónica.
2. **Oración O_011:**
   - La oración `O_011` (`"Chhuñiqasichay"`, lección L04) posee una sola palabra compuesta de 1 token, por lo que **no debe generar** actividad de `ordenar_oracion`.
3. **Opcionalidad del Micrófono:**
   - Todos los pasos ASR tienen el atributo `"opcional": true`. Si el usuario deniega permisos de audio o el dispositivo carece de hardware compatible, la interfaz debe ofrecer un botón de avance ("Continuar sin voz") sin penalizar la calificación de la lección.
