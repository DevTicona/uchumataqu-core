# Seq2Seq uchumataqu: piloto experimental v1

Tarea: superficie de una palabra → lema, categoría heredada de la entrada,
segmentación propuesta y campo de rasgos vacío. La red no genera traducciones
ni mensajes educativos, no corrige respuestas y no recibe el objetivo del ejercicio.

Arquitectura: encoder GRU unidireccional, embedding de 48, estado de 96;
decoder GRUCell con atención multiplicativa. Entrada por caracteres, salida por
caracteres más marcadores de campos y categorías. PAD se ignora en la pérdida.
La máscara excluye padding de la atención; el estado inicial del decoder se toma
en el último carácter real. Inferencia greedy acotada a 80 símbolos.

Datos: 317 formas de palabras.json y contextos de las 135 oraciones. Cuatro
expresiones con espacios quedan fuera. Las 55 segmentaciones sufijales son
hipótesis de concatenación de formas relacionadas, no etiquetas validadas.
Los ocho tokens adicionales de oraciones no tienen análisis fiable para supervisar
la red. Los 1384 registros del diccionario se inventariaron como reserva; no se
generan etiquetas morfológicas a partir de traducciones. No hay datos sintéticos.

Los originales no se modifican. Cada registro conserva procedencia y estado
documented_unreviewed. Las particiones por familia y vocabularios se congelan
en data/prepared/dataset.json. Solo entrenamiento aporta caracteres al vocabulario;
caracteres no soportados ocasionan abstención. No se elimina ningún caso difícil
del denominador de evaluación.

Entrenamiento exploratorio: tres semillas, Adam, clipping de gradiente, selección
por análisis exacto y luego lema en desarrollo, parada temprana. La prueba se abre
tras esa selección. metrics.json contiene todos los resultados y denominadores.
Son coincidencias con objetivos provisionales, no precisión lingüística validada.
No se calcula F1 de rasgos vacíos ni se afirma mejora educativa.

Referencias de comparación: diccionario de entrenamiento, copia de superficie como
lema/segmento y categoría mayoritaria. La cobertura del diccionario completo se
reporta aparte porque conoce las formas de prueba. La función ortográfica de
Levenshtein conserva palabras exactas y todos los candidatos empatados; no usa el
objetivo del ejercicio para elegir ni aporta morfología.

Exportación: encoder.onnx y decoder_step.onnx, opset 17, lote fijo 1 y entrada
rellenada a 32 caracteres. El bucle greedy queda fuera del grafo. Los nombres,
formas y tipos están en manifest.json. PAD/UNK/BOS se excluyen de la selección;
EOS termina la secuencia. Una salida sin EOS o con reconstrucción incorrecta se
rechaza. Se comprueban tensores y secuencias completas contra ONNX Runtime CPU.

El validador compara una hipótesis con evidencia exacta del léxico y se abstiene
cuando no coincide. Una coincidencia recibe experimental_match: sigue sin ser
una explicación acreditada porque sus fuentes no están revisadas. El léxico de
validación no reescribe la predicción; esta permanece visible por separado.

No probado en Sentis, Unity ni Android. No se completó la comprobación móvil
temprana de la guía; por ello este es un piloto externo y deployment_allowed=false.
No sustituye al modelo HFST ni a la evaluación educativa existente. Se necesitan
anotaciones revisadas, evaluación de diagnóstico y pruebas móviles antes de decidir
si resulta útil desplegarlo.
