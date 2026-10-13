---
date: 2026-10-12
description: Libera Suite 0.4 verrouille les documents ouverts, avec les verrous de LibreOffice, corrige 68 défauts de lecture et d'écriture des fichiers OpenDocument, et ajoute le glisser-déposer, un dictionnaire personnel et la conversion en ligne de commande.
---

# Libera Suite 0.4 : verrouillage des documents et fidélité à OpenDocument

Libera Suite 0.4 est disponible. Elle protège un document déjà ouvert ailleurs, dans Libera Suite comme dans LibreOffice. Elle lit et écrit aussi plus exactement les documents OpenDocument.

[Mettre à jour Libera Suite](../main/install.md#update){ .md-button .md-button--primary }

Pour mettre à jour, quittez Libera Suite, puis relancez l'installateur ou la commande d'installation, ou `brew upgrade libera`. Cette version s'accompagne d'une nouvelle version des composants d'Euro-Office, téléchargée une seule fois (environ 100 Mo).

## Le verrouillage des documents

Jusqu'ici, deux fenêtres pouvaient modifier le même document : la dernière à enregistrer écrasait le travail de l'autre. La 0.4 l'empêche entre deux fenêtres de Libera Suite comme entre Libera Suite et LibreOffice. Microsoft Office ne voit pas encore ces verrous : un document ouvert dans Word reste exposé.

- **Libera Suite pose un verrou au format de LibreOffice.** À l'ouverture d'un document, elle crée à côté de lui le petit fichier de verrou de LibreOffice. Elle tient compte aussi des verrous posés par LibreOffice. Un document déjà ouvert ailleurs s'ouvre en mode *locked for editing* : vous pouvez le lire et le modifier, mais l'enregistrement demande un autre emplacement. L'original reste intact.
- **Rouvrir un document déjà ouvert dans Libera Suite ramène sa fenêtre au premier plan**, sans en ouvrir une seconde.
- **Une fenêtre signale les modifications non enregistrées** : un point dans le bouton de fermeture sous macOS, un `*` devant le titre sous Linux et Windows.

## La fidélité aux formats OpenDocument

La 0.4 corrige **68 défauts du convertisseur** dans la lecture et l'écriture des fichiers OpenDocument (`.odt`, `.ods`, `.odp`), repérés grâce aux fichiers de test de LibreOffice. Elle corrige aussi deux défauts du format CSV : un emoji empêchait d'enregistrer un fichier CSV ; la lecture d'un grand fichier CSV perdait un caractère sur 500 000.

## L'annonce des nouvelles versions

Une fois par jour au plus, Libera Suite lit sur notre serveur de téléchargement le numéro de la dernière version. S'il est plus récent que le vôtre, elle vous le signale une fois, avec la marche à suivre pour votre mode d'installation. Elle ne télécharge rien et n'envoie aucune information sur vous ni sur vos documents ; hors ligne, elle ne fait rien. La ligne `check_updates = false` du [fichier de configuration](../guide/documents.md#your-name-in-documents) désactive cette vérification.

## Les autres nouveautés

- **Le glisser-déposer.** Un document déposé sur une fenêtre s'ouvre ; une image déposée sur un document s'y insère.
- **Le dictionnaire personnel.** Un mot ajouté par *Add to dictionary* est conservé pour tous les documents et toutes les langues.
- **Votre nom dans les modifications suivies et les commentaires**, réglable par `user_name` dans le fichier de configuration.
- **Ctrl-N, Ctrl-O et Ctrl-W** sous Linux et Windows.
- **L'impression** demande où enregistrer le PDF et propose le dossier du document.
- **La conversion en ligne de commande** : `libera --convert *.docx -t pdf` écrit un PDF à côté de chaque document, sans ouvrir de fenêtre.
- **La fenêtre About** affiche la version installée, à indiquer dans tout signalement de bogue.

Les autres limites, dont l'absence d'onglets et l'installateur Windows non signé, figurent sur la page [État des lieux](../main/status.md).

## Vos retours

Le retour le plus utile reste un document qui s'affiche mal, joint à votre message avec la sortie de `libera --diagnose`. La page [Vos retours](../feedback.md) explique comment nous écrire.

*Abilian*
