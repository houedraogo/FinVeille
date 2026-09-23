# Kafundo - Script de demarrage (PowerShell)
# Lancement : .\start.ps1  (ou clic droit > Executer avec PowerShell)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Kafundo - Demarrage" -ForegroundColor Cyan
Write-Host "=================================================="

# .env
if (-not (Test-Path ".env")) {
    Write-Host "Fichier .env introuvable. Creation depuis .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host ".env cree." -ForegroundColor Green
}

# Docker Compose
Write-Host ""
docker compose stop celery-worker celery-beat backend
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Host "Demarrage de PostgreSQL et Redis..." -ForegroundColor Cyan
docker compose up -d postgres redis
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERREUR Docker. Verifiez que Docker Desktop est lance." -ForegroundColor Red
    Read-Host "Appuyez sur Entree pour quitter"
    exit 1
}
docker compose build backend
if ($LASTEXITCODE -ne 0) { exit 1 }

# Attente PostgreSQL
Write-Host ""
Write-Host "Attente de PostgreSQL (12 secondes)..." -ForegroundColor Yellow
Start-Sleep -Seconds 12

# Migrations
Write-Host ""
Write-Host "Application des migrations..." -ForegroundColor Cyan
docker compose run --rm --no-deps backend python -m migrations.upgrade
if ($LASTEXITCODE -ne 0) {
    Write-Host "Migration arretee. Pour une base existante, sauvegarder puis suivre la procedure Lot 2." -ForegroundColor Red
    exit 1
}
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit 1 }

# Seed
Write-Host ""
Write-Host "Initialisation des donnees..." -ForegroundColor Cyan
docker compose exec backend python -m app.data.seed

Write-Host ""
Write-Host "=================================================="
Write-Host "  Kafundo est pret !" -ForegroundColor Green
Write-Host "=================================================="
Write-Host ""
Write-Host "  Frontend   : http://localhost:3000" -ForegroundColor White
Write-Host "  API docs   : http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "  Flower     : http://localhost:5555" -ForegroundColor White
Write-Host ""
Write-Host "  Admin      : admin@kafundo.com" -ForegroundColor Yellow
Write-Host "  Password   : Admin@2024!" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Changez le mot de passe apres connexion !" -ForegroundColor Red
Write-Host ""
Read-Host "Appuyez sur Entree pour fermer"

