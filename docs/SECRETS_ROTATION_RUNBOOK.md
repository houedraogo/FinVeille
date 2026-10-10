# Rotation des secrets exposés — procédure

Contexte : le 10 octobre 2026, une commande d'inspection a affiché en clair, dans une session
d'assistant, des variables d'environnement du conteneur de sauvegarde Kafundo. Ces valeurs ont
été conservées dans les transcriptions locales de la session. **Rien n'a été retrouvé sur le
serveur** (historique bash, syslog, auth.log, journal, logs du conteneur : 0 occurrence).
La rotation reste la seule vraie parade : une valeur exposée doit être considérée comme compromise.

## Règles d'or

1. **Aucune nouvelle valeur ne transite par une conversation avec l'assistant.** Vous la saisissez
   vous-même, en mode masqué, dans votre propre terminal SSH.
2. Aucune valeur en argument de commande (visible dans `ps`) ni dans l'historique du shell.
3. Une sauvegarde `0600` des fichiers est faite avant modification, détruite après vérification.
4. On vérifie d'abord, on révoque l'ancienne valeur ensuite (jamais l'inverse).

Outils fournis (`scripts/ops/`) : `set_secret.sh` (remplace un secret, saisie masquée, double
saisie), `envfile.py` (édition sûre), `rotate_postgres_password.sh` (rotation PostgreSQL avec
retour arrière automatique), `redact_transcripts.py` (expurgation des transcriptions).

## Inventaire (noms uniquement) — par priorité

| Priorité | Variable | Service | Remarque |
|---|---|---|---|
| 1 — exposée avec certitude | `STRIPE_SECRET_KEY` (live) | Kafundo | Rotation Stripe |
| 1 | `SMTP_PASSWORD` | Kafundo | Boîte `contact@…` |
| 1 | `POSTGRES_PASSWORD` (+ `DATABASE_URL`, `DATABASE_SYNC_URL`) | Kafundo | Base non exposée sur Internet ; script fourni |
| 2 — présentes dans des transcriptions | `STRIPE_WEBHOOK_SECRET`, `SECRET_KEY`, `REDIS_PASSWORD` | Kafundo | `SECRET_KEY` : invalide les sessions de connexion |
| 2 | `DB_PASSWORD`, `DB_ROOT_PASSWORD`, `OPENAI_API_KEY`, `PERFEX_API_KEY`, `LINKEDIN_CLIENT_SECRET`, `MICROSOFT_CLIENT_SECRET`, `SETUP_TOKEN` | Finnovatix | À évaluer (certaines valeurs peuvent être de test) |
| 2 | `APP_KEY` | Finnovatix | **Ne pas changer à la légère** : chiffrement des données et sessions ; procédure dédiée (`php artisan key:generate` + ré-chiffrement) |
| 3 — autres projets | `GMAIL_CLIENT_SECRET`, `APIFY_TOKEN`, `N8N_ENCRYPTION_KEY`, clés Higgsfield, etc. | autres | Même démarche |

## Stripe (vous, dans le tableau de bord + votre terminal)

1. Tableau de bord Stripe → *Developers* → *API keys* → **Roll key** sur la clé secrète. Choisir une
   expiration courte de l'ancienne clé (1 h) : le temps de déployer. Copier la nouvelle clé dans le presse-papiers.
2. Sur le serveur, **dans votre propre session SSH** :
   `cd /opt/finveille && sudo bash scripts/ops/set_secret.sh STRIPE_SECRET_KEY .env .env.production`
   (collez la valeur à l'invite masquée, deux fois).
3. *Developers* → *Webhooks* → votre point de terminaison → **Roll secret** (délai de grâce), puis
   `sudo bash scripts/ops/set_secret.sh STRIPE_WEBHOOK_SECRET .env .env.production`.
4. Redémarrer : `docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate backend celery-worker celery-beat postgres-backup`
5. Vérifier : `curl -fsS http://localhost:8000/api/health` ; dans Stripe, **Send test webhook** → réponse 200
   dans les logs du backend ; ouvrir une page de facturation de test.
6. Quand tout fonctionne : laisser l'ancienne clé expirer (ou la révoquer) et le délai de grâce du webhook s'achever.
7. Examiner *Developers → Logs* sur la fenêtre d'exposition (depuis le 10/10/2026, ~05:00 UTC) : requêtes
   inattendues, IP inconnues.

## SMTP

1. Changer le mot de passe de la boîte chez l'hébergeur de messagerie (webmail/panneau), en notant les
   autres clients qui l'utilisent (téléphones, webmail) pour les mettre à jour.
2. `sudo bash scripts/ops/set_secret.sh SMTP_PASSWORD .env .env.production`
3. Même commande de redémarrage que ci-dessus.
4. Vérifier : envoi de test depuis l'administration (`POST /api/v1/admin/email/test`) puis lecture des logs du
   backend (aucune erreur d'authentification SMTP).

## PostgreSQL (script prêt — **exécution seulement après accord explicite**)

```
cd /opt/finveille
bash scripts/ops/rotate_postgres_password.sh --dry-run    # contrôles + plan, n'écrit rien
bash scripts/ops/rotate_postgres_password.sh              # exécution ; taper ROTATE pour confirmer
```

* Pré-contrôles : fichiers présents, conteneurs démarrés, **sauvegarde de moins de 26 h lisible**.
* Le mot de passe (40 caractères alphanumériques) est généré sur place, jamais affiché ; transmis à
  PostgreSQL par l'entrée standard ; copies de travail `0600` détruites (`shred`) à la sortie.
* Met à jour `POSTGRES_PASSWORD`, `DATABASE_URL`, `DATABASE_SYNC_URL` dans `.env` **et** `.env.production`.
* Recrée seulement `backend`, `celery-worker`, `celery-beat`, `postgres-backup` (le conteneur PostgreSQL n'est pas
  redémarré). Coupure : quelques secondes.
* Vérifie la santé du service, que la **nouvelle clé est acceptée et l'ancienne refusée**.
* Échec à n'importe quelle étape après le changement : **retour arrière automatique** (mot de passe, fichiers, services).
* Testé sur une pile jetable : dry-run, rotation réussie, échec forcé avec retour arrière.
* À faire ensuite : supprimer toute autre copie de l'ancien mot de passe (scripts d'exploitation, gestionnaire, notes).

## Après rotation

* Supprimer les sauvegardes de travail : `shred -u /opt/finveille/.env.rotation-bak.*`
* Restreindre les permissions (aujourd'hui en 644, lisibles par tout utilisateur de la machine) :
  `chmod 600 /opt/finveille/.env /opt/finveille/.env.production`
* Si `bootstrap/cache/config.php` (Finnovatix) est en 644, il contient aussi des secrets : le passer en 600 (propriétaire `sail`).

## Transcriptions locales

* `python scripts/ops/redact_transcripts.py <dossier>` simule (compteurs seulement) ; `--apply` remplace par une
  version expurgée vérifiée (JSON valide, même nombre de lignes, plus aucune valeur détectable).
* La session **en cours** est ignorée tant qu'elle est active (risque de corruption). Après l'avoir fermée :
  `python scripts/ops/redact_transcripts.py "%USERPROFILE%\.claude\projects" --apply --include-recent`
* `~/.claude/file-history` conserve aussi des copies de fichiers édités (15 fichiers contenant des secrets d'autres projets) :
  même outil, sur demande.
* L'expurgation locale ne retire pas les valeurs déjà transmises au service d'IA pendant la conversation : seule la rotation protège.
