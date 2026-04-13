# calewood-movie-preview

`calewood-movie-preview` est une image Docker `linux/amd64` qui automatise la génération de previews vidéo pour des torrents en pré-archivage.

Le conteneur :

- lit les torrents éligibles depuis `CALEWOOD_API`,
- vérifie si le commentaire contient déjà des liens `imgbb`,
- retrouve le torrent correspondant dans qBittorrent avec le package Python officiel `qbittorrent-api`,
- localise les fichiers vidéo éligibles (exclusion des fichiers `Bonus`),
- génère un nombre de captures multiple de `3` (max `27`),
- envoie les images sur `IMGBB_API` (avec `album_id` si configuré),
- poste ensuite les URLs en préfixe du commentaire existant, une URL par ligne.

## Sécurité Par Défaut

Le comportement par défaut est `dry-run`.

Sans action explicite :

- aucune image n'est publiée sur imgbb,
- aucun commentaire n'est modifié côté `CALEWOOD_API`,
- aucune écriture distante n'est autorisée.

Pour autoriser les opérations réelles, il faudra lancer le conteneur avec `--just-do-it`.

## Fonctionnement

À chaque exécution, le conteneur :

1. récupère les torrents via `/api/upload/list?status=my-uploads` et `/api/upload/list?status=my-uploading`,
2. filtre en `cat=XXX`,
3. récupère le hash de correspondance depuis `CALEWOOD_API`,
4. interroge qBittorrent,
5. sélectionne les fichiers vidéo éligibles,
6. lit le commentaire uniquement pour les candidats traitables,
7. détecte les liens `imgbb.com` et `i.ibb.co`,
8. skippe les torrents déjà illustrés,
9. émet un warning si le commentaire contient entre `1` et `8` liens imgbb,
10. calcule la durée avec `ffprobe`,
11. extrait les captures avec `ffmpeg`,
12. upload les captures sur imgbb,
13. poste les URLs en préfixe du commentaire du torrent.

## Règles De Sélection Vidéo

Seuls les torrents qBittorrent complétés à `100%` sont traités. Si le torrent n'est pas terminé, il est ignoré avant toute sélection de fichier.

- seuls les fichiers vidéo sont conservés,
- les fichiers dont le nom contient `Bonus` sont exclus,
- si aucun fichier vidéo n'est trouvé : erreur.

Extensions minimales prises en charge :

- `.mkv`
- `.mp4`
- `.avi`
- `.mov`
- `.m4v`
- `.ts`

## Génération Des Captures

- le nombre total de captures est un multiple de `3`,
- maximum `27` captures,
- `1` vidéo : `9` captures réparties,
- `2` vidéos : `9` captures par vidéo (total `18`),
- `3` vidéos : `6` captures par vidéo (total `18`),
- `>3` vidéos : sélection déterministe de `18` vidéos aléatoires, 1 capture au milieu de chacune.

## Comportement Sur Les Commentaires

- `0` lien imgbb détecté : le torrent reste éligible.
- `1` à `8` liens imgbb détectés : warning `partial_imgbb_links_warning`, pas de repost automatique.
- `9` liens imgbb ou plus : le torrent est considéré comme déjà illustré.

Le commentaire publié contient les nouvelles URLs en préfixe, puis le commentaire existant.
Si aucun commentaire n’existe, seules les URLs sont publiées.

## Réparation Manuelle

Si des captures ont été produites ou si des uploads partiels existent sans commentaire final, le conteneur doit journaliser un événement exploitable pour reprise manuelle.

Ce log doit permettre d'identifier :

- l'identifiant du torrent côté `CALEWOOD_API`,
- le hash de correspondance,
- le chemin vidéo retenu,
- le répertoire temporaire,
- la raison du non-post,
- le nombre d'images générées,
- le nombre d'uploads réussis.

## Build

```bash
docker build --platform linux/amd64 -t sat0r/calewood-movie-preview .
```

## Exécution

Le volume monté doit correspondre en priorité au répertoire de téléchargement qBittorrent.

Contrainte importante :

- le chemin vu depuis le conteneur doit idéalement être exactement le même que celui renvoyé par qBittorrent,
- en pratique, il faut réutiliser dans ce conteneur les mêmes chemins de montage que dans le conteneur qBittorrent,
- autrement dit, si qBittorrent annonce un fichier sous un préfixe donné, ce même préfixe doit exister dans le conteneur,
- le remapping `PATH_MAP_SOURCE` / `PATH_MAP_TARGET` ne doit être utilisé qu'en second choix si un montage identique est impossible.

Mode sûr par défaut :

```bash
docker run --rm --platform linux/amd64 \
  --env-file .env \
  -v <HOST_QBITTORRENT_DOWNLOAD_ROOT>:<HOST_QBITTORRENT_DOWNLOAD_ROOT>:ro \
  sat0r/calewood-movie-preview
```

Mode actif :

```bash
docker run --rm --platform linux/amd64 \
  --env-file .env \
  -v <HOST_QBITTORRENT_DOWNLOAD_ROOT>:<HOST_QBITTORRENT_DOWNLOAD_ROOT>:ro \
  sat0r/calewood-movie-preview --just-do-it
```

## Variables D'Environnement

Variables minimales :

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

Variables optionnelles :

- `REQUESTS_RETRY_COUNT`
- `FFMPEG_BIN`
- `FFPROBE_BIN`
- `PATH_MAP_SOURCE`
- `PATH_MAP_TARGET`

Valeurs de comportement attendues :

- `CALEWOOD_API_BASE_URL=https://calewood.n0flow.io/api` par défaut
- `CALEWOOD_API_CATEGORY=XXX` par défaut
- `CALEWOOD_API_SINGLE_ID` vide par défaut
- `CALEWOOD_API_PER_PAGE=200` par défaut
- `HASH_FIELD_NAME=sharewood_hash` recommandé
- `DRY_RUN=true` par défaut
- `IMAGE_FORMAT=jpg` par défaut
- `IMGBB_ALBUM_ID=ymNBDj` par défaut

## Mapping De Chemins

qBittorrent peut renvoyer un chemin visible différemment depuis le conteneur. Le projet prévoit un remapping simple :

- `PATH_MAP_SOURCE`
- `PATH_MAP_TARGET`

Exemple :

- chemin retourné par qBittorrent : `<SOURCE_PATH_PREFIX>/releases/movie.mkv`
- chemin visible dans le conteneur, cas recommandé : `<SOURCE_PATH_PREFIX>/releases/movie.mkv`
- chemin visible dans le conteneur, cas avec remapping : `<TARGET_PATH_PREFIX>/releases/movie.mkv`

Le comportement recommandé reste :

- monter le dossier de téléchargement qBittorrent avec le même chemin côté hôte et côté conteneur,
- reprendre les mêmes chemins de montage que ceux utilisés par le conteneur qBittorrent,
- éviter le remapping quand ce montage identique est possible,
- réserver `PATH_MAP_SOURCE` et `PATH_MAP_TARGET` aux environnements où cette symétrie de chemin n'est pas faisable.

## Dépendances Techniques

Le projet cible Python 3.12 et s'appuie notamment sur :

- `qbittorrent-api` pour qBittorrent,
- `httpx` pour les APIs HTTP,
- `ffmpeg` et `ffprobe` dans l'image Docker.

## Contraintes D'Implémentation

- image Docker ciblée `linux/amd64`
- exécution en utilisateur non root
- pas de secrets embarqués
- logs structurés avec redaction des secrets
- nettoyage des fichiers temporaires même en cas d'erreur
- aucun commentaire partiel ne doit être posté
- aucun commentaire ne doit être modifié si un lien imgbb existe déjà
- si un upload échoue, rien n'est posté

## Exemples D'Usage

Run de vérification sans action distante :

```bash
docker run --rm --platform linux/amd64 \
  --env-file .env \
  -e DRY_RUN=true \
  -v <HOST_QBITTORRENT_DOWNLOAD_ROOT>:<HOST_QBITTORRENT_DOWNLOAD_ROOT>:ro \
  sat0r/calewood-movie-preview
```

Run réel avec opt-in explicite :

```bash
docker run --rm --platform linux/amd64 \
  --env-file .env \
  -v <HOST_QBITTORRENT_DOWNLOAD_ROOT>:<HOST_QBITTORRENT_DOWNLOAD_ROOT>:ro \
  sat0r/calewood-movie-preview --just-do-it
```

### Skip qBittorrent

Pour désactiver la phase qBittorrent (debug) :

```bash
sat0r/calewood-movie-preview --skip-qb
```

### Forcer Un ID/Hash

Pour cibler un torrent unique en forçant l'ID CALEWOOD et le hash qBittorrent :

```bash
docker run --rm --platform linux/amd64 \
  --env-file .env \
  -v <HOST_QBITTORRENT_DOWNLOAD_ROOT>:<HOST_QBITTORRENT_DOWNLOAD_ROOT>:ro \
  sat0r/calewood-movie-preview --force-id 12345 --force-hash deadbeef...
```

Les deux options `--force-id` et `--force-hash` sont obligatoires et doivent être fournies ensemble.

## Fichier Env

Un fichier d'exemple est fourni :

- `.env.example`

Le lancement standard attendu est :

1. créer un `.env` basé sur `.env.example`
2. remplacer les secrets et URLs nécessaires
3. lancer le conteneur avec `--env-file .env`

## Documentation Interne

Les exigences détaillées d'implémentation sont définies dans [`AGENTS.md`](AGENTS.md).

## Licence

Ce projet est distribué sous licence `GNU GPL v3`. Voir [`LICENSE`](LICENSE).
