@echo off
chcp 65001 >nul
echo.
echo   FinVeille — Demarrage
echo ==================================================

REM Vérification .env
if not exist .env (
    echo Fichier .env introuvable. Creation depuis .env.example...
    copy .env.example .env
    echo .env cree. Editez-le si necessaire.
)

REM PostgreSQL et Redis seuls avant toute migration ou démarrage des workers
docker compose stop celery-worker celery-beat backend
if %ERRORLEVEL% neq 0 exit /b 1
echo.
echo Demarrage de PostgreSQL et Redis...
docker compose up -d postgres redis
if %ERRORLEVEL% neq 0 (
    echo ERREUR : Docker compose a echoue.
    echo Verifiez que Docker Desktop est lance.
    pause
    exit /b 1
)
docker compose build backend
if %ERRORLEVEL% neq 0 exit /b 1

REM Attente base de données
echo.
echo Attente de PostgreSQL (10 secondes)...
timeout /t 10 /nobreak >nul

REM Migrations
echo.
echo Application des migrations Alembic...
docker compose run --rm --no-deps backend python -m migrations.upgrade
if %ERRORLEVEL% neq 0 (
    echo Migration arretee. Sauvegarder une base existante puis suivre la procedure Lot 2.
    exit /b 1
)
docker compose up -d --build
if %ERRORLEVEL% neq 0 exit /b 1

REM Seed
echo.
echo Initialisation des donnees (sources + admin)...
docker compose exec backend python -m app.data.seed

echo.
echo ==================================================
echo   FinVeille est pret !
echo ==================================================
echo.
echo   Frontend   : http://localhost:3000
echo   API docs   : http://localhost:8000/api/docs
echo   Flower     : http://localhost:5555
echo.
echo   Compte admin : admin@finveille.com
echo   Mot de passe : Admin@2024!
echo.
echo   ATTENTION : Changez le mot de passe admin apres connexion !
echo.
pause
