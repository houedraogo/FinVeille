# Nettoyage du catalogue Kafundo — runbook (phase 1 préparée, rien déployé)

Objectif : un catalogue fiable, sans doublons, uniquement des opportunités de financement,
avec une consommation IA maîtrisée. **Aucune suppression physique.**

## Ce qui est livré (branche `phase1-catalog-cleanup`)

| Domaine | Fichiers |
|---|---|
| Identité / doublons | `app/services/device_identity.py` (certain / probable / homonyme / aucun) |
| Périmètre | `app/services/scope_rules.py` (règles structurelles, haute précision) |
| Quarantaine / file de revue | `app/services/catalog_guard.py`, tables `device_rejections`, `device_duplicate_candidates` |
| Collecteur | `app/collector/deduplicator.py`, `app/collector/pipeline.py` |
| Import CSV | `app/data/import_aides_entreprises_csv.py` (`--dry-run`) |
| IA | `app/services/ai_eligibility.py` + gardes (`ai_rewriter`, `quality_tasks`, `admin /rewrite`, backfill) |
| Archivage réversible | `app/services/catalog_cleanup.py`, CLI `app/data/catalog_cleanup.py`, table `device_archive_log` |
| Qualité progressive | `app/services/catalog_quality.py` (déterministe, zéro IA) |
| Garde-fou | `app/models/archive_guard.py` (interdit de réactiver une fiche archivée hors restauration) |
| Migration | Alembic `b7d3a91c5e24` (3 tables, additive) |

## Procédure (chaque étape attend une validation explicite)

1. **Sauvegarde** : `pg_dump -Fc` + somme SHA-256 dans `/opt/finveille-backups/`, nom noté dans `--backup-ref`.
   Vérifier qu'elle se restaure (voir « Répétition »).
2. **Déploiement du code** (image backend + worker + beat) puis `alembic upgrade head`.
3. **Plan (lecture seule)** :
   `python -m app.data.catalog_cleanup plan --out /tmp/plan --protect-file ids_finnovatix.txt`
   `ids_finnovatix.txt` = `kafundo_id` des `funding_calls` Finnovatix (un par ligne) : un doublon déjà
   référencé par un dossier client n'est jamais archivé (lot P), et devient la fiche conservée si possible ;
   une fiche des lots A/B déjà référencée est mise de côté (lot Q, décision humaine).
4. **Suspension IA** (réversible) : `hold-ai --run-id RUN-AI --protect-file … [--yes]`.
5. **Archivage par lot, dans l'ordre A puis B puis C** :
   `apply --batch A_projets_institutionnels --plan-hash <hash du plan> --run-id RUN-A --backup-ref <dump> --protect-file … [--yes]`
   Sans `--yes` : simulation. Hash inattendu : arrêt. Lots F, H, P, Q, G, Z : refusés (revue humaine).
6. **Restauration** : `restore --run-id RUN-A [--batch …] [--device-id …] [--yes]` — remet les valeurs exactes.
7. **Qualité progressive** : `quality --limit 200` (rapport) puis `--yes` (écrit seulement `user_quality_*`).

## Répétition effectuée (10 octobre 2026, copie jetable isolée du dump 03:00)

* Restauration du dump nocturne : 7 s, 0 erreur, 7 678 fiches.
* Migration `b7d3a91c5e24` appliquée sur la copie.
* hold-ai + archivage A, B, C puis restauration complète : empreinte md5 du catalogue **identique** à l'état initial.

## Points d'attention

* Les scripts ponctuels de `app/data/` peuvent réaffecter `validation_status` : le garde-fou ORM les bloque
  pour une fiche archivée (les `UPDATE` SQL directs ne sont pas interceptés — ne pas en écrire).
* Côté Finnovatix : les `FundingCall` ne sont jamais supprimés ; un dispositif archivé disparaît du flux
  de synchronisation (statut non public) sans effacer la fiche locale ni les opportunités de dossiers.
