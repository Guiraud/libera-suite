# Développeurs

Libera Suite est un hôte écrit en Python autour des éditeurs d'Euro-Office. Les éditeurs font le travail difficile : lire un `.docx`, un `.xlsx` ou un `.pptx` et le mettre en page tel que son auteur l'a vu. L'hôte apporte le reste d'une application de bureau : les fenêtres, les menus, les dialogues de fichiers, la conversion des formats et l'empaquetage. Le reste vient de l'amont, inchangé.

L'essentiel du travail se situe donc aux points de jonction : les attentes de l'éditeur envers son hôte, la construction du *payload* — les éditeurs et les binaires natifs — et nos modifications de l'amont, conservées sous forme d'une série de correctifs relue.

## En six diapositives

<div class="deck" data-pdf="/en/pdf/Libera%20Suite%20for%20developers.pdf"><a href="/en/pdf/Libera%20Suite%20for%20developers.pdf">Libera Suite pour les développeurs, en six diapositives (PDF)</a></div>

## Le détail, en anglais

La documentation technique suit le code de près et n'existe qu'en anglais : l'architecture, la construction du payload, la série de correctifs, la marche à suivre pour publier une version, et la feuille de route.

[Developers](/en/develop/), en anglais, est le point de départ.
