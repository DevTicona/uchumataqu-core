# Seq2Seq uchumataqu

Piloto neuronal construido, entrenado en CPU con tres semillas y exportado a ONNX.
El modelo y su entorno son independientes de HFST. Los resultados aún no justifican
su uso educativo ni reemplazar la consulta de formas documentadas.

## Uso desde la raíz del proyecto

```bash
bash PLN/seq2seq/run.sh analyze Achasinaka
bash PLN/seq2seq/test.sh -q
```

La consulta ejecuta los grafos ONNX, devuelve la predicción original y compara su
estructura con el léxico documentado. `experimental_match` significa coincidencia
con una anotación provisional; `abstained` indica que no hay respaldo suficiente.
`unsupported_input` y `unsupported_character` rechazan entradas fuera del contrato.
No genera traducciones ni pistas lingüísticas inventadas y no recibe el objetivo
del ejercicio para alterar la respuesta.

## Reconstruir el experimento

```bash
bash PLN/seq2seq/tools/setup.sh
bash PLN/seq2seq/run.sh prepare
bash PLN/seq2seq/run.sh smoke
bash PLN/seq2seq/run.sh train
bash PLN/seq2seq/run.sh export
bash PLN/seq2seq/test.sh -q
```

Requiere Ubuntu/WSL, Python 3.12 y uv; la instalación inicial necesita acceso a
los índices de paquetes. Las dependencias quedan en `.venv`, fijadas mediante
`requirements.lock`. La versión CPU de PyTorch procede de su índice oficial.
No se instala software global ni se requiere HFST.

`prepare` conserva las fuentes y congela registros, vocabularios y particiones.
Rechaza cambios silenciosos en las fuentes o el dataset. Para otro experimento
hay que versionar esos artefactos; no reutilizar la prueba observada para ajustar
hiperparámetros. Una repetición idéntica de `train` reemplaza los checkpoints del
piloto; conservar una copia de `runs` y `reports` si se necesitan ejecuciones históricas.

## Datos y arquitectura

Se importan 317 formas de palabras.json y contextos de 135 oraciones. Las cuatro
expresiones con espacios se excluyen. No se crean análisis a partir de traducciones
del diccionario; sus 1384 registros quedan inventariados para ampliaciones revisadas.
Los ocho tokens adicionales de oraciones no tienen análisis para entrenamiento.
Todas las etiquetas mantienen `documented_unreviewed`, y las 55 segmentaciones
sufijales conservan estado de hipótesis. Los rasgos gramaticales permanecen vacíos.

El encoder GRU y decoder GRUCell con atención tienen 134016 parámetros, embedding
48 y estado 96. La salida serializa lema, categoría, segmentos y rasgos vacíos.
La entrada tiene hasta 32 caracteres y la decodificación hasta 80 símbolos; nunca
se truncan entradas silenciosamente. Los vocabularios usan caracteres únicamente
del entrenamiento. Las familias se mantienen completas en una sola partición:
258 formas de entrenamiento, 31 de desarrollo y 28 de prueba.

## Resultado del primer piloto

Se ejecutaron las semillas 17, 29 y 43, con selección y parada temprana por desarrollo.
La seleccionada fue 43, época 45. Solo después se abrió el conjunto de prueba.

| Conjunto | Análisis completos coincidentes | Total |
| --- | ---: | ---: |
| Entrenamiento | 251 (97.29 %) | 258 |
| Desarrollo | 15 (48.39 %) | 31 |
| Prueba por familias | 7 (25 %) | 28 |

Estos porcentajes comparan contra objetivos provisionales, no contra anotaciones
lingüísticas certificadas. En prueba, 12/28 salidas reconstruyen una estructura
válida, 11/28 tienen lema exacto y 12/28 segmentación exacta bajo esa validación.
La referencia que copia la superficie como lema/segmento obtiene 27/28 en esas
métricas; el conjunto reservado contiene principalmente formas base. El modelo
no demuestra una mejora frente a esa referencia. El diccionario completo tiene
acceso a todas las formas y su cobertura se informa aparte, sin confundirla con
generalización. No se midió aprendizaje ni diagnóstico educativo con estudiantes.

## Archivos

- `src/uchumataqu_seq2seq/`: preparación, codificación, modelo, entrenamiento,
  evaluación, referencia ortográfica, exportación, validación y CLI.
- `configs/pilot.json`: arquitectura, límites, semillas y configuración.
- `data/raw/`, `data/prepared/`: fuentes copiadas y dataset congelado.
- `runs/seed-*/best.pt`: mejor checkpoint de cada semilla e historial.
- `runs/selected.pt`: checkpoint seleccionado con desarrollo.
- `runs/export-smoke/`: prueba ONNX anterior al entrenamiento.
- `reports/experiment.json`: métricas, tiempos y comparación de referencias.
- `reports/test-predictions.json`: predicciones y errores de prueba.
- `export/pln-seq2seq-v1/`: encoder, decoder, vocabularios, límites, léxico,
  métricas, vectores, manifiesto, licencias y hashes.

## Exportación y límites

El contrato usa lote fijo 1 y entrada de longitud 32, con máscara. El decoder
exporta un paso; el bucle greedy queda en el runtime. El manifiesto registra tipos,
formas, nombres, opset, semillas y hashes. Se comprueban los tensores del encoder
y el primer paso del decoder, además de las secuencias completas, entre PyTorch
y ONNX Runtime para las entradas admitidas del corpus.

No se ha verificado Sentis, Unity ni Android. La exportación externa no certifica
compatibilidad móvil. `deployment_allowed=false` hasta contar con evidencia
lingüística, utilidad educativa y validación de integración. La ficha del modelo
explica las limitaciones en `resources/model_card.md`.

Referencias de implementación: [exportación ONNX de PyTorch](https://docs.pytorch.org/docs/2.14/onnx.html),
[GRUCell](https://docs.pytorch.org/docs/2.14/generated/torch.nn.GRUCell.html) y
[API de ONNX Runtime](https://onnxruntime.ai/docs/api/python/api_summary.html).
