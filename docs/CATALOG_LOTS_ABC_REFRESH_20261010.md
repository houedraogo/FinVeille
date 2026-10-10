# Actualisation des lots A / B / C (plan du 10/10/2026 13:25 UTC) — lecture seule, rien archivé

Plan recalculé sur 7 682 fiches avec 2 008 références externes protégées (kafundo_id Finnovatix actuels + 233 cibles de
rattachement prévues). Manifestes : `/opt/finveille-backups/audit_20261010/plan_20261010_1325/` (0600).

| Lot | Effectif | Empreinte | Fiches publiques (validation) | Listées dans l'API | Précédent (08:04) |
|---|---|---|---|---|---|
| A projets institutionnels | 1 127 | `a3894c90e3868915` | 9 | 0 | 1 127 |
| B expirées non récurrentes | 618 | `44246f36eedcee5b` | 176 | 0 | 619 |
| C doublons certains | 114 | `0b1f3db7066bb11d` | 92 | 68 | 114 |
| P doublons référencés (non archivés) | 51 | `0706b926b8c8138b` | 51 | 51 | — |
| Q A/B référencés, à arbitrer (non archivés) | 42 | `39d730343a2e2fa0` | 22 | 0 | — |
| F / G / H / Z (non archivables) | 370 / 43 / 102 / 5 215 | | | | |

* Chevauchements (critères évalués indépendamment) : A∩B = 205, A∩C = 1, B∩C = 14, A∩B∩C = 0 ; union 1 962. Le plan affecte chaque
  fiche à un seul lot (priorité A > rejetées > B > C), total archivable A+B+C = 1 859.
* Références externes : 0 fiche de A/B/C protégée ; 0 ligne `favorite_devices`, `device_pipeline`, `alert_deliveries`,
  `device_duplicate_candidates` sur les fiches A/B/C ; 571 fiches A/B/C déjà journalisées `ai_hold`.
* Fiches publiques : seules 68 fiches de A/B/C sont aujourd'hui listées par l'API (toutes du lot C : doublons de
  data.aides-entreprises.fr / Global South Opportunities) ; 0 doublon public dont la fiche conservée serait non publique.
  Les 9 fiches publiques du lot A sont des projets Banque Mondiale / AFD (6 `open`, 2 `expired`, 1 `standby`) : à confirmer.
* Lot Q : 42 fiches expirées/fermées référencées par des dossiers Finnovatix → décision humaine (conservées).

## Protocole d'archivage (à lancer seulement après validation) — réversible
1. Sauvegarde `pg_dump -Fc` + sha256 + restauration testée (`scripts/ops/migration_prevalidation.sh`).
2. `plan --protect-file` → vérifier les empreintes ci-dessus ; `hold-ai` si besoin.
3. `apply --batch A… --plan-hash <empreinte> --run-id … --backup-ref …` (simulation sans `--yes`), puis B, puis C.
4. Contrôles entre lots (comptes, API, références), journal `device_archive_log`, `restore --run-id …` possible.

## Revue individuelle des 9 fiches publiques du lot A (exclues provisoirement ; rien archivé)

Analyse faite sur le contenu Kafundo (description, dates, type, source). Aucune n'est un appel à candidatures : ce sont des
enregistrements de projets déjà approuvés (Banque Mondiale : « date d'approbation » et « clôture prévisionnelle » = fin du projet,
pas date limite de dépôt ; AFD : financement souverain).

| # | Fiche | Statut | Clôture | Nature | Verdict proposé |
|---|---|---|---|---|---|
| 1 | Guinée – Deuxième financement additionnel COVID-19 (P178602) | expired | 30/06/2024 | projet approuvé, terminé | archiver (lot A) |
| 2 | Guinée – Financement supplémentaire COVID-19 (P176706) | expired | 30/06/2024 | projet approuvé, terminé | archiver (lot A) |
| 3 | AFD – FMT, appui budgétaire transition verte, Monténégro | expired | 15/12/2024 | financement souverain (100 M€), terminé | archiver (lot A) |
| 4 | Togo – Réponse d'urgence contingente CERP (P515227) | open | 30/04/2032 | instrument d'urgence de l'État, approuvé 14/05/2026 | archiver (déjà financé, pas d'appel) |
| 5 | Rwanda – Réponse d'urgence par contingent (P510931) | open | 01/12/2031 | instrument d'urgence de l'État | archiver |
| 6 | Maroc – Opération de politique de développement, emploi et croissance verte (P513503) | open | 30/06/2027 | prêt de politique publique à l'État | archiver |
| 7 | Éthiopie – 2e programme d'action communautaire, paysages (P510697) | open | 29/08/2031 | programme axé sur résultats, mise en œuvre étatique | archiver (ou signal « veille ») |
| 8 | Madagascar – accélérer l'accès à une énergie durable (P515164) | open | 30/06/2030 | projet approuvé 04/05/2026 ; volets privés possibles via l'agence d'exécution, aucun appel documenté | **revue humaine** : conserver hors lot, vérifier la source |
| 9 | Rwanda – Entrepreneuriat numérique des jeunes urbains DEVY (P510000) | standby | — | projet approuvé 09/04/2026 ; type « subvention », volet entrepreneurs possible, aucune ouverture | **revue humaine** : conserver hors lot, vérifier la source |

Synthèse : 7 fiches sont des projets institutionnels déjà financés ou terminés (aucun appel accessible) ; 2 (n° 8 et 9) peuvent
déboucher sur des guichets pour entrepreneurs via l'agence d'exécution mais aucun n'est ouvert à ce jour : à reclasser en
« signal » plutôt qu'« opportunité ouverte ». Limite : l'analyse repose sur les données Kafundo ; la page source de n° 8 et 9
reste à consulter avant décision.
