#!/bin/bash
# ============================================================
# FinVeille — Script de démarrage rapide
# ============================================================
set -e

echo ""
echo "  FinVeille — Démarrage"
echo "=================================================="

# Vérification .env
if [ ! -f .env ]; then
  echo "⚠️  Fichier .env introuvable. Création depuis .env.example..."
  cp .env.example .env
  echo "✅  .env créé. Éditez-le avant de continuer si nécessaire."
fi

# Arrêter les processus existants avant toute migration.
docker compose stop celery-worker celery-beat backend
# La base et Redis démarrent seuls : aucun worker ne traite de tâches avant migration.
echo ""
echo "🐳 Démarrage de PostgreSQL et Redis..."
docker compose up -d postgres redis
docker compose build backend

# Attente base de données
echo ""
echo "⏳ Attente de PostgreSQL..."
sleep 5

# Migrations
echo ""
echo "📦 Application des migrations..."
docker compose run --rm --no-deps backend python -m migrations.upgrade

# L'API doit être prête avant les workers (depends_on: service_healthy).
docker compose up -d --build

# Seed
echo ""
echo "🌱 Initialisation des données..."
docker compose exec -T backend python -m app.data.seed

echo ""
echo "=================================================="
echo "  FinVeille est prêt !"
echo "=================================================="
echo ""
echo "  Frontend   : http://localhost:3000"
echo "  API docs   : http://localhost:8000/api/docs"
echo "  Flower     : http://localhost:5555"
echo ""
echo "  Compte admin : admin@finveille.com"
echo "  Mot de passe : Admin@2024!"
echo ""
echo "  ⚠️  Changez le mot de passe admin après connexion !"
echo ""
