# Alcance de HFST v1

Este paquete es un transductor finito de formas documentadas, con continuaciones
restringidas a las relaciones presentes en palabras.json. No es una gramática
productiva general del uchumataqu ni un corrector neuronal.

Incluye 317 formas del vocabulario principal y 8 tokens adicionales de las 135
oraciones. Las cuatro expresiones de varias palabras se conservan en la auditoría,
fuera del modelo de palabras aisladas. Los ocho tokens adicionales no reciben
traducciones ni categorías inventadas. Ninguno tuvo coincidencia exacta en el
diccionario suplementario, que queda disponible para futuras ampliaciones.

La salida HFST tiene la forma `lema+POS+ID=identificador+SUF=sufijo`.
`analyses.json` resuelve los identificadores a traducciones, fuentes, contextos,
segmentaciones propuestas y estado de revisión. Se preservan análisis alternativos.
Las etiquetas POS reflejan la categoría de la entrada principal, incluso cuando
esa categoría necesita revisión (por ejemplo Chhuñi). No son una reclasificación
gramatical validada de cada forma flexionada.

Las 55 segmentaciones se proponen a partir de relaciones explícitas y concatenación
exacta. Se admiten naka, chay, pini, pini+chay, naka+chay y naka+pini únicamente
en las familias y formas documentadas. El compendio local orienta la interpretación
de chay/pini, pero no acredita automáticamente todos sus usos. El ejemplo naka
de la guía HFST y las parejas del corpus sustentan una hipótesis de plural;
no se convierte esa hipótesis en rasgos validados. Achichay permanece indiviso.

Todos los registros tienen estado documented_unreviewed; la segmentación sufijal
tiene estado hypothesis. `features` permanece vacío. No se inventa singular por
ausencia de naka, ni persona, tiempo, función copulativa o intensificación universal.
Las diferencias entre formas se explican citando sus traducciones documentadas.

Las comprobaciones de cobertura, generación y enumeración son regresiones sobre
el léxico compilado, no una evaluación de generalización, corrección lingüística,
diagnóstico con estudiantes ni mejora de aprendizaje. No hay ejemplos sintéticos
introducidos como evidencia lingüística. Los casos negativos prueban restricciones
del transductor, no demuestran que una palabra sea imposible en la lengua.

La consulta funciona offline en Linux x86_64. No se ha integrado ni probado en
Unity/Android; el paquete no incluye runtime Android. lookup-index.json permite
una futura consulta finita precomputada, que tampoco amplía la cobertura.
