# Lot A (projets institutionnels) — simulation et plan d'archivage progressif (12/10/2026) — rien archivé

Base : 7 683 fiches, schéma `c8e1f4a7b2d9`. Simulation en lecture seule (`scripts/ops/lot_a_simulation.py`), répétition complète sur
copie jetable (`scripts/ops/lot_a_rehearsal.sh`). Données (0600) : `/opt/finveille-backups/audit_20261012_lotA/`.

## Chiffres exacts

| Élément | Effectif |
|---|---|
| Candidates du lot A (après exclusion des 2 fiches du propriétaire) | **1 125** (1 127 avant) |
| — certaines | **1 118** (498 `open`, 202 `expired`, 418 `standby`) |
| — validées individuellement par le propriétaire (7 projets publics Banque Mondiale / AFD) | **7** |
| — à revue humaine supplémentaire | **0** |
| Exclues sur demande : Madagascar P515164, Rwanda P510000 | 2 (passent en lot Q) |
| Lot Q (références externes à arbitrer, conservées) | 44 (42 + les 2 ci-dessus) |
| Candidates listées dans l'API publique | **0** |
| Références bloquantes (favoris, pipelines, alertes, paires de revue) | **0** |
| Doublon hors lot (certain ou probable) | **0** |
| Fiches déjà journalisées `ai_hold` | 111 (non bloquant : nouvelle ligne de journal) |

Règles : `worldbank_project_record` 1 011, `afd_opendata_project_dataset` 114 ; sources : Banque Mondiale par pays (≈ 60-77 chacun),
AFD concours/appels à projets 113 ; types : `institutional_project` 1 122, `autre` 2, `pret` 1 (AFD FMT Monténégro, validée).
Validation : `admin_only` 1 091, `rejected` 19, `pending_review` 8, `auto_published` 7 (les 7 validées).

Empreintes (calculées avec `protect_for_apply*.txt`, fichiers de protection = références Finnovatix + cibles de rattachement + exclusions) :
* `protect_for_apply.txt` : lot A = 1 118 certaines, empreinte `5ea8c0e5df2a835c`.
* `protect_for_apply_with_owner_validated.txt` : lot A = 1 125, empreinte `b19b8f20b90224bc`.
La liste des identifiants : `lotA_certain_ids.txt` (1 118), `lotA_candidates.csv` (1 125 avec motif, règle, statut, type, source, URL),
`lotA_excluded.csv` (44), `lotA_first_sublot_ids.txt` (50).

## Impacts
* **API publique** : aucune candidate n'est listée aujourd'hui (les fiches `institutional_project` sont masquées par défaut) :
  total de pagination inchangé (3 180). Seul effet visible : le détail direct d'une fiche archivée répond 404 (testé).
  Les 7 fiches validées étaient les seules `auto_published`.
* **Collecteurs** : une fiche archivée n'est jamais réactivée ni modifiée (`last_verified_at` seul avance) ; les fiches hors périmètre
  sont mises en quarantaine à l'ingestion. Testé sur la copie : collecte de la source d'une fiche archivée → 50/50 toujours archivées.
* **IA** : une fiche archivée passe en `on_hold` (plus aucune réécriture IA).
* **Finnovatix** : aucune fiche protégée par un `kafundo_id` n'est dans le lot ; Finnovatix n'est pas modifié.

## Restauration et contrôles
* Chaque archivage écrit une ligne `device_archive_log` (anciennes valeurs exactes). `restore --run-id RUN [--device-id …] --yes`
  remet statut, qualité, IA, tags d'origine. Répétition : 50 fiches archivées puis restaurées → empreinte du catalogue entier
  (statut, IA, qualité, titre) **identique** à l'avant-archivage.
* La migration `c8e1f4a7b2d9` rend la suppression physique d'une fiche journalisée impossible (RESTRICT).

## Plan progressif (chaque étape : validation explicite du propriétaire)

Avant chaque étape : sauvegarde `pg_dump -Fc` + sha256 + sommaire ; régénérer les fichiers de protection (références Finnovatix
courantes) et recalculer l'empreinte ; aucune tâche Celery active (créneau sans collecte : 07:10–07:55 ou 21:15–21:45 UTC) ;
`/api/ready` 200. **L'empreinte du lot change après chaque étape** (les fiches archivées sortent du plan) : toujours recalculer.

| Étape | Contenu | Commande (simulation sans `--yes`) |
|---|---|---|
| 1 | 50 fiches certaines (21 open / 14 expired / 15 standby, 0 listée API) | `apply --batch A_projets_institutionnels --plan-hash <H> --run-id LOTA-S1-<date> --backup-ref <dump> --limit 50 --protect-file protect_for_apply.txt [--yes]` |
| 2 | +200 certaines | idem `--limit 200`, `--run-id LOTA-S2-…` |
| 3 | le reste des certaines (≈ 868) | sans `--limit` (en 2 passes si > 500) |
| 4 | les 7 projets validés individuellement | avec `protect_for_apply_with_owner_validated.txt`, accord explicite séparé |

Contrôles après CHAQUE étape (lecture seule) : archivées = N attendu ; fiches totales inchangées ; journal +N lignes ; `skipped` vide ;
aucune fiche protégée archivée ; `/api/ready` 200 ; pagination (total, lignes, distincts) = avant ; 0 erreur dans les journaux ;
file Celery vide ; collecte suivante (:05) sans échec ni réactivation ; Finnovatix : aucune référence cassée (lecture).

**Critères d'arrêt** (arrêt immédiat, pas d'étape suivante, restauration du run en cause) : écart sur l'un des contrôles
ci-dessus ; `PlanMismatch` ; fiche protégée ou référencée dans le lot ; fiche publique inattendue listée dans l'API qui disparaît ;
augmentation d'erreurs de collecte ; toute alerte du propriétaire. Restauration : `restore --run-id <RUN> --yes`, puis contrôle
d'empreinte.
