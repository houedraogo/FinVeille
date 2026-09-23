# Lot 5 — routage et alertes

Avant modification, Redis contenait 809 messages historiques dans `celery`, répartis entre les 14 tâches `quality_tasks`. Le worker écoute uniquement `default,collect,alerts`. Le backlog n'a été ni consommé, ni purgé, ni déplacé : le comptage en lecture seule après correction est resté à 809.

| Tâches nouvelles | Queue | Worker |
| --- | --- | --- |
| `collect_tasks.*` (3 entrées Beat et collecte enfant) | `collect` | `celery-worker -Q default,collect,alerts` |
| `alert_tasks.*` (2 entrées Beat et déclenchement après collecte) | `alerts` | même worker |
| `quality_tasks.*` (14 entrées Beat) et fallback explicite | `default` | même worker |

Le routage a été vérifié pour les 19 entrées Beat et par publication de trois tâches sur un broker mémoire isolé. Le processus Beat déjà lancé doit charger la nouvelle configuration lors du déploiement ; ne jamais ajouter `celery` aux queues écoutées. Le backlog historique exige un tri métier distinct avant toute décision de purge ou de reprise.

Les alertes digest `daily` et `weekly` sont sélectionnées selon leur dernière livraison confirmée. Les alertes `instant` parcourent les dispositifs depuis la création de l'alerte, par lots de 50, et excluent ceux déjà enregistrés dans `alert_deliveries`. Chaque lot est marqué livré uniquement si SMTP confirme l'envoi. L'envoi SMTP et le commit PostgreSQL ne peuvent pas être atomiques : une panne précisément entre les deux peut encore provoquer un nouvel email lors d'un retry. Une idempotence de bout en bout nécessiterait un fournisseur email acceptant une clé d'idempotence.

La recherche de liens `/projects/{id}/edit` dans le frontend actuel ne trouve aucun émetteur ; les actions actuelles pointent vers `/projects/{id}`, route existante. Aucun nouvel écran d'édition n'a été ajouté.
