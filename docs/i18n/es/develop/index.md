# Desarrolladores

Libera Suite es un host escrito en Python alrededor de los editores de Euro-Office. Los editores hacen la parte difícil: leer un `.docx`, un `.xlsx` o un `.pptx` y maquetarlo tal como lo veía quien lo escribió. El host aporta todo lo demás de una aplicación de escritorio: las ventanas, los menús, los diálogos de archivos, la conversión de formatos y el empaquetado. Todo lo demás viene del proyecto original, sin cambios.

El trabajo de verdad está, por tanto, en los puntos de unión: qué espera el editor de su host, cómo se construye el *payload* —los editores y los binarios nativos— y cómo nuestras modificaciones del proyecto original se mantienen como una serie de parches legible.

## En seis diapositivas

<div class="deck" data-pdf="/en/pdf/Libera%20Suite%20for%20developers.pdf"><a href="/en/pdf/Libera%20Suite%20for%20developers.pdf">Libera Suite for developers, en seis diapositivas (PDF)</a></div>

## Los detalles, en inglés

La documentación técnica sigue el código de cerca y solo existe en inglés: la arquitectura, la construcción del payload, la serie de parches, el procedimiento para publicar una versión y la hoja de ruta.

[Developers](/en/develop/), en inglés, es el punto de partida.
