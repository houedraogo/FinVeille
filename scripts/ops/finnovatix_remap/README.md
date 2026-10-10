# Rétablissement des références Kafundo -> Finnovatix (`funding_calls.kafundo_id`)

**Statut : préparé et simulé. Rien n'a été écrit dans la base Finnovatix de production.** Toute exécution réelle
(`06_apply.sh --apply`) exige l'accord explicite du propriétaire et un créneau convenu.

## Pourquoi

La déduplication et les nettoyages du 1er octobre 2026 ont supprimé physiquement des fiches Kafundo. Finnovatix
conserve une copie locale (`funding_calls`) liée à Kafundo par `kafundo_id` (UNIQUE) ; ses dossiers clients pointent
vers `funding_calls.id`, pas vers `kafundo_id`. Résultat : **293** `funding_calls` ont un `kafundo_id` qui n'existe
plus dans Kafundo (elles ne reçoivent plus aucune mise à jour) :

| Origine | Nombre |
|---|---|
| Doublon CSV supprimé, fiche conservée équivalente (même source+URL+titre) | 248 |
| Idem, rapprochement par titre+organisme | 1 |
| Fiche sans équivalent (actualités FONSTI, titres empilés dont le titre d'origine est détruit) | 29 |
| Jamais présentes dans la sauvegarde du 25/09 (titres empilés synchronisés le 26-29/09) | 15 |

Impact côté clients : ~14 167 opportunités de dossiers reposent sur 1 518 `funding_calls`.

## Entrées de la campagne (dossier `AUDIT_DIR`, mode 0700)

* `finnovatix_protected_ids_missing_in_kafundo.txt` : identifiants `kafundo_id` de la liste de protection absents de
  Kafundo (293). Obtenus en restaurant une sauvegarde fraîche dans une base isolée et en comparant.
* `finnovatix_remap.csv` : `ancien_id -> fiche conservée` pour les fiches présentes dans la sauvegarde du 25/09
  (rapprochement source+URL+titre, puis titre+organisme), calculé sur la même copie isolée.
* `plan_*/` : plan de nettoyage (`catalog_cleanup plan`) utilisé pour savoir si un remplaçant est lui-même un
  doublon ou archivable.

`00_export_finnovatix.sh` ajoute l'état Finnovatix (lecture seule) ; `05_simulate.sh` produit la sauvegarde vérifiée.

## Ce que fait chaque étape (toutes en lecture seule sauf 06)

| # | Script | Rôle |
|---|---|---|
| 01 | `01_control.py` | Contrôle des correspondances ancien -> nouveau : conflits d'unicité, plusieurs anciens vers un même remplaçant, remplaçant lui-même doublon (lot C) ou archivable (lot A/B), remplaçant non public, usage client |
| 02 | `02_classify_no_equivalent.py` | Classe les références sans équivalent ; retrouve le titre d'origine dans la sauvegarde Kafundo d'avant suppression |
| 03 | `03_match_by_url.py` | Cherche un remplaçant par `source_url` pour les références sans équivalent par titre |
| 04 | `04_generate_sql.py` | Génère le plan d'actions, `finnovatix_apply.sql`, `finnovatix_apply_optional_M.sql` et le retour arrière **exact** (valeurs d'origine capturées) |
| 05 | `05_simulate.sh` | Sauvegarde vérifiée + simulation complète sur un MySQL jetable isolé : avant/après, rejeu, retour arrière, fusion optionnelle, exécuteur |
| 06 | `06_apply.sh` | Exécuteur **gardé** : simulation par défaut ; `--apply` / `--rollback` seulement avec accord ; vérifie aussi `KAFUNDO_SYNC_CREATE_CAP=0` et lance `07_verify.py` après application |
| 07 | `07_verify.py`, `07_simulate_sync.sh` | Vérification post-application (valeurs == API Kafundo, doublons, annotations) ; simulation complète avec le **vrai code Finnovatix** (artisan) sur copie jetable |
| 08 | `08_digest.sh` / `08_digest.php` | Synthèse par consultant (une notification par destinataire), simulation par défaut, rejouable, réversible |

## Matrice de traitement (293 références)

| Action | Nb | Traitement | Réversible |
|---|---|---|---|
| `R_remap` | 232 | `kafundo_id` ancien -> fiche conservée. Aucune autre colonne modifiée | oui (exact) |
| `R_remap_by_url` | 1 | idem, rapprochement par `source_url` (une seule fiche publique) | oui |
| `S_superseded_annotate` | 17 | Le remplaçant a **déjà** un `FundingCall` (doublon préexistant côté Finnovatix) : un `UPDATE` violerait l'unicité. Annotation `metadata.kafundo_superseded` uniquement, pas de changement de statut ni de dossier | oui |
| `K_keep_open_annotate` | 28 | Opportunité réelle à échéance future dont la fiche Kafundo a disparu : on **conserve** statut `open` et dossiers, annotation `metadata.kafundo_source_missing` | oui |
| `E_expired` | 9 | Échéance dépassée et fiche source disparue : `status='expired'` (cohérent avec la date), annotation avec `previous_status` | oui |
| `U_unknown_status` | 6 | Actualités FONSTI (pas des opportunités) : `status='unknown'` (valeur déjà utilisée par la synchro en l'absence de statut) -> sortent de `FundingCall::open()` ; dossiers conservés | oui |

Jamais de suppression. `funding_opportunities` et `marketing_contents` ne sont **pas** modifiées par l'application
principale.

### Fusion optionnelle (décision requise)

3 `FundingCall` (381, 384, 386) ont des dossiers alors que la fiche équivalente n'en a aucun : déplacer leurs
`funding_opportunities` / `marketing_contents` vers la cible est propre (aucun doublon créé dans un dossier).
Pour les 12 autres conflits, **les mêmes 9 dossiers portent déjà les deux fiches** : déplacer créerait des
opportunités dupliquées dans ces dossiers -> traités par annotation seulement ; un nettoyage fonctionnel des
dossiers est une décision produit distincte.

## Effets de bord à connaître avant d'appliquer

* **Notifications clients.** La synchro de 06:30 (`kafundo:sync-funding-calls --apply`) compare `deadline`,
  `funding_max`, `status` et notifie les dossiers qui suivent la fiche. Après rattachement, 19 fiches sur 232
  changeraient (9 statut, 7 montant max, 4 échéance), soit ~159 dossiers-opportunités à notifier. Choisir :
  laisser notifier (information réelle) ou appliquer dans une fenêtre où la synchro est suspendue et réaligner.
* **Aucun `save()` Eloquent.** Le hook `FundingCall::saved` (génération LinkedIn, notifications) ne se déclenche pas
  avec du SQL direct : ne pas passer par `tinker`/Eloquent pour cette opération.
* **Plafond de création.** `KAFUNDO_SYNC_CREATE_CAP=0` doit rester à 0 jusqu'à la fin ; le relever avant le
  rattachement créerait des doublons dans Finnovatix.
* **Replanifier le nettoyage Kafundo APRÈS** : les remplaçants seront alors des fiches référencées
  (`--protect-file` à régénérer), donc basculées en lots P/Q au lieu d'être archivées.

## Procédure

1. `01` -> `04` (lecture seule) puis `05_simulate.sh` : produit la sauvegarde vérifiée et le rapport
   `finnovatix_simulation_report.txt`. **Revue du rapport par le propriétaire.**
2. Créneau hors 06:15-06:55 (synchro) ; `KAFUNDO_SYNC_CREATE_CAP=0`.
3. `bash 06_apply.sh` (simulation) : contrôle sauvegarde < 3 h, état identique à la simulation, synchro hors cours.
4. Accord explicite -> `bash 06_apply.sh --apply` (taper `APPLY`). Transaction : une seule ligne hors état attendu
   => `ROLLBACK` complet. Rejeu sans effet.
5. Vérifier : doublons `kafundo_id` = 0, comptes dossiers/marketing inchangés (affichés avant/après).
6. Retour arrière à tout moment : `bash 06_apply.sh --rollback` (restitue les valeurs d'origine exactes).

## Résultat de la simulation du 10/10/2026 (copie jetable, production non modifiée)

| Mesure | Avant | Après |
|---|---|---|
| `funding_calls` | 1 775 | 1 775 |
| `kafundo_id` distincts | 1 775 | 1 775 |
| `funding_calls` dont `kafundo_id` absent de Kafundo | **293** | **60** |
| statuts `open` / `expired` / `unknown` | 1 547 / 0 / 0 | 1 532 / 9 / 6 |
| `funding_opportunities` (dossiers) | 14 167 | 14 167 (empreinte identique) |
| `marketing_contents` | 1 774 | 1 774 (empreinte identique) |
| doublons `kafundo_id` | 0 | 0 |
| rejeu de `finnovatix_apply.sql` | - | refusé : 293 lignes hors état attendu -> `ROLLBACK` |
| retour arrière | - | empreintes des 3 tables **identiques** à l'état initial |

Les 60 références qui gardent un `kafundo_id` absent de Kafundo sont **volontairement** conservées (jamais supprimées) :
43 sans équivalent exploitable (28 gardées ouvertes + annotées, 9 passées `expired`, 6 actualités en `unknown`) et
17 conflits d'unicité (doublons préexistants côté Finnovatix, annotés). Le 44ᵉ « sans équivalent » est rattaché par URL.

## Notifications : mécanisme retenu (réalignement silencieux + synthèse)

* Le rattachement SQL ne notifie personne. Les notifications « Modification détectée » ne viennent que de la synchro de
  06:30, qui compare `deadline`, `funding_max`, `status` à l'API Kafundo.
* Dans la **même transaction** que le rattachement, les fiches qui seraient notifiées reçoivent les valeurs de la source
  (`silent_realign`), l'ancienne valeur est inscrite dans `metadata.change_history` et `metadata.kafundo_remap`
  (ancien `kafundo_id`, run). La synchro suivante ne voit aucune différence : 0 notification pour ces fiches.
* Après vérification : `08_digest.sh --apply` crée **une** notification de synthèse par destinataire (dossiers + changements).
  `08_digest.sh --rollback` retire uniquement les synthèses de ce run.
* Les changements ultérieurs réels restent détectés (testé).

### Simulation du 10/10/2026 (copie jetable ; code Finnovatix réel en lecture seule ; API Kafundo figée) — tous les contrôles passent

| Contrôle | Résultat |
|---|---|
| Valeurs des fiches rattachées == API Kafundo (233 fiches ; 175 identiques, 58 absentes de la liste de l'API donc jamais synchronisées) | OK |
| Notifications créées par l'opération | 0 ; aucune tâche en file |
| Synchro suivante vs synchro de référence (sans opération) | identique (36 / 36, même empreinte) |
| Historique `silent_realign` après la synchro | conservé |
| Changement futur simulé (échéance) sur 2 fiches | 2 changements détectés, 18 notifications (une par dossier suivi), historique cumulatif |
| Synthèse | 1 destinataire (1 seul utilisateur), 3 dispositifs / 27 dossiers ; rejeu : 0 doublon |
| Rejeu du SQL principal | refusé (`ROLLBACK`) |
| Retour arrière (synthèses + SQL) | empreintes `funding_calls`, `funding_opportunities`, `marketing_contents`, `notifications`, `jobs` identiques à l'état initial |

### Écart avec l'estimation précédente (« 19 fiches »)

L'estimation de 19 fiches comparait toutes les fiches de remplacement. La synchro, elle, ne lit que la liste publique de
l'API : sur les 233 rattachements, **3** fiches changeraient réellement (2 échéances, 1 statut), **58** ne sont pas dans la
liste (jamais synchronisées, donc jamais notifiées ; 33 pointent vers une fiche non publique, 5 ont des écarts de valeurs
listés dans `finnovatix_not_synced_changes.csv`, non réalignés par cette opération).
