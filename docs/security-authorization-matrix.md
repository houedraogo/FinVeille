# Lot 3 — modèle et matrice d'autorisation

Le rôle plateforme (`users.role`: `admin`, `editor`, `reader`) est distinct du rôle d'organisation (`organization_members.role`: `org_owner`, `org_admin`, `member`, `viewer`). Les endpoints `/admin`, les sources et l'édition des fiches utilisent le rôle plateforme. Un administrateur d'organisation n'est pas administrateur Kafundo. Les claims de rôle du JWT ne font pas foi : l'utilisateur actif est relu en base.

Le tenant actif est `users.default_organization_id` lorsque renseigné, sinon la première appartenance active. La sélection explicite par `/api/v1/organizations/{id}/select` exige une appartenance active et une organisation active. Un tenant par défaut devenu invalide n'ouvre pas automatiquement un autre tenant. Les ressources dont `organization_id` est nul sont invisibles aux endpoints tenant. Les UUID des ressources sont toujours vérifiés avec tenant et, pour les données personnelles, utilisateur.

| Ressource et action | Owner | Admin org | Member | Viewer | Anonyme |
| --- | --- | --- | --- | --- | --- |
| Organisation courante, contexte, membres : lire | Oui | Oui | Oui | Oui | Non |
| Organisation : créer et devenir owner | Oui | Oui | Oui | Oui | Non |
| Organisation : sélectionner parmi ses appartenances actives | Oui | Oui | Oui | Oui | Non |
| Invitation : créer / inviter | Oui | Oui | Non | Non | Non |
| Invitation : accepter pour son adresse et jeton valide | Oui | Oui | Oui | Oui | Non |
| Workspace, projets, alertes, profil : lire dans le tenant courant | Oui | Oui | Oui | Oui | Non |
| Workspace, projets, alertes, profil : créer / modifier / supprimer | Oui | Oui | Oui | Non | Non |
| Vue équipe, activité et reporting : lire dans le tenant courant | Oui | Oui | Oui | Oui | Non |
| Exports workspace et matching IA : exécuter selon abonnement | Oui | Oui | Oui | Non | Non |
| Abonnement et utilisation : consulter | Oui | Oui | Oui | Oui | Non |
| Checkout et portail Stripe : gérer | Oui | Non | Non | Non | Non |
| Catalogue public : liste / détail / recherche | Oui | Oui | Oui | Oui | Oui |
| Export CSV/Excel : plan Team ou supérieur | Oui | Oui | Oui | Non | Non |
| Fiches non publiées et opérations catalogue internes | Selon rôle plateforme | Selon rôle plateforme | Selon rôle plateforme | Selon rôle plateforme | Non |
| Administration Kafundo et sources : accès | Selon rôle plateforme | Selon rôle plateforme | Selon rôle plateforme | Selon rôle plateforme | Non |

« Selon rôle plateforme » signifie `admin` ou `editor` pour les lectures/écritures de fiches et de sources autorisées par leurs endpoints ; certaines opérations destructrices restent réservées à `admin`. La simple appartenance à une organisation ne confère aucun accès aux fiches non publiées. Les statuts `auto_published`, `approved`, `validated` sont publics ; `admin_only`, `pending_review`, `rejected` et tout statut inconnu ne le sont pas. Les filtres envoyés par le client ne peuvent pas élargir cette règle.

Depuis le Lot 4, les colonnes de rôle s'ajoutent aux droits du plan : l'export requiert `exports`, le matching `matching_ai`, le scoring `smart_scoring` et l'analyse IA `advanced_analysis`. Voir [billing-lot4.md](billing-lot4.md).

Décisions conservatrices en l'absence de règle produit explicite : facturation Stripe réservée à `org_owner` ; `viewer` en lecture seule pour les ressources métier ; `member` sans gestion des invitations ; statut de publication inconnu refusé ; administration globale jamais héritée du rôle d'organisation. La création d'une nouvelle organisation reste ouverte à tout utilisateur actif, conformément au parcours existant ; elle crée une nouvelle appartenance owner sans donner accès à une organisation existante.

Limites connues : des contraintes d'unicité historiques sont définies par utilisateur et dispositif, sans organisation, pour favoris/pipeline, et par utilisateur pour préférences. Lorsqu'un utilisateur partagé réutilise la même clé dans B, l'API refuse l'opération au lieu de modifier l'enregistrement de A. Une migration de ces contraintes sera nécessaire pour permettre ces doublons légitimes. La nouvelle migration `d742f48a3c19` ajoute `user_projects`, absent de l'inventaire initial du Lot 2 ; elle refuse un schéma où la table existerait déjà afin d'éviter un écrasement silencieux.
