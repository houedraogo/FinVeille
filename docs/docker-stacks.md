# Docker stacks locaux

Le projet Kafundo utilise un seul projet Docker Compose nommé `kafundo`.

## Stack attendu

Les conteneurs attendus pour ce dépôt sont :

- `kafundo-backend`
- `kafundo-frontend`
- `kafundo-postgres`
- `kafundo-redis`
- `kafundo-worker`
- `kafundo-beat`
- `kafundo-flower`
- `kafundo-mailhog`

## Diagnostic

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker compose config --services
docker compose ps
```

Si des conteneurs `finveille-*` ou `fasodata-*` tournent en parallèle, ils viennent d'anciens stacks ou d'autres projets locaux. Ils peuvent créer de la confusion sur les ports, les logs et les commandes `docker exec`.

## Nettoyage non destructif

Avant de supprimer quoi que ce soit, arrêter seulement les anciens conteneurs :

```powershell
docker stop $(docker ps -q --filter "name=fasodata")
docker stop $(docker ps -q --filter "name=finveille")
```

Ne pas supprimer les volumes sans sauvegarde explicite. Les données PostgreSQL peuvent s'y trouver.

Pour redémarrer uniquement Kafundo :

```powershell
docker compose up -d --build
```
