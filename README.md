# Kafundo

Plateforme de veille sur les dispositifs de financement public — **France & Afrique**

## Démarrage rapide

### Prérequis
- Docker + Docker Compose
- Node.js 20+ (développement frontend local)

### Lancement

```bash
# 1. Cloner et aller dans le projet
cd kafundo

# 2. Copier la configuration
cp .env.example .env
# Éditez .env si besoin (optionnel pour le dev)

# 3. Démarrer tout le stack
bash start.sh
```

L'application sera accessible sur :
- **Frontend** : http://localhost:3000
- **API** : http://localhost:8000/api/docs
- **Workers** : http://localhost:5555 (Flower)

Identifiants par défaut :
- Email : `admin@kafundo.com`
- Mot de passe : `Admin@2024!`

> ⚠️ Changez le mot de passe admin dès la première connexion en production.

---

## Architecture

```
kafundo/
├── backend/           # FastAPI + Celery
│   ├── app/
│   │   ├── models/        # Modèles SQLAlchemy
│   │   ├── schemas/       # Validation Pydantic
│   │   ├── routers/       # Endpoints API
│   │   ├── services/      # Logique métier
│   │   ├── collector/     # Moteur de collecte
│   │   ├── tasks/         # Workers Celery
│   │   └── data/          # Seed & données initiales
│   └── migrations/    # Alembic
├── frontend/          # Next.js 14
│   └── src/
│       ├── app/           # Pages (App Router)
│       ├── components/    # Composants réutilisables
│       └── lib/           # API client, types, utils
└── docker-compose.yml
```

## Stack technique

| Composant | Technologie |
|---|---|
| Backend API | Python 3.11 + FastAPI |
| Base de données | PostgreSQL 15 |
| Cache / Queue | Redis 7 |
| Workers | Celery 5 + Celery Beat |
| Frontend | Next.js 14 + TypeScript + Tailwind |
| Conteneurisation | Docker Compose |

## Endpoints API principaux

| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Authentification |
| GET | `/api/v1/devices/` | Liste avec filtres |
| GET | `/api/v1/devices/stats` | KPIs dashboard |
| GET | `/api/v1/devices/{id}` | Fiche détaillée |
| POST | `/api/v1/devices/` | Ajout manuel |
| GET | `/api/v1/devices/export/csv` | Export CSV |
| GET | `/api/v1/sources/` | Liste des sources |
| POST | `/api/v1/sources/{id}/collect` | Collecte manuelle |
| GET | `/api/v1/alerts/` | Alertes utilisateur |
| GET | `/api/v1/dashboard/` | Données dashboard |
| GET | `/api/v1/admin/quality` | Rapport qualité |
| GET | `/api/health` | Santé API |

## Développement

```bash
# Backend uniquement (sans Docker)
cd backend
pip install -r requirements.txt
alembic upgrade head
python -m app.data.seed
uvicorn app.main:app --reload

# Worker Celery
celery -A app.tasks.celery_app worker --loglevel=info

# Frontend uniquement
cd frontend
npm install
npm run dev
```

## Ajouter une source

Via l'interface admin ou via l'API :

```bash
curl -X POST http://localhost:8000/api/v1/sources/ \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Nom de la source",
    "organism": "Organisme",
    "country": "France",
    "source_type": "institution_publique",
    "level": 2,
    "url": "https://exemple.fr/aides",
    "collection_mode": "html",
    "check_frequency": "daily",
    "reliability": 4,
    "config": {
      "list_selector": ".aides-list article",
      "item_title_selector": "h3",
      "item_link_selector": "a"
    }
  }'
```

## Déclencher une collecte manuelle

```bash
curl -X POST http://localhost:8000/api/v1/sources/<SOURCE_ID>/collect \
  -H "Authorization: Bearer <TOKEN>"
```
