# CALEWOOD_API Mapping

Ce document stabilise les endpoints utiles au projet dans un contrat local maintenu manuellement.

Objectif :

- fournir un contrat lisible et versionnable,
- faciliter les mises à jour futures sans réécrire la logique métier.

## Principe De Maintenance

Le code applicatif ne doit pas dépendre d'une documentation externe.

Le workflow recommandé est :

1. on maintient ce fichier de mapping manuellement,
2. le client `CALEWOOD_API` s'appuie sur ce mapping et sur des adaptateurs de schéma centralisés,
3. si l'API change, on modifie ce fichier plutôt que d'éparpiller les changements dans le code.

## Endpoints Utiles Au Projet

### Liste Des Torrents

`GET /api/archive/pre-archivage/list`

Usage retenu :

- endpoint principal pour récupérer les torrents en pré-archivage,
- sans filtre : expose les torrents disponibles,
- avec `status=my-pre-archiving` : retourne les torrents déjà en cours de pré-archivage.

Filtres documentés :

- `status`
- `p`
- `per_page`
- `q`
- `cat`
- `subcat`
- `seeders`
- `min_size`
- `max_size`

États explicitement mentionnés dans la doc :

- `selected`
- `pre_archiving`
- `awaiting_fiche`
- `post_archiving`

Interprétation pour ce projet :

- la chaîne de pré-archivage est l'entrée la plus pertinente identifiée dans la documentation locale,
- si un endpoint plus précis pour les états métier finaux du projet est confirmé plus tard, seul `calewood_api.py` devra être ajusté.

### Liste Des Torrents Archivés

`GET /api/archive/list`

Usage retenu :

- endpoint pertinent pour récupérer les torrents déjà archivés,
- utile pour couvrir explicitement le périmètre `archived`,
- utile aussi pour les vues orientées `mine` lorsque l'API renvoie les archives de l'opérateur courant.

Filtres documentés :

- `status`
- `uploader`
- `p`
- `per_page`
- `q`
- `cat`
- `subcat`
- `seeders`
- `min_size`
- `max_size`

Valeurs de statut observées dans la doc :

- `my-archiving`
- `my-archives`

Interprétation pour ce projet :

- `my-archives` doit être considéré comme pertinent pour le cas `archived mine`,
- `archive/list` est le candidat principal pour la lecture des torrents déjà archivés,
- `calewood_api.py` devra supporter à la fois la vue pré-archivage et la vue archivage classique selon le besoin métier.

### Lecture D'Un Commentaire Torrent

`GET /api/torrent/comment/{id}`

Usage retenu :

- lire le commentaire courant,
- détecter les liens `imgbb`,
- compter le nombre de liens existants,
- décider du skip ou du warning `partial_imgbb_links_warning`.

### Publication D'Un Commentaire Torrent

`POST /api/torrent/comment/{id}`

Body JSON documenté :

```json
{ "comment": "..." }
```

Usage retenu :

- poster les 9 URLs imgbb, une URL par ligne,
- ne poster qu'en mode actif avec `--just-do-it`,
- ne rien poster si le commentaire contient déjà au moins un lien imgbb.

### Détail D'Un Torrent D'Archivage

`GET /api/archive/get/{id}`

Usage possible :

- compléter les métadonnées d'un torrent,
- récupérer des champs absents de la liste,
- identifier un éventuel champ de hash ou des métadonnées nécessaires au mapping avec qBittorrent.

### Téléchargement Du `.torrent`

`GET /api/archive/pre-archivage/torrent-file/{id}`

Usage possible :

- endpoint de secours si le hash de correspondance n'est pas directement exposé par la liste ou le détail,
- permet de reconstituer des métadonnées à partir du `.torrent` si nécessaire.

Contrainte :

- ne l'utiliser qu'en fallback,
- privilégier d'abord un champ de hash déjà présent dans la réponse API.

## Endpoints Annexes Observés

Non nécessaires au premier périmètre, mais présents dans la doc :

- `GET /api/torrent/list`
- `POST /api/archive/take/{id}`
- `POST /api/archive/complete/{id}`
- `POST /api/archive/revert-done/{id}`
- `POST /api/archive/seedbox-check`
- `POST /api/archive/pre-archivage/take/{id}`
- `POST /api/archive/pre-archivage/dl-done/{id}`
- `POST /api/archive/pre-archivage/confirm/{id}`
- `POST /api/archive/pre-archivage/abandon/{id}`
- `POST /api/archive/pre-archivage/blast/{id}`

## Transitions D'État Observées

D'après le contrat actuellement retenu :

- `selected -> pre_archiving` via `POST /api/archive/pre-archivage/take/{id}`
- `pre_archiving -> awaiting_fiche` via `POST /api/archive/pre-archivage/dl-done/{id}`
- `awaiting_fiche -> post_archiving` côté uploader
- `post_archiving -> done` via `POST /api/archive/pre-archivage/confirm/{id}`
- `archiving -> done` via `POST /api/archive/complete/{id}`

Pour ce projet, cela implique :

- la notion métier utile est la progression d'archivage,
- les noms exacts des états doivent rester configurables si le schéma change.

## Hypothèses À Valider Dans Le Code

Le mapping exact doit être centralisé dans `calewood_api.py` :

- champ identifiant torrent,
- champ commentaire,
- champ statut,
- champ hash de correspondance vers qBittorrent,
- éventuelle pagination,
- éventuelle enveloppe `{ success, data }`.

Tant que ces points ne sont pas garantis, le client doit :

- parser défensivement,
- journaliser les champs manquants,
- éviter toute hypothèse câblée en dur en dehors du module `calewood_api.py`.

## Mise À Jour Future

Si la documentation d'origine change ou n'est plus disponible :

1. conserver ce fichier comme référence stable,
2. comparer le nouveau contrat API à cette liste,
3. mettre à jour seulement ce mapping et le code de `calewood_api.py`,
4. ne pas modifier les autres modules si seul le contrat API change.
