# Déploiement des correctifs « suppression / fusion / purge / import CSV / pagination » (préparé — rien déployé)

Deux étapes distinctes, chacune avec son accord. Aucune n'est lancée sans validation explicite.

## Contenu

| Commit | Objet | Migration |
|---|---|---|
| `de55dfd` | Jamais de suppression physique d'une fiche archivée/journalisée ; fusion et purge connaissent `device_archive_log` et `device_duplicate_candidates` ; échec fermé si une relation inconnue apparaît ; 409 sur `DELETE` / `merge-group` | non |
| `6e720cf` | Import CSV `aides-entreprises` : `updated_at` ne change que si le contenu écrit change | non |
| `bf93419`, `8ec15b3` | Tests qualité réintégrés, `.gitattributes` | non |
| (pagination) | `GET /api/v1/devices/` : ordre total (identifiant en dernier critère). Avant : 3 179 lignes pour 2 679 fiches distinctes | non |
| `d8dd345` | Migration `c8e1f4a7b2d9` : clés étrangères de `device_archive_log` en `RESTRICT` | **oui (étape 2)** |

## Étape 1 — code seul (aucune migration)

Pré-requis : sauvegarde `pg_dump -Fc` de moins de 24 h lisible ; image taguée par SHA ; version d'alembic de la base
**inchangée** (`b7d3a91c5e24`) : le code de l'étape 1 fonctionne avec ce schéma.

1. `python scripts/ops/swap_container.py plan kafundo-backend --image <image>` (aucune valeur d'environnement affichée).
2. `swap` backend, puis worker et beat, un par un ; chaque `swap` conserve l'ancien conteneur en `-prev`.
3. Ne **pas** exécuter `commit` avant la fin des contrôles.

Contrôles après déploiement (tous lecture seule) :

* `curl -fsS http://localhost:8000/api/health` ; `alembic current` = `b7d3a91c5e24`.
* Pagination : parcourir `/api/v1/devices/?page_size=100` ; `total` == nombre d'identifiants distincts.
* Garde : `DELETE` d'une fiche archivée de test (copie) → 409 ; `merge-group` avec fiche conservée archivée → 409.
* File Celery : stable ; ne pas toucher à la file historique `celery` (382 messages).
* Import CSV : exécuter `--dry-run` : `unchanged` > 0, aucune fiche inchangée marquée mise à jour.

Retour arrière : `swap_container.py rollback <nom>` (instantané).

## Étape 2 — migration `c8e1f4a7b2d9` (validation spécifique)

Pré-requis : étape 1 validée ; sauvegarde fraîche ; `alembic heads` = `c8e1f4a7b2d9`.
Effet : deux `ALTER TABLE` sur `device_archive_log` (ajout de contraintes `RESTRICT`), verrou court ; aucune donnée modifiée.
Contrôle : `alembic current` ; tentative de `DELETE FROM devices` d'une fiche journalisée (copie) refusée par la base.
Retour arrière : `alembic downgrade b7d3a91c5e24` (restitue `CASCADE` / `SET NULL`).

## Ce que cela n'implique pas

Ni archivage des lots A/B/C, ni modification Finnovatix, ni rotation de secret.
