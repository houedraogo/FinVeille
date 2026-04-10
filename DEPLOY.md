# Déploiement production

## 1. Préparer le serveur

Exemple Ubuntu :

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable docker
sudo systemctl start docker
```

## 2. Copier le projet

```bash
git clone <votre-repo> finveille
cd finveille
cp .env.production.example .env.production
nano .env.production
```

## 3. Vérifier les variables critiques

À changer impérativement :

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `SMTP_PASSWORD`
- les clés d'API tierces
- `NEXT_PUBLIC_API_URL`

## 4. Lancer la plateforme

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## 5. Vérifier l'état

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
```

## 6. Mettre à jour plus tard

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

## 7. Sauvegardes recommandées

- volume PostgreSQL
- fichier `.env.production`

## 8. Important

Le fichier `docker-compose.yml` actuel reste utile pour le développement.
Pour le serveur, utilisez `docker-compose.prod.yml`.
