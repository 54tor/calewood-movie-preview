# AGENTS

## Mission

Construire un outil exécutable dans une image Docker qui :

1. interroge une API tracker privée nommée ici `CALEWOOD_API`,
2. récupère les torrents via `/api/archive/list?status=my-archives`, `/api/upload/list?status=my-uploads` et `/api/upload/list?status=my-uploading`,
3. ignore tout torrent dont le commentaire contient déjà suffisamment de previews imgbb (`>=9` liens),
4. retrouve le torrent correspondant dans qBittorrent via un hash de correspondance,
5. localise les fichiers vidéo sur disque (exclusion des fichiers `Bonus`),
6. génère un nombre de captures multiple de `3` (max `27`) selon l'algorithme défini,
7. envoie ces images vers `IMGBB_API` (avec `album_id` si configuré),
8. publie les URLs en commentaire sur le torrent concerné en les préfixant au commentaire existant.

Le projet doit rester anonyme à 100%.

## Règles d'anonymisation

Le dépôt ne doit contenir aucun nom réel, aucun nom de tracker privé, aucune URL réelle, aucun hash réel, aucun token, aucune IP, aucun chemin personnel, aucune capture réelle, aucun exemple provenant d'un environnement de production.

Utiliser uniquement des noms génériques :

- `CALEWOOD_API`
- `CALEWOOD_API_BASE_URL`
- `CALEWOOD_API_TOKEN`
- `QBITTORRENT_BASE_URL`
- `QBITTORRENT_USERNAME`
- `QBITTORRENT_PASSWORD`
- `IMGBB_API_KEY`
- `IMGBB_ALBUM_ID`
- `HASH_FIELD_NAME`

Interdictions :

- ne pas hardcoder de domaines,
- ne pas committer de `.env` réel,
- ne pas logguer de secrets,
- ne pas afficher les commentaires complets si cela peut exposer du contenu sensible,
- ne pas inclure de dumps API réels dans les tests,
- ne pas écrire le nom du tracker d'origine dans le code, la doc ou les logs.

## Résultat attendu

Le dépôt final doit fournir :

1. une image Docker autonome,
2. une configuration par variables d'environnement,
3. un mode `dry-run` activé par défaut,
4. des logs structurés et redacts,
5. des tests unitaires sur la logique critique,
6. une documentation minimale pour lancer l'outil dans Docker.

Le projet peut utiliser un point d'entrée Python interne au conteneur, mais il ne faut pas concevoir ni documenter le livrable comme une CLI utilisateur séparée.

## Mode forcé

Un mode forcé doit exister pour cibler un torrent unique :

- `--force-id` : identifiant CALEWOOD
- `--force-hash` : hash qBittorrent

Les deux paramètres sont obligatoires et doivent être fournis ensemble.
En mode forcé, la logique de filtrage sur les statuts ne doit pas empêcher le traitement.

## Workflow fonctionnel

Pour chaque exécution :

1. récupérer les torrents via `/api/archive/list?status=my-archives`, `/api/upload/list?status=my-uploads` et `/api/upload/list?status=my-uploading`,
2. filtrer sur la catégorie configurée,
3. charger le commentaire du torrent,
4. détecter les liens `imgbb` existants,
5. si le commentaire contient `1` à `8` liens imgbb, logguer `partial_imgbb_links_warning` puis skip,
6. si le commentaire contient `>=9` liens imgbb, skip,
7. récupérer le hash de correspondance côté tracker,
8. se connecter à qBittorrent Web API,
9. retrouver le torrent qBittorrent correspondant à ce hash,
10. déterminer les fichiers vidéo éligibles,
11. calculer la durée totale,
12. extraire les captures selon l'algorithme multiple de `3`,
13. uploader les captures sur `IMGBB_API`,
14. poster un commentaire avec les URLs en préfixant l'ancien commentaire,
15. journaliser le résultat.

## Correspondance avec qBittorrent

Le hash utilisé pour retrouver le torrent doit provenir d'un champ configurable de la réponse tracker :

- par défaut : `HASH_FIELD_NAME`,
- ce champ doit être configurable car le schéma exact de `CALEWOOD_API` peut varier,
- si le hash est absent, journaliser `missing_source_hash` et passer au torrent suivant.

Comparer les hashes de manière insensible à la casse.

Ordre de recherche du hash :

1. `sharewood_hash`
2. `lacale_hash` (fallback)

## Résolution du fichier vidéo

Lors de la lecture des torrents depuis qBittorrent, seuls les torrents complétés à `100%` doivent être considérés.

Règle :

- si le torrent qBittorrent correspondant n'est pas complété à `100%`, il doit être ignoré,
- ce filtre s'applique avant toute lecture de fichiers,
- dans ce cas, journaliser un skip explicite et ne pas tenter de capture.

Cas à gérer :

- ne conserver que les fichiers vidéo,
- exclure les fichiers dont le nom contient `Bonus` (insensible à la casse),
- si aucun fichier vidéo n'est trouvé, considérer cela comme une erreur.

Extensions vidéo à supporter au minimum :

- `.mkv`
- `.mp4`
- `.avi`
- `.mov`
- `.m4v`
- `.ts`

Le parcours du dossier peut se faire soit à partir des fichiers exposés par qBittorrent, soit par inspection locale du répertoire contenu, mais il faut privilégier les métadonnées qBittorrent si elles sont suffisantes.

## Génération des captures

Utiliser `ffprobe` pour obtenir la durée et `ffmpeg` pour extraire les frames.

Contraintes :

- le nombre total de captures doit être un multiple de `3`,
- maximum `27` captures,
- ignorer `0%` et `100%`,
- nommage temporaire déterministe,
- nettoyage systématique des fichiers temporaires,
- format image : `jpg` ou `png`, configurable, avec `jpg` par défaut,
- qualité raisonnable pour limiter la taille d'upload.

Algorithme de répartition :

- `1` vidéo : `9` captures réparties sur la durée,
- `2` vidéos : `9` captures par vidéo (total `18`),
- `3` vidéos : `6` captures par vidéo (total `18`),
- `>3` vidéos : sélectionner `18` vidéos aléatoirement (tirage déterministe par hash) et capturer 1 image au milieu de chaque vidéo.

Exigences techniques :

- ne pas capturer à partir d'une durée nulle,
- vérifier que le fichier existe avant extraction,
- échouer proprement si `ffprobe` ou `ffmpeg` ne sont pas disponibles,
- encapsuler les appels système avec timeout.
- prévoir un fallback ffmpeg (seek avant/après `-i`, flags tolérants corruption),
- accepter une capture si le fichier image est produit, même si `ffmpeg` retourne non-zéro.

## Upload vers imgbb

L'upload se fait par requête HTTP à `IMGBB_API`.

Contraintes :

- uploader chaque image individuellement,
- récupérer l'URL publique finale de chaque image,
- conserver l'ordre des timestamps dans le commentaire final,
- si un upload échoue, ne pas poster de commentaire partiel,
- en cas d'échec partiel, journaliser et passer au torrent suivant.

Si `IMGBB_ALBUM_ID` est défini, il doit être passé à l'API.

## Publication du commentaire

Le commentaire publié sur le torrent doit contenir les URLs, une par ligne, puis le commentaire existant :

```text
https://...
https://...
https://...
...

<commentaire existant>
```

Le commentaire publié doit préfixer les nouvelles URLs au commentaire existant, sans ajouter d'autre texte.

## Idempotence

Le job doit être idempotent.

Règles :

- si le commentaire contient `>=9` liens `imgbb`, ne rien republier,
- si le commentaire contient `1` à `8` liens `imgbb`, émettre `partial_imgbb_links_warning` puis ne rien republier,
- si une exécution précédente a produit des captures mais n'a pas posté de commentaire, les fichiers temporaires ne doivent pas être réutilisés implicitement,
- dans ce cas, émettre un log exploitable pour réparation manuelle,
- l'outil peut être relancé sans duplication de commentaires.

Le log de réparation manuelle doit contenir au minimum :

- l'identifiant du torrent côté `CALEWOOD_API`,
- le hash de correspondance,
- le chemin vidéo retenu si connu,
- le répertoire temporaire concerné si connu,
- la raison du non-post,
- le nombre d'images générées si disponible,
- le nombre d'uploads réussis si disponible.

## Gestion des erreurs

Chaque torrent doit être traité isolément. Un échec unitaire ne doit pas interrompre toute l'exécution.

Catégories d'erreur minimales :

- `calewood_api_error`
- `comment_fetch_error`
- `already_has_imgbb`
- `partial_imgbb_links_warning`
- `missing_source_hash`
- `qb_auth_error`
- `qb_torrent_not_found`
- `video_not_found`
- `ffprobe_error`
- `ffmpeg_error`
- `imgbb_upload_error`
- `comment_post_error`

Le code de sortie global doit être non nul si au moins une erreur technique bloquante survient pendant le run, même si certains torrents ont été traités avec succès.

La sélection d'un sous-ensemble aléatoire de vidéos pour `>3` fichiers ne doit pas être considérée comme une erreur.

`partial_imgbb_links_warning` est aussi un warning léger :

- si le commentaire contient au moins un lien `imgbb` mais moins de `9` liens détectables,
- journaliser le nombre de liens trouvés,
- ne pas republier automatiquement,
- laisser le torrent en skip pour éviter toute duplication incohérente,
- ne pas rendre le code de sortie global non nul à elle seule.

## Architecture recommandée

Langage recommandé : Python 3.12.

Structure suggérée :

```text
.
├── AGENTS.md
├── Dockerfile
├── README.md
├── pyproject.toml
├── src/
│   └── calewood_movie_preview/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── logging.py
│       ├── calewood_api.py
│       ├── qbittorrent.py
│       ├── media.py
│       ├── imgbb.py
│       ├── workflow.py
│       └── models.py
└── tests/
    ├── test_comment_parsing.py
    ├── test_video_selection.py
    ├── test_capture_timestamps.py
    └── test_workflow.py
```

## Dépendances recommandées

- `httpx` pour les appels HTTP,
- `qbittorrent-api` comme package Python officiel pour qBittorrent,
- `pydantic` ou `pydantic-settings` pour la config,
- `tenacity` pour les retries ciblés,
- `structlog` ou `logging` JSON pour les logs,
- `pytest` pour les tests.

Ne pas ajouter de dépendance lourde sans nécessité.

Contrainte spécifique :

- l'intégration qBittorrent doit utiliser le package Python officiel `qbittorrent-api`,
- ne pas réimplémenter le client qBittorrent en HTTP brut sauf impossibilité technique documentée.

## Contrat de configuration

Variables d'environnement minimales :

- `CALEWOOD_API_BASE_URL`
- `CALEWOOD_API_TOKEN`
- `CALEWOOD_API_TIMEOUT_SECONDS`
- `CALEWOOD_API_VERIFY_TLS`
- `CALEWOOD_API_CATEGORY`
- `CALEWOOD_API_SINGLE_ID`
- `HASH_FIELD_NAME`
- `QBITTORRENT_BASE_URL`
- `QBITTORRENT_USERNAME`
- `QBITTORRENT_PASSWORD`
- `QBITTORRENT_TIMEOUT_SECONDS`
- `QBITTORRENT_VERIFY_TLS`
- `IMGBB_API_KEY`
- `IMGBB_ALBUM_ID`
- `IMGBB_TIMEOUT_SECONDS`
- `IMAGE_FORMAT`
- `DRY_RUN`
- `LOG_LEVEL`
- `TEMP_DIR`

Optionnelles :

- `REQUESTS_RETRY_COUNT`
- `FFMPEG_BIN`
- `FFPROBE_BIN`

Valeurs par défaut attendues :

- `CALEWOOD_API_BASE_URL=https://calewood.n0flow.io/api`
- `CALEWOOD_API_CATEGORY=XXX`
- `CALEWOOD_API_SINGLE_ID` vide par défaut, utile pour un test ciblé,
- `CALEWOOD_API_PER_PAGE=200`
- `IMGBB_ALBUM_ID=ymNBDj`

## Comportement `dry-run`

En `dry-run` :

- l'outil peut lire `CALEWOOD_API`,
- l'outil peut lire qBittorrent,
- l'outil peut calculer les captures,
- l'outil ne doit pas uploader sur imgbb,
- l'outil ne doit pas poster de commentaire,
- il doit journaliser précisément ce qu'il aurait fait.

`DRY_RUN` doit être à `true` par défaut.

Le comportement par défaut du projet doit donc être non destructif :

- aucune publication sur imgbb,
- aucune modification des commentaires côté `CALEWOOD_API`,
- aucune action d'écriture distante tant qu'un opérateur n'a pas explicitement désactivé `dry-run`.

La désactivation de `dry-run` doit se faire explicitement via l'alias `--just-do-it`.

Règles :

- sans `--just-do-it`, le conteneur reste en `dry-run`,
- avec `--just-do-it`, le conteneur est autorisé à uploader sur imgbb et à poster les commentaires,
- si `DRY_RUN` et `--just-do-it` sont tous deux fournis, `--just-do-it` a priorité pour forcer le mode actif,
- la documentation doit présenter `--just-do-it` comme un opt-in explicite à comportement destructif.

## Docker

L'image Docker doit :

- cibler explicitement la plateforme `linux/amd64`,
- embarquer `ffmpeg` et `ffprobe`,
- tourner en utilisateur non root,
- être la plus minimale possible,
- ne pas embarquer de secrets,
- supporter le montage d'un volume contenant les données médias,
- supporter un réseau permettant l'accès à `CALEWOOD_API`, qBittorrent et imgbb,
- définir un `ENTRYPOINT` vers le point d'entrée interne du conteneur.

Le conteneur doit supposer que les chemins remontés par qBittorrent sont visibles depuis le conteneur via un montage cohérent. Prévoir une option de remapping de chemin si nécessaire :

- `PATH_MAP_SOURCE`
- `PATH_MAP_TARGET`

Exemple :

- cas recommandé : qBittorrent retourne `/data/media/releases/movie.mkv` et le conteneur voit exactement `/data/media/releases/movie.mkv`
- cas toléré avec remapping : qBittorrent retourne `<SOURCE_PATH_PREFIX>/releases/movie.mkv` et le conteneur voit `<TARGET_PATH_PREFIX>/releases/movie.mkv`

Contrainte importante :

- le montage Docker doit viser en priorité le répertoire de téléchargement qBittorrent,
- le chemin côté conteneur doit idéalement être identique à celui exposé par qBittorrent,
- le remapping `PATH_MAP_SOURCE` / `PATH_MAP_TARGET` ne doit être utilisé qu'en solution de repli.

Exigences de build :

- le `Dockerfile` doit être compatible avec `docker build --platform linux/amd64`,
- si une image de base multi-arch est utilisée, documenter que la cible supportée par le projet reste `amd64`,
- ne pas supposer un hôte `arm64`,
- si des binaires système sont installés, ils doivent provenir de dépôts compatibles `amd64`.

## Sécurité et confidentialité

Mesures obligatoires :

- redaction des secrets dans les logs,
- pas de verbose HTTP avec headers sensibles,
- validation stricte des variables d'environnement au démarrage,
- message d'erreur explicite mais non sensible,
- nettoyage des artefacts temporaires, même sur erreur,
- aucun appel externe autre que `CALEWOOD_API`, qBittorrent et imgbb.

## Détection des liens imgbb

La détection doit être tolérante et basée sur regex.

Détecter au minimum :

- `imgbb.com`
- `i.ibb.co`

Si l'un de ces domaines apparaît dans le commentaire, considérer le torrent comme déjà illustré.

Le parser doit aussi compter le nombre de liens `imgbb` détectés :

- si `0`, le torrent reste éligible,
- si `1` à `8`, lever `partial_imgbb_links_warning` puis ignorer le torrent,
- si `9` ou plus, considérer le torrent comme déjà illustré puis ignorer le torrent.

## Tests minimums à écrire

1. détection de lien imgbb dans un commentaire,
2. warning si le commentaire contient entre `1` et `8` liens imgbb,
3. calcul exact des timestamps pour 9 captures,
4. exclusion des fichiers `Bonus`,
5. répartition 2 vidéos = 18 captures (9 par vidéo),
6. répartition 3 vidéos = 18 captures (6 par vidéo),
7. sélection déterministe de 18 vidéos quand il y en a plus de 3,
8. erreur quand aucun hash tracker n'est présent,
9. `dry-run` ne poste rien,
10. pas de commentaire posté si un seul upload échoue,
11. émission d'un log de réparation manuelle si des captures ou uploads partiels existent sans commentaire final.

## Critères d'acceptation

Le travail est acceptable si :

1. le projet se build avec `docker build`,
2. le conteneur démarre et valide sa configuration,
3. le workflow complet est découpé en modules testables,
4. les secrets sont exclusivement injectés par environnement,
5. le nombre de captures est un multiple de `3` et ne dépasse pas `27`,
6. aucun commentaire n'est posté s'il existe déjà un lien imgbb,
7. aucun commentaire partiel n'est posté,
8. la doc et le code restent totalement anonymes.

## Plan d'implémentation demandé aux agents

Ordre de travail :

1. scaffolder le projet Python et le point d'entrée du conteneur,
2. implémenter la configuration et les logs redacts,
3. implémenter le client `CALEWOOD_API`,
4. implémenter le client qBittorrent avec `qbittorrent-api`,
5. implémenter la logique de sélection du fichier vidéo,
6. implémenter `ffprobe` et `ffmpeg`,
7. implémenter le client imgbb,
8. implémenter l'orchestrateur principal,
9. écrire les tests,
10. écrire `Dockerfile` et `README.md`,
11. vérifier que rien dans le dépôt ne casse l'anonymisation.

## Interdictions pour les agents

- ne pas inventer des endpoints finaux sans les isoler derrière des placeholders configurables,
- ne pas utiliser de SDK non nécessaire si une API HTTP simple suffit,
- ne pas contourner la règle des captures multiples de `3`,
- ne pas poster de commentaire si les URLs ne sont pas toutes disponibles,
- ne pas modifier le comportement demandé sur le cas des multiples fichiers,
- ne pas stocker de cache persistant par défaut,
- ne pas introduire de télémétrie.

## Remarques

S'il manque des détails exacts sur `CALEWOOD_API`, les agents doivent :

1. garder une interface client propre et adaptable,
2. centraliser le mapping de schéma dans `calewood_api.py`,
3. documenter clairement les hypothèses dans `README.md`,
4. ne jamais remplacer des inconnues par des valeurs réelles ou identifiantes.
