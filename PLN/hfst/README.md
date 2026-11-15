# Módulo HFST — Analizador Morfológico de Estados Finitos (Uchumataqu)

Este directorio contiene la implementación, compilador, entorno de pruebas y exportador del **analizador y generador morfológico de estados finitos (HFST — Helsinki Finite-State Transducer Technology)** para la lengua indígena originaria **Uchumataqu (Uru de Irohito)**.

El transductor modela la morfología aglutinante y derivativa documentada en las fuentes primarias (Hannss 2008, Métraux 1935, Uhle 1894), permitiendo la segmentación precisa de raíces léxicas y morfemas de flexión/derivación (como el pluralizador `-naka`, enfático `-pini`, diminutivo `-cha`, limitativo `-skama`, entre otros).

---

## 📁 Estructura del Directorio

```text
PLN/hfst/
├── src/uchumataqu_hfst/            # Paquete Python del compilador y runtime
│   ├── __init__.py
│   ├── __main__.py                 # Interfaz de línea de comandos (CLI)
│   ├── build.py                    # Compilador Lexc -> HFST -> HFSTOL y verificador
│   ├── data.py                     # Carga de datos, normalización Unicode y auditoría
│   ├── native.py                   # Envoltorios de subprocesos nativos HFST (C++)
│   └── runtime.py                  # Motor de consulta, abstención y comparación pedagógica
│
├── grammar/                        # Especificación gramatical generada
│   └── lexicon.lexc                # Gramática Léxica formal en formato Lexc
│
├── build/                          # Transductores compilados intermedios
│   ├── generator.hfst              # Generador morfológico (análisis -> superficie)
│   ├── analyzer.hfst               # Analizador invertido (superficie -> análisis)
│   └── analyzer.hfstol             # Transductor de búsqueda optimizado para memoria
│
├── export/pln-hfst-v1/             # Artefactos empaquetados para producción y Unity
│   ├── transducer.hfst             # Transductor estándar
│   ├── transducer.hfstol           # Transductor optimizado (consulta en sub-milisegundos)
│   ├── lexicon.lexc                # Gramática formal documentada
│   ├── analyses.json               # Diccionario de análisis morfológicos indexados
│   ├── lookup-index.json           # Índice de búsqueda rápida para runtime C#
│   ├── normalization.json          # Reglas canónicas de normalización textual
│   └── manifest.json               # Manifiesto de integridad criptográfica SHA-256
│
├── shared/raw/                     # Copias congeladas de las fuentes primarias
│   ├── palabras.json
│   ├── oraciones.json
│   ├── diccionario.json
│   └── reglas_de_escritura_y_gram_tica_uchumataqu.md
│
├── tests/                          # Suite de pruebas automatizadas
│   └── test_hfst.py                # 27 tests unitarios y de regresión con Pytest
│
├── tools/                          # Binarios y bibliotecas nativas HFST
│   └── setup.sh                    # Script de instalación autónoma sin permisos root
│
├── reports/                        # Auditorías y métricas de compilación
│   ├── hfst-metrics.json
│   └── data-audit.json
│
├── run.sh                          # Lanzador principal del CLI HFST
├── test.sh                         # Lanzador de la suite de pruebas
└── README.md                       # Esta guía
```

---

## ⚙️ Requisitos y Reconstrucción del Entorno Nativo

El módulo opera de manera autónoma en Linux (Ubuntu 22.04 / 24.04 o WSL2 x86_64) utilizando binarios nativos de HFST extraídos localmente en `tools/` sin requerir permisos de superusuario (`sudo`).

### Instalación de dependencias:

```bash
# 1. Configurar binarios y entorno virtual Python:
bash PLN/hfst/tools/setup.sh

# 2. Compilar el transductor:
bash PLN/hfst/run.sh build

# 3. Ejecutar las pruebas para verificar la instalación:
bash PLN/hfst/test.sh -q
```

---

## 🔨 Cómo Compilar el Transductor HFST (Paso a Paso)

El proceso de construcción y compilación morfológica se ejecuta mediante el comando:

```bash
bash PLN/hfst/run.sh build
```

O directamente mediante el módulo Python:
```bash
PLN/hfst/.venv/bin/python -m uchumataqu_hfst build
```

### ¿Qué hace internamente el compilador (`build.py`)?

1. **Lectura y Auditoría Léxica (`data.py`)**:
   - Carga las unidades léxicas de `palabras.json` y los contextos oracionales.
   - Aplica normalización Unicode NFC, minúsculas y estandarización de apóstrofes (`’` y `ʼ` a `'`).
2. **Generación de la Gramática Formal (`grammar/lexicon.lexc`)**:
   - Define los símbolos multicarácter (`Multichar_Symbols`) correspondientes a las categorías gramaticales (`+N`, `+V`, `+ADJ`, `+ADV`, etc.) y sufijos documentados (`+SUF=naka`, `+SUF=pini`, `+SUF=cha`, etc.).
   - Define el léxico `Root` que mapea cada raíz a su correspondiente clase de continuación (`F0`, `F1`, ...).
   - Genera las transiciones morfológicas regulares y formas irregulares documentadas.
3. **Compilación del Transductor Generador (`hfst-lexc`)**:
   - Compila `lexicon.lexc` hacia el grafo binario de estados finitos `generator.hfst`.
4. **Inversión de Direccionalidad (`hfst-invert`)**:
   - Invierte las cintas de entrada y salida para transformar el generador morfológico en un **analizador morfológico** (`analyzer.hfst`), capaz de recibir una forma de superficie escrita (ej. `achasinaka`) y emitir su análisis (`achasi+N+ID=achasi+SUF=naka`).
5. **Optimización de Transductor (`hfst-fst2fst -O`)**:
   - Compila el analizador al formato indexado de búsqueda en memoria `analyzer.hfstol` (*Optimized Lookup FST*), permitiendo resoluciones morfológicas en menos de 5 milisegundos.
6. **Verificación Exhaustiva de Paridad**:
   - Ejecuta una prueba de regresión automática consultando el 100% de las formas documentadas. Si existe una sola divergencia o error de segmentación, el proceso se detiene inmediatamente.
7. **Exportación de Artefactos de Distribución**:
   - Empaqueta los binarios y diccionarios JSON en `export/pln-hfst-v1/` para su consumo directo en Unity / C#.

---

## 💻 Uso en Línea de Comandos (CLI)

### 1. Analizar una palabra individual:
```bash
bash PLN/hfst/run.sh analyze achasinaka
```
**Salida JSON:**
```json
{
  "input": "achasinaka",
  "normalized": "achasinaka",
  "engine": "hfst",
  "status": "analyzed",
  "analyses": [
    {
      "id": "achasinaka",
      "surface": "achasinaka",
      "lemma": "achasi",
      "pos": "N",
      "suffixes": ["naka"],
      "translation": "Almohadas"
    }
  ]
}
```

### 2. Comparar la respuesta de un estudiante frente al objetivo:
```bash
bash PLN/hfst/run.sh compare achasi achasinaka
```
Permite distinguir si la diferencia ortográfica corresponde a un error tipográfico, a otra palabra distinta, o a una variación morfológica válida dentro de la misma familia léxica.

---

## 🖥️ Consola Interactiva en Tiempo Real

El repositorio incluye una herramienta visual interactiva en terminal con resaltado de sintaxis y explicación gramatical de sufijos:

```bash
python3 probar_hfst_tiempo_real.py
```

### Características de la Consola:
- **Resaltado ANSI por colores** de lemas, categorías gramaticales y sufijos.
- **Glosario morfológico automático**: Desglosa en lenguaje natural el significado de cada morfema (ej. `-naka`: pluralizador nominal; `-pini`: intensificador enfático; `-skama`: limitativo temporal).
- **Sugerencias por similitud Levenshtein**: Si se ingresa una palabra con un error menor de escritura, sugiere las formas canónicas documentadas más cercanas.
- **Comando de ejemplos**: Escriba `ejemplos` dentro de la consola para ver formas representativas.

---

## 🧪 Pruebas Automatizadas

Para ejecutar las 27 pruebas unitarias de regresión lingüística:

```bash
bash PLN/hfst/test.sh
```

Verifica:
- Determinismo de compilación e idempotencia.
- Manejo correcto de diacríticos y apóstrofes.
- Cobertura del 100% del vocabulario curricular documentado.
- Detección y abstención controlada ante entradas no documentadas (`unknown`).
- Paridad idéntica entre el transductor estándar `.hfst` y el optimizado `.hfstol`.

---

## 🔗 Integración con Unity / C#

Los archivos generados en `export/pln-hfst-v1/` (`analyses.json` y `lookup-index.json`) son sincronizados hacia `Assets/Content/Data/PLN/` en Unity mediante el comando:

```bash
python3 sincronizar_unity.py
```

Esto permite que la aplicación móvil ejecute validaciones morfológicas instantáneas en Android sin necesidad de librerías nativas compiladas por plataforma.
