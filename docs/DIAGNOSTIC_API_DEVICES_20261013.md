# Diagnostic de la lenteur de `GET /api/v1/devices/` (13/10/2026 05:00–05:30 UTC) — lecture seule

## Mesures (production, aucune écriture)
| Mesure | Résultat |
|---|---|
| HTTP `page_size=100`, pages 1/2/10/30 (3 passes) | 6,7 à 15,9 s par requête |
| `page_size=20` / `page_size=1` | 10,5 s / 7,7 s (donc quasi indépendant du nombre de lignes) |
| `?q=energie` | 30 s |
| `/api/v1/devices/stats` | 3,9 s |
| `/api/health` (sans base) | 7 ms |
| Dans l'application (page 1, 100) | recherche 18,5 s = `count(*)` 6,1 s + page 3,2 s + attente ; sérialisation 123 ms |
| Dans l'application (page 10 ; 1/1 ; 1/20) | 7,4 s (3,6 + 3,4) ; 6,6 s (3,5 + 2,4) ; 4,9 s (3,1 + 1,6) |
| `EXPLAIN (ANALYZE, BUFFERS)` comptage | 2,8 s d'exécution, planification 94 ms, 14 736 buffers pour 2 155 pages de table (3 186 + 854 lignes filtrées) |
| `EXPLAIN (ANALYZE, BUFFERS)` page | 2,0 s, même plan (BitmapAnd `validation_status` + `status`, tri top-N) |

La requête exécutée deux fois par appel (comptage + page) applique le filtre de visibilité par défaut : `length(coalesce(...))` sur
`short_description`, `auto_summary`, `full_description`, `funding_details`, `specific_conditions`, `required_documents`,
`eligibility_criteria`, `source_url`, plus 4 `NOT ILIKE` sur le titre. Ces calculs obligent à lire/décompresser les colonnes TOAST
de chaque ligne candidate (≈ 4 000) et ne peuvent pas utiliser d'index : coût intrinsèque environ 0,5 à 1 s par requête sur une
machine saine, 2 par appel.

## Cause principale : machine saturée, non liée à l'archivage
* Charge 294–310 sur 2 vCPU ; `steal` 73–75 % ; RAM libre 128 Mo ; swap 4/4 Go plein (si/so 600–1 600 pages/s) ; 255 processus
  en état D ; PSI CPU/mémoire/E-S « some » ≈ 83–99 % ; OOM-kills répétés dans un autre conteneur.
* Processus dominant : `/tmp/hasaneyoh -o 157.230.47.83:10008 -u … -k` (profil de mineur de cryptomonnaie), 128 % CPU, 2,1 Go RSS
  (26 % de la RAM), lancé le 12/10 23:24:22 UTC, dans le conteneur **`fasodata-web-1`** (projet FasoData, `next-server`), qui est
  rattaché au réseau Docker **`kafundo_default`**. Le même conteneur héberge `/tmp/safenet-client` depuis le 15/09 23:45.
* Historique comparable : pas de mesure stockée ; indirectement, les parcours de 33 pages du script de migration (12/10 07:11) et du
  pilote (12/10 21:16) se sont déroulés en quelques secondes au total (< 1 s par page). Le mineur n'est apparu qu'à 23:24, après le pilote.
* Reproductible : 100 % des requêtes mesurées entre 05:06 et 05:25.

## Corrections recommandées (aucune appliquée)
1. **Incident (décision du propriétaire FasoData)** : isoler/arrêter `fasodata-web-1`, conserver les preuves (`docker export`, journaux),
   reconstruire l'image depuis une source saine, patcher Next.js, faire tourner les secrets FasoData, retirer ce conteneur du réseau
   `kafundo_default`. Risque : indisponibilité de FasoData.
2. **Kafundo** : considérer les secrets Kafundo accessibles depuis ce réseau comme exposés (rotation, chantier distinct).
3. **Requête** (après retour à la normale) : mettre en cache le total (TTL 30–60 s) ou le calculer par fenêtre ; matérialiser le
   filtre de visibilité dans une colonne booléenne maintenue à l'écriture avec index partiel ; `work_mem` 4 Mo → 16–32 Mo
   (9,8 Go de fichiers temporaires). Risques : migration + dérive possible du booléen si une écriture l'oublie ; à tester sur copie.
4. **Capacité** : 8 Go de RAM partagés entre ~36 conteneurs : surveiller swap/steal, limites mémoire par conteneur.
