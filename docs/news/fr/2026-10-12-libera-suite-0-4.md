---
date: 2026-10-12
description: Libera Suite 0.4 signale un document déjà ouvert ailleurs, par Libera Suite ou par LibreOffice, restitue plus fidèlement les fichiers OpenDocument, et ajoute le glisser-déposer, un dictionnaire personnel et la conversion en ligne de commande.
---

# Libera Suite 0.4 : plus sûre en dossier partagé, plus fidèle à OpenDocument

Libera Suite 0.4 est disponible. Elle protège un document ouvert par quelqu'un d'autre, dans Libera Suite comme dans LibreOffice. Ses éditeurs lisent et écrivent plus exactement les formats OpenDocument.

[Mettre à jour Libera Suite](../main/install.md#update){ .md-button .md-button--primary }

Relancez l'installeur ou la commande d'installation, ou `brew upgrade libera`, après avoir quitté Libera Suite. Cette version installe de nouveaux éditeurs, un téléchargement unique d'environ 100 Mo.

## Le verrouillage des documents

Jusqu'ici, rien n'empêchait deux fenêtres de modifier le même document : la dernière à enregistrer écrasait le travail de l'autre. La bêta le mentionnait parmi ses limites. La 0.4 la supprime entre deux fenêtres de Libera Suite comme entre Libera Suite et LibreOffice. Microsoft Office ne voit pas encore ces verrous : un document ouvert dans Word reste exposé.

- **Libera Suite pose un verrou au format de LibreOffice.** À l'ouverture d'un document, elle crée à côté de lui le petit fichier de verrou que LibreOffice utilise. Elle tient compte aussi des verrous posés par LibreOffice. Un document déjà ouvert ailleurs s'ouvre en mode *locked for editing* : vous pouvez le lire et le modifier, mais l'enregistrement vous demande un autre emplacement. L'original reste intact.
- **Rouvrir un document déjà ouvert dans Libera Suite ramène sa fenêtre au premier plan**, sans en ouvrir une seconde.
- **Une fenêtre signale les modifications non enregistrées** : un point dans le bouton de fermeture sur macOS, un `*` devant le titre sous Linux et Windows.

## Une meilleure fidélité aux formats OpenDocument

Les éditeurs de la 0.4 intègrent **68 corrections pour les formats OpenDocument** (`.odt`, `.ods`, `.odp`), chacune repérée sur les documents de test de LibreOffice. Deux défauts du format CSV disparaissent aussi. Un emoji empêchait d'enregistrer un CSV ; un grand CSV perdait un caractère sur 500 000 à la lecture.

## L'annonce des nouvelles versions

Nouveauté de la 0.4 : une fois par jour au plus, Libera Suite lit sur notre serveur de téléchargement le numéro de la dernière version. S'il est plus récent que le vôtre, elle vous le signale une fois, avec la marche à suivre pour votre mode d'installation. Elle ne télécharge rien et n'envoie aucune information sur vous ni sur vos documents ; hors ligne, elle ne fait rien. La ligne `check_updates = false` dans le [fichier de configuration](../guide/documents.md#your-name-in-documents) la désactive.

## Les autres nouveautés

- **Le glisser-déposer.** Un document déposé sur une fenêtre s'ouvre ; une image déposée sur un document s'y insère.
- **Le dictionnaire personnel.** Un mot ajouté par *Add to dictionary* est conservé, pour tous les documents et toutes les langues.
- **Votre nom dans les modifications suivies et les commentaires**, réglable par `user_name` dans le fichier de configuration.
- **Ctrl-N, Ctrl-O et Ctrl-W** sous Linux et Windows.
- **L'impression** demande où enregistrer le PDF, en proposant le dossier du document.
- **La conversion en ligne de commande** : `libera --convert *.docx -t pdf` écrit un PDF à côté de chaque document, sans ouvrir de fenêtre.
- **La fenêtre About** affiche la version installée, première information à donner dans un signalement de bogue.

Les limites restantes, dont l'absence d'onglets et un installeur Windows encore non signé, sont détaillées sur [la page d'état](../main/status.md).

## Signalez-nous les problèmes

Le signalement le plus utile reste un document mal rendu, joint au message. La page [Vos retours](../feedback.md) indique comment nous écrire.

*Abilian*
