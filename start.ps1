# FinVeille — Script de demarrage (PowerShell)
# Lancement : .\start.ps1  (ou clic droit > Executer avec PowerShell)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  FinVeille — Demarrage" -ForegroundColor Cyan
Write-Host "=================================================="

# .env
if (-not (Test-Path ".env")) {
    Write-Host "Fichier .env introuvable. Creation depuis .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host ".env cree." -ForegroundColor Green
}

# Docker Compose
Write-Host ""
Write-Host "Demarrage des conteneurs Docker..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERREUR Docker. Verifiez que Docker Desktop est lance." -ForegroundColor Red
    Read-Host "Appuyez sur Entree pour quitter"
    exit 1
}

# Attente PostgreSQL
Write-Host ""
Write-Host "Attente de PostgreSQL (12 secondes)..." -ForegroundColor Yellow
Start-Sleep -Seconds 12

# Migrations
Write-Host ""
Write-Host "Application des migrations..." -ForegroundColor Cyan
docker compose exec backend alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "Retry migrations dans 5s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    docker compose exec backend alembic upgrade head
}

# Seed
Write-Host ""
Write-Host "Initialisation des donnees..." -ForegroundColor Cyan
docker compose exec backend python -m app.data.seed

Write-Host ""
Write-Host "=================================================="
Write-Host "  FinVeille est pret !" -ForegroundColor Green
Write-Host "=================================================="
Write-Host ""
Write-Host "  Frontend   : http://localhost:3000" -ForegroundColor White
Write-Host "  API docs   : http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "  Flower     : http://localhost:5555" -ForegroundColor White
Write-Host ""
Write-Host "  Admin      : admin@finveille.com" -ForegroundColor Yellow
Write-Host "  Password   : Admin@2024!" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Changez le mot de passe apres connexion !" -ForegroundColor Red
Write-Host ""
Read-Host "Appuyez sur Entree pour fermer"
