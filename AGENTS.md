# AGENTS

## Mission

Construire un outil exécutable dans une image Docker qui :

1. interroge une API tracker privée nommée ici `CALEWOOD_API`,
2. récupère les torrents dans l'état `prearchived` ou `archived`,
3. lit le commentaire de chaque torrent,
4. ignore tout torrent dont le commentaire contient déjà au moins un lien `imgbb`,
5. retrouve le torrent correspondant dans qBittorrent via un hash de correspondance,
6. localise le fichier vidéo sur disque,
7. génère 9 captures aux positions `10%`, `20%`, `30%`, `40%`, `50%`, `60%`, `70%`, `80%`, `90%` de la durée totale,
8. envoie ces 9 images vers `IMGBB_API`,
9. publie les 9 URLs en commentaire sur le torrent concerné, une URL par ligne.

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

## Workflow fonctionnel

Pour chaque exécution :

1. récupérer la liste des torrents éligibles depuis `CALEWOOD_API`,
2. filtrer sur les statuts `prearchived` et `archived`,
3. charger le commentaire de chaque torrent,
4. détecter la présence d'au moins un lien `imgbb` dans le commentaire,
5. si un lien `imgbb` existe déjà, marquer le torrent comme `skipped_already_has_preview`,
6. sinon, récupérer le hash de correspondance côté tracker,
7. se connecter à qBittorrent Web API,
8. retrouver le torrent qBittorrent correspondant à ce hash,
9. déterminer le chemin du contenu,
10. identifier le bon fichier vidéo,
11. calculer la durée totale,
12. extraire 9 captures,
13. uploader les captures sur `IMGBB_API`,
14. poster un commentaire avec les 9 URLs, une par ligne,
15. journaliser le résultat.

## Correspondance avec qBittorrent

Le hash utilisé pour retrouver le torrent doit provenir d'un champ configurable de la réponse tracker :

- par défaut : `HASH_FIELD_NAME`,
- ce champ doit être configurable car le schéma exact de `CALEWOOD_API` peut varier,
- si le hash est absent, journaliser `missing_source_hash` et passer au torrent suivant.

Comparer les hashes de manière insensible à la casse.

## Résolution du fichier vidéo

Lors de la lecture des torrents depuis qBittorrent, seuls les torrents complétés à `100%` doivent être considérés.

Règle :

- si le torrent qBittorrent correspondant n'est pas complété à `100%`, il doit être ignoré,
- ce filtre s'applique avant toute lecture de fichiers,
- dans ce cas, journaliser un skip explicite et ne pas tenter de capture.

Cas à gérer :

- si qBittorrent expose un unique fichier vidéo, le prendre,
- si qBittorrent expose deux fichiers vidéo, prendre le plus gros,
- si qBittorrent expose exactement trois fichiers vidéo, prendre le plus gros,
- si qBittorrent expose plus de trois fichiers, considérer cela comme une erreur légère,
- si aucun fichier vidéo n'est trouvé, considérer cela comme une erreur.

Justification :

- la sélection automatique ne doit être permise que pour les cas simples,
- les cas `2` et `3` fichiers sont traités automatiquement en prenant le plus gros,
- au-delà de `3`, la structure est considérée comme trop ambiguë pour un traitement fiable.

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

- 9 captures exactement,
- positions fixes : `10%`, `20%`, `30%`, `40%`, `50%`, `60%`, `70%`, `80%`, `90%`,
- ignorer `0%` et `100%`,
- nommage temporaire déterministe,
- nettoyage systématique des fichiers temporaires,
- format image : `jpg` ou `png`, configurable, avec `jpg` par défaut,
- qualité raisonnable pour limiter la taille d'upload.

Exigences techniques :

- ne pas capturer à partir d'une durée nulle,
- vérifier que le fichier existe avant extraction,
- échouer proprement si `ffprobe` ou `ffmpeg` ne sont pas disponibles,
- encapsuler les appels système avec timeout.

## Upload vers imgbb

L'upload se fait par requête HTTP à `IMGBB_API`.

Contraintes :

- uploader les 9 images individuellement,
- récupérer l'URL publique finale de chaque image,
- conserver l'ordre des timestamps dans le commentaire final,
- si un upload échoue, ne pas poster de commentaire partiel,
- en cas d'échec partiel, journaliser et passer au torrent suivant.

## Publication du commentaire

Le commentaire publié sur le torrent doit contenir strictement les URLs, une par ligne :

```text
https://...
https://...
https://...
https://...
https://...
https://...
https://...
https://...
https://...
```

Pas de texte additionnel sauf si `CALEWOOD_API` exige un wrapper particulier. Si c'est le cas, ce wrapper doit être configurable et désactivé par défaut.

## Idempotence

Le job doit être idempotent.

Règles :

- si le commentaire contient déjà un lien `imgbb`, ne rien republier,
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
- `too_many_video_files_warning`
- `ffprobe_error`
- `ffmpeg_error`
- `imgbb_upload_error`
- `comment_post_error`

Le code de sortie global doit être non nul si au moins une erreur technique bloquante survient pendant le run, même si certains torrents ont été traités avec succès.

`too_many_video_files_warning` est une erreur légère :

- elle doit être journalisée,
- le torrent courant est ignoré,
- elle ne doit pas à elle seule rendre le code de sortie global non nul.

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
│   └── movie_preview/
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
- `CALEWOOD_API_ARCHIVED_STATUSES`
- `HASH_FIELD_NAME`
- `QBITTORRENT_BASE_URL`
- `QBITTORRENT_USERNAME`
- `QBITTORRENT_PASSWORD`
- `QBITTORRENT_TIMEOUT_SECONDS`
- `QBITTORRENT_VERIFY_TLS`
- `IMGBB_API_KEY`
- `IMGBB_TIMEOUT_SECONDS`
- `IMAGE_FORMAT`
- `DRY_RUN`
- `LOG_LEVEL`
- `TEMP_DIR`

Optionnelles :

- `CALEWOOD_API_COMMENT_WRAPPER_TEMPLATE`
- `REQUESTS_RETRY_COUNT`
- `FFMPEG_BIN`
- `FFPROBE_BIN`

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
3. calcul exact des 9 timestamps,
4. sélection du plus gros fichier quand il y a 2 vidéos,
5. sélection du plus gros fichier quand il y a 3 vidéos,
6. warning léger quand il y a plus de 3 vidéos,
7. erreur quand aucun hash tracker n'est présent,
8. `dry-run` ne poste rien,
9. pas de commentaire posté si un seul upload échoue,
10. émission d'un log de réparation manuelle si des captures ou uploads partiels existent sans commentaire final.

## Critères d'acceptation

Le travail est acceptable si :

1. le projet se build avec `docker build`,
2. le conteneur démarre et valide sa configuration,
3. le workflow complet est découpé en modules testables,
4. les secrets sont exclusivement injectés par environnement,
5. les 9 captures sont produites aux bons pourcentages,
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
- ne pas contourner la règle des 9 captures,
- ne pas poster de commentaire si les 9 URLs ne sont pas disponibles,
- ne pas modifier le comportement demandé sur le cas des multiples fichiers,
- ne pas stocker de cache persistant par défaut,
- ne pas introduire de télémétrie.

## Remarques

S'il manque des détails exacts sur `CALEWOOD_API`, les agents doivent :

1. garder une interface client propre et adaptable,
2. centraliser le mapping de schéma dans `calewood_api.py`,
3. documenter clairement les hypothèses dans `README.md`,
4. ne jamais remplacer des inconnues par des valeurs réelles ou identifiantes.
