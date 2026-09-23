# Lot 4 — politique commerciale et synchronisation Stripe

La base conserve le mapping `stripe_customer_id → organization_id`. Stripe est l'autorité pour l'identifiant de subscription, son statut, ses périodes et son Price ID. Le Price ID est rapproché d'un plan Kafundo actif côté serveur ; les métadonnées du webhook ne choisissent jamais le plan. Les attributions manuelles par administrateur plateforme restent possibles uniquement sans subscription Stripe liée. `enterprise` est une offre manuelle à prix catalogue nul : aucun checkout Stripe n'est créé tant qu'un Price ID n'est pas explicitement configuré côté serveur.

| Plan | Utilisateurs | Alertes | Recherches | Pipeline | Matching / scoring | Alertes personnalisées | Export CSV/Excel | Analyse IA |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| Free | 1 | 3 | 5 | 15 | Non | Non | Non | Non |
| Pro | 1 | 25 | 75 | 150 | Oui | Oui | Non | Non |
| Team | 5 | 120 | 250 | 600 | Oui | Oui | Oui | Non |
| Expert | 10 | 250 | 500 | 2000 | Oui | Oui | Oui | Oui |
| Enterprise | Illimité | Illimité | Illimité | Illimité | Oui | Oui | Oui | Oui |

Les alertes Free avec critères vides restent possibles dans la limite de 3. Les critères personnalisés exigent le droit `custom_alerts`. Les quotas sont comptés par organisation et vérifiés sous verrou PostgreSQL de l'organisation jusqu'à l'insertion. Les invitations en attente non expirées réservent une place utilisateur.

Seuls `active` et `trialing` donnent des droits payants, pendant une période Stripe encore valide. Une annulation programmée conserve les droits jusqu'à la fin de la période si le statut reste `active`. `past_due`, `unpaid`, `incomplete`, `incomplete_expired`, `canceled`, `paused`, un statut inconnu, un plan inconnu ou un Price ID inconnu ne donnent que les droits Free. Un abonnement administré manuellement sans ID Stripe peut être actif sans période Stripe.

Le webhook exige le secret et une signature valide sur les octets bruts. Les événements connus sont sérialisés par organisation, dédupliqués par ID puis appliqués seulement si `event.created` est plus récent. À timestamp égal, le système relit la subscription Stripe ; si la relecture échoue, les droits sont suspendus jusqu'à réconciliation. Un Price ID ou statut inconnu suspend aussi les droits et avance l'horloge locale. Une subscription terminée ne peut être réactivée sous le même ID : un réabonnement légitime possède un nouvel ID Stripe. Le ledger et l'état d'abonnement sont écrits dans une transaction. Le checkout réutilise une session encore ouverte pour le même plan et vérifie à nouveau les subscriptions Stripe avant toute nouvelle session. Une subscription locale ou Stripe non terminale renvoie vers le portail.

Décisions métier encore nécessaires : traitement des remboursements partiels ou complets, politique de grâce éventuelle pour `past_due`, résiliation d'un client Stripe avant suppression définitive de son organisation, et réconciliation automatique si une réponse Stripe externe réussit mais que la transaction locale échoue. Le code refuse la suppression d'une organisation liée à un client Stripe ; le nettoyage doit être contrôlé.
