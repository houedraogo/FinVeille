# Migration `c8e1f4a7b2d9` — prévalidation (10/10/2026) — NON appliquée en production

## Objet et effets
Remplace les deux clés étrangères de `device_archive_log` vers `devices` :

| Colonne | Avant | Après | Effet |
|---|---|---|---|
| `device_id` | `ON DELETE CASCADE` | `RESTRICT` | supprimer une fiche journalisée est refusé par la base (le journal de restauration n'est plus effacé) |
| `merged_into_id` | `ON DELETE SET NULL` | `RESTRICT` | supprimer la fiche conservée d'un doublon archivé est refusé (le lien de restauration n'est plus perdu) |

`device_duplicate_candidates` garde `CASCADE` (une paire en file de revue n'a pas de valeur sans ses fiches). Aucune donnée n'est
modifiée ; aucune table n'est réécrite. La migration est transactionnelle et définit `lock_timeout = 10 s` : si un verrou ne
peut être pris (écritures longues), elle échoue sans rien laisser à moitié appliqué.

* **Suppressions** : un `DELETE FROM devices` d'une fiche journalisée ou cible de fusion échoue (`violates foreign key`).
  Le code applicatif refuse déjà ces suppressions (409) ; la base devient le filet de sécurité pour tout autre chemin.
* **Restaurations** (`catalog_cleanup restore`) : inchangées, elles ne suppriment aucune fiche.
* **Sources** : `devices.source_id` est `SET NULL`, supprimer une source reste possible.
* **Fusion / purge** : le code re-pointe `merged_into_id` et exclut les fiches journalisées avant de supprimer
  (testé : `tests/test_device_deletion_guard_postgres.py`, 14 tests).

## Pré-contrôles (production, lecture seule, 10/10 13:15 UTC)
| Contrôle | Résultat |
|---|---|
| Conteneurs | backend/worker `fixes1-fb57e3d`, beat `fixes2-e39d055`, PostgreSQL 15.17 sain, Redis sain |
| Révision | `b7d3a91c5e24` (attendue) |
| Journal | 1 012 lignes, toutes `ai_hold`, 0 restaurée, 0 cible de fusion ; 0 orpheline (`device_id`), 0 `merged_into_id` orphelin |
| Fiches archivées | 0 |
| Connexions / transactions > 1 min | 3 / 0 |
| Verrous | la pose des contraintes prend un verrou court sur `devices` et `device_archive_log` (1 012 lignes) |

## Sauvegarde et restauration (base jetable `kafundo-iso-pg`)
* `pre_migration_20261010T131551Z.dump` : 19,99 Mo, sha256 vérifié, 266 entrées, produit en 3 s.
* Restauration : 7 s ; comptes identiques sur les 34 tables ; empreintes du journal et des fiches enregistrées.

## Migration et retour arrière sur la base jetable
| Étape | Résultat |
|---|---|
| `python -m migrations.upgrade --backup-confirmed` | OK en 2,8 s (démarrage du processus compris) ; `Schéma vérifié à head` |
| Clés | `device_id=r`, `merged_into_id=r` ; journal, fiches et comptes de tables inchangés |
| `DELETE` d'une fiche journalisée | refusé (`device_archive_log_device_id_fkey`) |
| `DELETE` d'une cible de fusion (cas construit, annulé) | refusé (`..._merged_into_id_fkey`) |
| `DELETE` d'une fiche ordinaire (annulé) | possible |
| `alembic downgrade b7d3a91c5e24` | OK : clés `c` / `n` restituées, empreintes identiques à l'avant-migration |
| Ré-application | OK |

## Fonctionnement sur la base migrée (code `phase1`, même base jetable)
* API : `/api/health` ok, `/api/ready` = `c8e1f4a7b2d9`, pagination 3 177 lignes / 3 177 distinctes, recherche 2 952 résultats.
* Import CSV aides-entreprises réel (sur la copie) : 2 443 mises à jour, **2 443 inchangées**, 0 erreur, 0 insertion, 16-25 s.
* Collecteurs : 3 sources de niveau 1 collectées sans erreur (une atteint la limite de 20 pages, comportement existant) ;
  fiches avant/après : 7 682 / 7 682.
* Tests PostgreSQL (12 fichiers) : verts, dont `test_schema_migrations_postgres` (8) et `test_device_deletion_guard_postgres` (14).

## Procédure de production (après accord explicite)
1. Vérifier : conteneurs sains, révision `b7d3a91c5e24`, aucune transaction longue, sauvegarde < 1 h
   (`bash scripts/ops/migration_prevalidation.sh` produit une sauvegarde vérifiée et rejoue tout sur copie).
2. Fenêtre : juste après une collecte, hors 03:00 (sauvegarde), 05:00-05:10 (import CSV), 06:30 (synchro Finnovatix).
3. Migration : `docker run --rm --network kafundo_default --env-file <env> <image c8e1> python -m migrations.upgrade --backup-confirmed`
   (image construite depuis la branche de déploiement + ce commit, `HEAD_REVISION = c8e1f4a7b2d9`).
4. Contrôles : `alembic_version = c8e1f4a7b2d9` ; clés en `r` ; `/api/health` ; comptes (fiches 7 682, journal 1 012).
5. Déployer ensuite les images dont `HEAD_REVISION = c8e1f4a7b2d9` (backend, worker, beat) : tant que l'ancienne image tourne,
   seul `/api/ready` répond 503 (écart de révision) ; les requêtes, collectes et imports ne sont pas concernés.

## Retour arrière
* Immédiat (schéma seul) : `python -m alembic downgrade b7d3a91c5e24` (testé : restitue `CASCADE` / `SET NULL`, aucune donnée touchée).
* Complet : restaurer `pre_migration_<ts>.dump` dans une base neuve puis basculer (procédure `pg_restore`, testée, 7 s en copie).
* Conteneurs : `swap_container.py rollback` (les `-prev` sont conservés).
