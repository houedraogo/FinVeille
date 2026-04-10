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

# Build et démarrage des conteneurs
echo ""
echo "🐳 Démarrage des conteneurs Docker..."
docker compose up -d --build

# Attente base de données
echo ""
echo "⏳ Attente de PostgreSQL..."
sleep 5

# Migrations
echo ""
echo "📦 Application des migrations..."
docker compose exec -T backend alembic upgrade head

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
