# Uchumataqu — Proyecto de Grado

Aplicación móvil educativa offline para la revitalización de la lengua indígena originaria **Uchumataqu (Uru de Irohito)**, integrando procesamiento del lenguaje natural (PLN), reconocimiento automático del habla (ASR offline) y Realidad Aumentada (RA) en Unity.

---

## Estructura del Entorno WSL

```text
proyecto-grado/
├── Para_Unity/
│   ├── datos_app/            # Datos JSON procesados para runtime
│   ├── audios_palabras/      # Audios de palabras normalizados
│   ├── audios_oraciones/     # Audios de oraciones
│   └── reportes/             # Reportes de auditoría y validación
├── Specifications/           # Especificaciones técnicas (fuente autoritativa)
├── Para_ASR/                 # Modelos, lexicones y recursos de Sherpa-onnx (no sincronizados)
├── audios_originales/        # Corpus de audio original
├── excel/                    # Fuentes léxicas y oraciones en hojas de cálculo
├── sincronizar_unity.py      # Script de sincronización WSL -> Unity
└── README.md
```

---

## Sincronización con Unity

El proyecto utiliza un mecanismo de **sincronización automática y segura por copia controlada** (sin enlaces simbólicos) desde WSL hacia el proyecto Unity en Windows (`D:\unity\Uchumataqu`, montado en `/mnt/d/unity/Uchumataqu`).

### Mapeo de Sincronización

| Origen en WSL | Destino en Unity | Contenido |
|---|---|---|
| `Para_Unity/datos_app/` | `Assets/Content/Data/` | `*.json` (excluye `lecciones.json`, scripts, temporales) |
| `Para_Unity/audios_palabras/` | `Assets/Content/Audio/Palabras/` | `*.wav`, `*.mp3`, `*.ogg` |
| `Para_Unity/audios_oraciones/` | `Assets/Content/Audio/Oraciones/` | `*.wav`, `*.mp3`, `*.ogg` |
| `Specifications/` | `Docs/Specifications/` | `*.md` (recursivo) |

> [!NOTE]
> `Specifications/` en WSL es la **fuente autoritativa** de `Docs/Specifications/` en Unity. Cualquier cambio en la documentación debe realizarse en WSL y sincronizarse con este comando.

> [!IMPORTANT]
> - **Archivos `.meta`**: El sincronizador **nunca** crea, modifica, copia ni elimina archivos `.meta` dentro de `Assets/`. Unity es el único responsable de gestionar sus metadatos.
> - **Módulo ASR**: Modelos ONNX, `lexicon.txt`, `tokens.txt` y corpus de entrenamiento de `Para_ASR/` **no forman parte de esta sincronización**.

---

### Configuración

Defina la ruta hacia el proyecto Unity mediante la variable de entorno:

```bash
export UNITY_PROJECT_PATH="/mnt/d/unity/Uchumataqu"
```

Opcionalmente, puede crear un archivo `.env` en la raíz del proyecto WSL:

```env
UNITY_PROJECT_PATH=/mnt/d/unity/Uchumataqu
```

O pasar la ruta directamente mediante `--unity-path`:

```bash
python sincronizar_unity.py --unity-path "/mnt/d/unity/Uchumataqu"
```

---

### Comandos de Uso

#### 1. Simulación (Dry-Run)
Verifica qué archivos serían copiados, actualizados o detectados como huérfanos sin realizar ninguna modificación en el disco:

```bash
python sincronizar_unity.py --dry-run
```

#### 2. Sincronización Normal
Compara mediante SHA-256 y copia únicamente los archivos nuevos o modificados:

```bash
python sincronizar_unity.py
```

#### 3. Eliminación de Huérfanos
Elimina archivos en los destinos autorizados de Unity que ya no existen en WSL (los `.meta` en Assets se preservan para que Unity los limpie):

```bash
python sincronizar_unity.py --delete
```

#### 4. Simulación de Eliminación
Muestra qué archivos huérfanos serían eliminados sin alterar nada:

```bash
python sincronizar_unity.py --dry-run --delete
```
