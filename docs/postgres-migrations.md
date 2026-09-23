# Migrations PostgreSQL de Kafundo

Le schéma est défini par les révisions Alembic `5a37a54cae56` (26 tables), `8c2f6e9a4b10` (rapprochement du schéma historique, triggers et plan gratuit), `d742f48a3c19` (table `user_projects`), `e910b53f2c64` (ledger Stripe et checkout) et `f54e3b706d18` (livraisons d'alertes instantanées confirmées). Exécuter les commandes depuis `backend/`, ou dans un conteneur backend avec `/app` comme répertoire de travail. `DATABASE_SYNC_URL` doit cibler **la même base** que `DATABASE_URL` de l'API. Ne jamais utiliser une base de production comme base de test.

## Installation vierge

Après démarrage de PostgreSQL, `python -m migrations.upgrade` applique Alembic. `alembic upgrade head` fonctionne aussi sur une base réellement vide. Vérifier ensuite `alembic current`, `python -m migrations.upgrade` (idempotence) et `GET /api/ready` (HTTP 200). L'API et les workers ne doivent être démarrés qu'après ces contrôles. Aucun `create_all()` n'est requis.

## Installation existante, schéma historique non versionné

1. Arrêter l'API, Celery worker et Celery beat. Attendre la fin des transactions en cours. Laisser PostgreSQL démarré. Ne pas purger Redis ni rejouer de tâches.
2. Faire une sauvegarde `pg_dump -Fc` et **vérifier sa restauration dans une base PostgreSQL isolée** (structure, comptes des tables importantes et quelques lignes). Le script `scripts/backup-postgres.sh` produit un dump atomique et valide sa table des matières, mais cette vérification seule ne remplace pas un essai de restauration. Conserver le dump hors du volume de la base avant migration.
3. Avec les URLs de la base concernée, lancer `python -m migrations.baseline_legacy` sans option. La commande est en lecture seule et signale les tables/colonnes inconnues, types ou nullabilités incompatibles, FK orphelines et doublons empêchant un UNIQUE. Examiner le plan de colonnes, FK, contraintes et index. En cas d'écart dangereux, **arrêter** et analyser la copie ; aucune ligne n'est corrigée ou supprimée automatiquement.
4. Une fois la sauvegarde restaurable confirmée : `python -m migrations.baseline_legacy --stamp --backup-confirmed`. Ce `stamp` n'écrit que la version Alembic de la baseline vérifiée ; il ne transforme pas les tables métier.
5. Exécuter `python -m migrations.upgrade --backup-confirmed`. La révision de réparation revérifie le schéma et les données, ajoute les éléments manquants dans une transaction PostgreSQL puis passe à head. Un échec conserve la dernière version validée et doit être investigué avant toute reprise.
6. Contrôler `alembic current`, les comptes/lignes comparés à la sauvegarde et `GET /api/ready` après démarrage de l'API. Démarrer ensuite les workers et beat. Faire `python -m migrations.upgrade` une dernière fois pour confirmer l'état head sans changement.

Pour une base **déjà versionnée** mais pas à head, sauter le `stamp` : après sauvegarde vérifiée, lancer directement `python -m migrations.upgrade --backup-confirmed`. Le wrapper refuse toute base non vide et non versionnée ; il refuse également l'upgrade d'une base versionnée existante sans `--backup-confirmed`. Ne contourner ces garde-fous ni par `create_all()` ni par `stamp head`.

Sur Compose de production, utiliser `docker compose -f docker-compose.prod.yml` pour arrêter `celery-worker celery-beat backend`, maintenir `postgres redis`, produire et vérifier la sauvegarde, puis exécuter les commandes Python ci-dessus avec `docker compose -f docker-compose.prod.yml run --rm --no-deps backend ...`. Démarrer ensuite `backend` et attendre que son healthcheck `/api/ready` soit healthy avant `celery-worker celery-beat`. Les scripts de démarrage locaux suivent le même ordre ; ils s'arrêtent volontairement sur une base existante tant que la procédure de sauvegarde/baseline n'a pas été faite.

`/api/health` indique seulement que le processus répond. `/api/ready` vérifie en lecture seule la révision Alembic et les colonnes/FK essentielles à l'authentification et aux parcours métier ; il répond 503 si le schéma n'est pas prêt. Il ne remplace pas le contrôle complet de migration. Les downgrades des deux révisions sont volontairement refusés car un retour au schéma antérieur pourrait détruire des données ; restaurer une sauvegarde vérifiée si un retour est nécessaire.
