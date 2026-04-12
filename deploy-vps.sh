#!/bin/bash
# ================================================
# FinVeille — Script de déploiement VPS Hostinger
# Domaine : finveille.hamed-vps.cloud
# IP VPS  : 145.223.103.103 (Ubuntu 24.04 + FASTPANEL)
# ================================================
set -e

DOMAIN="finveille.hamed-vps.cloud"
REPO="https://github.com/houedraogo/FinVeille.git"
APP_DIR="/opt/finveille"

echo ""
echo "========================================"
echo "  FinVeille — Déploiement Production"
echo "  Domaine : $DOMAIN"
echo "========================================"
echo ""

# 1. Vérification root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Ce script doit être exécuté en root (sudo bash deploy-vps.sh)"
    exit 1
fi

# 2. Installation des dépendances système
echo ">>> [1/6] Installation de Docker et Git..."
apt update -qq
apt install -y docker.io docker-compose-plugin git curl

systemctl enable docker --now
echo "✅ Docker $(docker --version | cut -d' ' -f3) installé"

# 3. Clone ou mise à jour du dépôt
echo ""
echo ">>> [2/6] Récupération du code source depuis GitHub..."
if [ -d "$APP_DIR/.git" ]; then
    echo "    Répertoire existant, mise à jour..."
    git -C "$APP_DIR" pull
else
    git clone "$REPO" "$APP_DIR"
fi
echo "✅ Code source à jour dans $APP_DIR"

cd "$APP_DIR"

# 4. Configuration de l'environnement
echo ""
echo ">>> [3/6] Configuration de l'environnement production..."
if [ ! -f ".env.production" ]; then
    cp .env.production.example .env.production

    # Génération automatique des secrets
    SECRET_KEY=$(openssl rand -hex 32)
    DB_PASS=$(openssl rand -base64 20 | tr -d '=+/' | head -c 20)
    REDIS_PASS=$(openssl rand -base64 16 | tr -d '=+/' | head -c 16)

    sed -i "s|replace-with-a-long-random-secret|$SECRET_KEY|g" .env.production
    sed -i "s|replace-with-a-strong-db-password|$DB_PASS|g" .env.production
    sed -i "s|replace-with-a-strong-redis-password|$REDIS_PASS|g" .env.production
    sed -i "s|https://your-domain.com|https://$DOMAIN|g" .env.production

    echo ""
    echo "⚠️  Fichier .env.production créé avec des secrets auto-générés."
    echo ""
    echo "    Vous DEVEZ encore configurer :"
    echo "    - SMTP_HOST / SMTP_USER / SMTP_PASSWORD (service email)"
    echo "    - EMAIL_FROM (ex: noreply@$DOMAIN)"
    echo "    - OPENAI_API_KEY ou MISTRAL_API_KEY (optionnel)"
    echo ""
    echo "    Editez maintenant : nano $APP_DIR/.env.production"
    echo ""
    read -p "    Appuyez sur Entrée quand vous avez fini d'éditer .env.production..."
else
    echo "    .env.production existant conservé."
    # Mise à jour de l'URL du domaine si nécessaire
    sed -i "s|NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=https://$DOMAIN|g" .env.production
fi
echo "✅ Environnement configuré"

# 5. Build et démarrage des conteneurs Docker
echo ""
echo ">>> [4/6] Build et démarrage des services Docker..."
echo "    (cela peut prendre 5-10 minutes la première fois)"
docker compose -f docker-compose.prod.yml up -d --build
echo "✅ Services Docker démarrés"

# 6. Vérification de la santé des services
echo ""
echo ">>> [5/6] Vérification des services..."
sleep 10

if docker compose -f docker-compose.prod.yml ps | grep -q "unhealthy"; then
    echo "⚠️  Certains services ne sont pas encore sains. Vérifiez avec :"
    echo "    docker compose -f docker-compose.prod.yml ps"
    echo "    docker compose -f docker-compose.prod.yml logs backend"
else
    echo "✅ Tous les services sont opérationnels"
fi

# 7. Instructions FASTPANEL
echo ""
echo ">>> [6/6] Configuration FASTPANEL requise"
echo ""
echo "========================================================"
echo "  CONFIGURATION FASTPANEL (à faire dans l'interface)"
echo "========================================================"
echo ""
echo "  L'app tourne sur le port interne 8080."
echo "  Configurez FASTPANEL pour proxifier le domaine :"
echo ""
echo "  1. Connectez-vous à FASTPANEL"
echo "     (votre-ip:8888 ou via Hostinger hPanel > VPS > FASTPANEL)"
echo ""
echo "  2. Allez dans 'Sites web' > 'Ajouter un site'"
echo "     - Domaine : $DOMAIN"
echo "     - Type    : Reverse Proxy / Proxy"
echo "     - URL cible: http://127.0.0.1:8080"
echo ""
echo "  3. Dans les paramètres SSL du site :"
echo "     - Activez Let's Encrypt (SSL gratuit)"
echo "     - Cochez 'Rediriger HTTP vers HTTPS'"
echo ""
echo "  4. Sauvegardez et attendez l'émission du certificat SSL"
echo ""
echo "========================================================"
echo ""
echo "  Une fois FASTPANEL configuré, votre app sera accessible à :"
echo "  https://$DOMAIN"
echo ""
echo "  API docs : https://$DOMAIN/api/docs"
echo ""
echo "  Logs     : docker compose -f $APP_DIR/docker-compose.prod.yml logs -f"
echo "  Status   : docker compose -f $APP_DIR/docker-compose.prod.yml ps"
echo "========================================================"
echo ""
