# Sviluppatori

Libera Suite è un host scritto in Python attorno agli editor di Euro-Office. Gli editor fanno la parte difficile: leggere un `.docx`, un `.xlsx` o un `.pptx` e impaginarlo come lo vedeva chi lo ha scritto. L'host porta tutto il resto di un'applicazione desktop: le finestre, i menu, le finestre di dialogo dei file, la conversione dei formati e il confezionamento. Tutto il resto viene dal progetto originale, invariato.

Il lavoro vero sta quindi nei punti di giunzione: cosa l'editor si aspetta dal suo host, come viene costruito il *payload* — gli editor e i binari nativi — e come le nostre modifiche al progetto originale sono tenute come una serie di patch leggibile.

## In sei diapositive

<div class="deck" data-pdf="/en/pdf/Libera%20Suite%20for%20developers.pdf"><a href="/en/pdf/Libera%20Suite%20for%20developers.pdf">Libera Suite for developers, in sei diapositive (PDF)</a></div>

## I dettagli, in inglese

La documentazione tecnica segue il codice da vicino ed esiste solo in inglese: l'architettura, la costruzione del payload, la serie di patch, la procedura per pubblicare una versione e la roadmap.

[Developers](/en/develop/), in inglese, è il punto di partenza.
