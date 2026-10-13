# Plan de rotation des secrets Kafundo — après l'incident du 12-13/10/2026 (PLAN SEULEMENT, rien n'est exécuté)

Contexte : un mineur (`/tmp/hasaneyoh`, depuis le 12/10 23:24 UTC) et un client `/tmp/safenet-client` (depuis le 15/09 23:45) ont
tourné dans le conteneur FasoData `fasodata-web-1`, qui était rattaché au réseau `kafundo_default`. Ce conteneur pouvait joindre
PostgreSQL, Redis et le backend de Kafundo. Aucune preuve de lecture des secrets Kafundo n'a été recherchée (hors périmètre) :
**ils sont à considérer comme potentiellement exposés** sur la période 15/09 → 13/10. Ce plan complète
`docs/SECRETS_ROTATION_RUNBOOK.md` (procédures détaillées par service) avec l'ordre, les prérequis et les interruptions.

## 1. Inventaire (noms uniquement, relevés sur les conteneurs backend / worker / beat)

| Priorité | Variable(s) | Où est-elle utilisée | Effet de la rotation |
|---|---|---|---|
| 1 | `POSTGRES_PASSWORD`, `DATABASE_URL`, `DATABASE_SYNC_URL` | postgres, backend, worker, beat, postgres-backup | coupure ≈ 15-30 s (swap des 3 conteneurs) ; script `rotate_postgres_password.sh` |
| 1 | `REDIS_PASSWORD`, `REDIS_URL` | redis, backend, worker, beat | redémarrage de Redis : files Celery vidées (vides au repos) ; coupure ≈ 20 s |
| 1 | `SECRET_KEY` | backend (JWT/sessions) | **toutes les sessions utilisateurs sont déconnectées** ; prévenir |
| 1 | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | backend (facturation) | « Roll key » côté Stripe (ancienne clé valide 1 h) ; aucun arrêt |
| 1 | `SMTP_PASSWORD` (`SMTP_HOST/PORT/USER`) | backend (e-mails) | changement chez le fournisseur de messagerie ; autres clients à remettre à jour |
| 2 | `OPENAI_API_KEY`, `MISTRAL_API_KEY` | backend, worker (IA) | révocation côté fournisseur après remplacement ; aucun arrêt |
| 2 | `AIDES_ENTREPRISES_API_KEY` / `_ID`, `LES_AIDES_API_IDC` | worker (collecte) | demande d'une nouvelle clé au fournisseur ; collecte interrompue jusqu'au remplacement |
| 3 | `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (public), `STRIPE_PRICE_*` (identifiants non secrets) | frontend | aucune rotation nécessaire |
| — | `.env`, `.env.production` (hôte, 0600) et **9 copies** `/opt/releases/kafundo/*/.env.production` | déploiements | purger les copies périmées après la rotation |

Hors Kafundo (à traiter par leurs propriétaires) : secrets FasoData (conteneur compromis), Finnovatix (`DB_PASSWORD`,
`OPENAI_API_KEY`… voir runbook), VIGIS.

## 2. Prérequis bloquants (aucun n'est levé aujourd'hui)

1. **Hôte sain et stable ≥ 24 h** (charge < 4, steal < 10 %, aucun processus suspect) ; FasoData isolé du réseau `kafundo_default`
   (vérifié le 13/10 : `fasodata_prod` seulement).
2. **Rollbacks `-prev` existants** : `rotate_postgres_password.sh` refuse de tourner tant que des `kafundo-*-prev` existent
   (10 conteneurs actuellement). Décision requise : les conserver (archive d'images `rollback_images_20261012`) puis `commit`, ou
   adapter le script. Ne rien supprimer sans validation.
3. **Un seul fichier d'environnement source** : déployer uniquement depuis `/opt/finveille/.env.production` ; ajouter les 9 copies
   des releases à `ENV_FILES` ou les purger après validation.
4. **Sauvegarde fraîche vérifiée** + dump restauré en copie jetable ; image de retour arrière chargeable.
5. **Pas de collision** avec les tâches planifiées (créneau 07:10–07:55 ou 21:15–21:45 UTC) ni avec l'archivage du lot A.
6. Les nouvelles valeurs sont saisies par le propriétaire en mode masqué sur le serveur (`set_secret.sh`), jamais dans une conversation.

## 3. Ordre d'exécution proposé (une étape par créneau, vérification avant la suivante)

| Étape | Secret | Interruption | Vérification | Retour arrière |
|---|---|---|---|---|
| R1 | Stripe (clé secrète puis secret de webhook) | aucune | webhook de test 200, page de facturation | ancienne clé valide 1 h |
| R2 | SMTP | aucune | `POST /api/v1/admin/email/test`, journaux sans erreur d'authentification | ancien mot de passe re-saisissable |
| R3 | Clés IA (OpenAI, Mistral) | aucune | une réécriture de test, journaux | ancienne clé jusqu'à révocation |
| R4 | Clés collecte (AIDES_ENTREPRISES, LES_AIDES) | collecte du fournisseur suspendue | collecte `success` | ancienne clé si encore valide |
| R5 | `REDIS_PASSWORD` | ≈ 20 s (Redis + 3 swaps) | ping Celery, files à 0, beat sans tâche | `swap_container.py rollback` + ancien `.env` |
| R6 | `SECRET_KEY` | sessions invalidées | connexion, `/api/ready` | ancienne valeur (sessions restaurées) |
| R7 | `POSTGRES_PASSWORD` + URLs | ≈ 15-30 s | `rotate_postgres_password.sh` (contrôles intégrés : nouvelle clé acceptée, ancienne refusée) | retour automatique du script |
| R8 | Purge des copies `.env.production` périmées, `chmod 600`, `shred` des sauvegardes de travail | — | `ls -la` | — |

Chaque étape : dry-run, journal, contrôle `/api/ready`, pagination, files Celery, 0 erreur ; arrêt au moindre écart.

## 4. Durcissement associé (décisions séparées)

* Les ports 8000 (backend Kafundo), 8080 (nginx) et d'autres conteneurs sont publiés sur `0.0.0.0` : vérifier le pare-feu
  (non contrôlé ici) et lier à `127.0.0.1` derrière nginx si possible.
* FTP (`proftpd`, port 21) écoute sur toutes les interfaces : à examiner côté hôte.
* Limites mémoire par conteneur (8 Go partagés entre ~36 conteneurs) et surveillance swap/steal.
* Réseaux Docker dédiés par projet (aucun conteneur étranger sur `kafundo_default`) ; le script `lot_a_pilot.sh` le contrôle désormais.
