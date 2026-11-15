# Módulo Unity — Entorno de Aplicación Móvil y Recursos Educativos

Este directorio contiene los datos de runtime, audios estandarizados y herramientas de compilación curricular para la aplicación móvil educativa offline desarrollada en **Unity / C#** (Revitalización de la lengua Uchumataqu / Uru de Irohito).

---

## 📁 Estructura del Directorio

```text
UNITY/
├── datos_app/                      # Artefactos JSON consumidos en tiempo de ejecución
│   ├── palabras.json               # Raíces léxicas y formas documentadas (266 familias, 321 unidades)
│   ├── oraciones.json              # Oraciones canónicas (137 oraciones: 120 curriculares + 17 reserva)
│   ├── lecciones.json              # Definición de 26 lecciones pedagógicas (L01 a L26)
│   ├── lecciones_compiladas.json   # Secuencia de 879 microactividades interactivas (11 modalidades)
│   └── escenarios_ra.json          # Mapeo de 6 escenarios de Realidad Aumentada interactiva
│
├── audios_palabras/                # Audios WAV de palabras (16 kHz, Mono, -3.0 dBFS) (~326 archivos)
├── audios_oraciones/               # Audios WAV de oraciones (16 kHz, Mono, -3.0 dBFS) (~136 archivos)
│
├── reportes/                       # Auditorías y reportes de cobertura acústica
│   └── reporte_audios_app.txt      # Reporte detallado de cobertura y balance sonoro
│
├── scripts/                        # Pipelines de procesamiento y compilación
│   ├── corpus/                     # Generador y compilador curricular determinista
│   │   ├── lector_xlsx.py          # Lector de hojas de cálculo Excel
│   │   ├── distractores_corpus.py  # Algoritmo de distractores fonéticos y semánticos
│   │   ├── compilador_lecciones.py # Compilador pedagógico (11 tipos de actividad)
│   │   ├── preparar_corpus_app.py  # Orquestador general Excel -> datos_app/*.json
│   │   └── test_compilador_lecciones.py # 22 pruebas unitarias automatizadas
│   └── audio/                      # Estandarización acústica y normalización
│       ├── normalizar_audios.py    # Normalizador atómico de volumen pico a -3.0 dBFS
│       ├── verificar_audios_app.py # Auditoría de cobertura acústica de la App
│       ├── completar_audios_app.py # Asignador de mejores tomas de locutores
│       └── convertir_oraciones_sofia.py # Transcodificador de fuentes específicas
│
└── README.md                       # Esta guía
```

---

## 📝 Guía Paso a Paso: Cómo Organizar y Agregar Contenidos

### 1. ¿Cómo agregar nuevas palabras al vocabulario?

1. **Editar la fuente autoritativa en Excel**:
   - Abra el archivo `excel/palabras_app.xlsx`.
   - Inserte la nueva palabra respetando el formato de columnas:
     - **ID** (slug en minúsculas sin acentos, ej. `masota`).
     - **Uchumataqu** (grafía oficial estandarizada, ej. `Masota`).
     - **Español** (traducción pedagógica primaria, ej. `Gato`).
     - **Categoría** (sustantivo, verbo, adjetivo, pronombre, etc.).
   - *Nota*: Si la palabra contiene formas flexionadas o derivadas (ej. plural `-naka`), regístrelas asociadas a su raíz según `05-guia-corpus-datos.md`.
2. **Exclusión estricta de nombres propios en actividades**:
   - Los nombres propios contextuales (`Pedro`, `Lorenzo`, `María`, `Juana`, `Waki`, `Irohito Urus`) se clasifican como `nombre_propio`.
   - El compilador los excluye automáticamente de distractores de selección múltiple para evitar ambigüedad evaluativa.
3. **Recompilar el corpus de datos**:
   ```bash
   python3 UNITY/scripts/corpus/preparar_corpus_app.py
   ```
4. **Validar la consistencia**:
   ```bash
   python3 -m unittest UNITY/scripts/corpus/test_compilador_lecciones.py
   python3 validar_todo.py
   ```

---

### 2. ¿Cómo agregar nuevas oraciones al currículo?

1. **Editar la fuente en Excel**:
   - Abra `excel/oraciones.xlsx`.
   - Añada la nueva fila con:
     - **ID**: `O_XXX` (del `O_001` al `O_120` para curriculares, `O_121` en adelante para reserva/distractores).
     - **Uchumataqu**: Oración canónica con puntuación y mayúsculas adecuadas.
     - **Español**: Traducción exacta al castellano.
2. **Asignación curricular en `lecciones.json`**:
   - El compilador distribuye las oraciones en las lecciones temáticas correspondientes (4 a 5 oraciones por lección).
3. **Recompilar los datos JSON**:
   ```bash
   python3 UNITY/scripts/corpus/preparar_corpus_app.py
   ```

---

### 3. ¿Cómo agregar y organizar grabaciones de audio?

Todos los audios de la aplicación deben cumplir los estándares técnicos de Unity para Android:
- **Formato**: WAV PCM sin compresión con pérdida.
- **Canales**: 1 canal (Mono).
- **Frecuencia de muestreo**: 16,000 Hz (16 kHz).
- **Resolución**: 16-bit.
- **Volumen pico**: Exactamente **-3.0 dBFS** (evita saturación y asegura volumen homogéneo).

#### Procedimiento:
1. **Colocar grabaciones crudas**:
   Deposite los audios sin recortar en `audios_originales/` o `ASR/audios_originales/`.
2. **Limpiar y segmentar tomas**:
   ```bash
   # Para palabras:
   python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor pedro --app
   
   # Para oraciones:
   python3 ASR/scripts/limpieza/limpiar_oraciones.py --locutor pedro --app
   ```
   *El parámetro `--app` copia automáticamente la mejor toma canónica (`_01.wav`) a `UNITY/audios_palabras/` u `UNITY/audios_oraciones/` con el nombre `{id}.wav`.*
3. **Normalizar el volumen pico a -3.0 dBFS**:
   ```bash
   python3 UNITY/scripts/audio/normalizar_audios.py
   ```
4. **Auditar la cobertura acústica**:
   ```bash
   python3 UNITY/scripts/audio/verificar_audios_app.py
   ```
   Este comando genera un informe en `UNITY/reportes/reporte_audios_app.txt` verificando que no existan audios faltantes ni sobrantes.

---

### 4. Estructura Curricular: Las 26 Lecciones y los 6 Escenarios RA

El currículo gamificado está organizado en **26 lecciones** (`L01` a `L26`) y **6 escenarios de Realidad Aumentada**:

| Escenario RA | Lecciones Asociadas | Eje Temático |
| :--- | :--- | :--- |
| `ra_encuentro_comunicacion` | `L01`, `L02`, `L03`, `L04`, `L05` | Saludos, presentaciones y diálogo inicial |
| `ra_familia_vestimenta` | `L06`, `L07`, `L08`, `L09`, `L10` | Núcleo familiar y vestimenta tradicional Uru |
| `ra_casa_objetos` | `L11`, `L12`, `L13`, `L14` | Espacios del hogar, utensilios y objetos escolares |
| `ra_cocina_alimentos` | `L15`, `L16`, `L17`, `L18` | Cocina tradicional y alimentos de la región |
| `ra_animales_ecosistema` | `L19`, `L20`, `L21`, `L22`, `L23` | Fauna silvestre, doméstica y aves del lago |
| `ra_naturaleza_orientacion` | `L24`, `L25`, `L26` | Flora, elementos naturales y navegación en balsa |

#### Modalidades de Actividad en Runtime (Catálogo de 11 tipos):
1. `presentacion_familia`: Tarjeta de introducción léxica con audio y traducción.
2. `uch_a_es`: Selección múltiple de traducción Uchumataqu -> Español.
3. `audio_a_uch`: Discriminación auditiva con opciones escritas.
4. `audio_a_forma`: Reconocimiento auditivo de formas flexionadas.
5. `emparejar_uch_es`: Minijuego de asociación de pares (2 a 5 parejas).
6. `escribir_palabra`: Dictado y escritura con teclado en pantalla.
7. `escribir_forma`: Escritura de palabras con sufijos de flexión.
8. `escribir_oracion`: Escritura libre de oraciones completas.
9. `ordenar_oracion`: Reconstrucción sintáctica mediante bancos de palabras (*word bank*).
10. `escucha_y_repite_asr`: Pronunciación por voz evaluada con el modelo ASR (palabras).
11. `escucha_y_repite_oracion_asr`: Pronunciación por voz de oraciones completas.

---

## 🔄 Sincronización con el Proyecto Unity en Windows

Para transferir los datos y audios desde WSL hacia el motor Unity en Windows (`D:\unity\Uchumataqu`), se utiliza el script seguro `sincronizar_unity.py`.

### Mapeo de Destinos en Unity

| Origen en WSL (`UNITY/`) | Destino en Unity (`Assets/`) | Archivos |
| :--- | :--- | :--- |
| `UNITY/datos_app/` | `Assets/Content/Data/` | `lecciones_compiladas.json`, `palabras.json`, `oraciones.json` |
| `PLN/hfst/export/pln-hfst-v1/` | `Assets/Content/Data/PLN/` | `analyses.json`, `lookup-index.json` |
| `UNITY/audios_palabras/` | `Assets/Content/Audio/Palabras/` | Archivos `*.wav` |
| `UNITY/audios_oraciones/` | `Assets/Content/Audio/Oraciones/` | Archivos `*.wav` |
| `Specifications/` | `Docs/Specifications/` | Especificaciones `*.md` |

> [!IMPORTANT]
> **Preservación de Metadatos `.meta`**:
> El sincronizador **nunca** crea, modifica ni elimina archivos `.meta` dentro de `Assets/`. Unity mantiene el control exclusivo de sus GUIDs y referencias internas.

### Comandos de Sincronización:

```bash
# 1. Simulación sin tocar el disco (Dry-Run):
python3 sincronizar_unity.py --dry-run

# 2. Sincronización normal (copia únicamente archivos nuevos o modificados por SHA-256):
python3 sincronizar_unity.py

# 3. Sincronización con eliminación de huérfanos (limpia archivos que fueron borrados en WSL):
python3 sincronizar_unity.py --delete
```

---

## 🧪 Pruebas y Validación de Calidad

Antes de sincronizar o compilar la APK de Unity, ejecute siempre la suite de validación:

```bash
# Ejecutar las pruebas unitarias del compilador:
python3 -m unittest UNITY/scripts/corpus/test_compilador_lecciones.py

# Ejecutar la suite integral de 25 reglas:
python3 validar_todo.py
```
Ambas verificaciones deben finalizar con `100% OK` sin errores.
