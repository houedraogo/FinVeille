# Celery : démarrage groupé de beat et file historique `celery` (constats du 10/10/2026)

## Démarrage groupé (corrigé dans le code, non déployé)

* Cause : `backend/celerybeat-schedule` (shelve d'ordonnancement, `last_run_at` = 25/04/2026) était versionné depuis le premier
  commit et copié dans l'image par `git archive`. Au premier démarrage du conteneur, les 10 tâches « dues » sont parties d'un coup
  (collectes ×3 niveaux → 237 tâches, alertes, enrichissement, qualité, rapport hebdomadaire). Les images précédentes avaient été
  construites sans ce fichier.
* Correctif (commit `7f5448a`) : fichier retiré du dépôt, `.gitignore` + `backend/.dockerignore`, et
  `beat_schedule_filename = $CELERY_BEAT_SCHEDULE_FILE` (défaut `/tmp/celerybeat-schedule`, hors du code). Un conteneur neuf ne
  lance plus rien au démarrage ; une tâche manquée pendant l'arrêt est simplement reportée à sa prochaine échéance.
* Tests : `tests/test_celery_beat_schedule.py` (chemin hors code, fichier non versionné/dockerignoré, 0 tâche due au démarrage,
  mode de défaillance documenté avec un `last_run_at` ancien). Le test échoue si le chemin redevient relatif.
* À faire au prochain déploiement (avec validation) : construire depuis ce commit.

## File historique `celery` (382 messages)

| Mesure | Constat |
|---|---|
| Contenu | 14 types de tâches qualité/synchronisation : `requalify_editorial_auto_sources` 188 ; 16 × chacune des 12 tâches quotidiennes ; 2 × `weekly_quality_report`. 382 identifiants distincts, 0 doublon, 0 `eta`, 0 relance |
| Ancienneté | pas d'horodatage dans les messages ; 16 occurrences de chaque tâche quotidienne et 188 ≈ 12/jour × 15,7 j → environ **16 jours (≈ 24-25/09 → 09-10/10)** ; 2 origines (2 anciens conteneurs beat, aucun n'existe plus) |
| Pourquoi non traités | les workers n'écoutent que `default,collect,alerts` (vérifié : un seul worker, 3 files) ; ces messages avaient été publiés dans la file par défaut historique `celery`, que personne ne consomme |
| Croissance | stable à 382 depuis les premières mesures du 10/10 ; le beat actuel route les mêmes tâches vers `default` (traitées : démarrage de 10:29, `succeeded`) |
| Blocage des workers | aucun : 0 tâche active / réservée au repos, files `default`, `collect`, `alerts` vidées (237 collectes terminées), 0 tâche échouée dans Finnovatix |
| Risque si consommées | rafale de 382 tâches obsolètes (dont 16 × enrichissement IA, 16 × import CSV) : **ne pas démarrer de worker sur `celery`** |
| Recommandation | exporter les 382 messages (JSON) puis les purger après accord ; décision requise |
