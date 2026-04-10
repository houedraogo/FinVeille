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

REM Build et démarrage des conteneurs
echo.
echo Demarrage des conteneurs Docker...
docker compose up -d --build
if %ERRORLEVEL% neq 0 (
    echo ERREUR : Docker compose a echoue.
    echo Verifiez que Docker Desktop est lance.
    pause
    exit /b 1
)

REM Attente base de données
echo.
echo Attente de PostgreSQL (10 secondes)...
timeout /t 10 /nobreak >nul

REM Migrations
echo.
echo Application des migrations Alembic...
docker compose exec backend alembic upgrade head
if %ERRORLEVEL% neq 0 (
    echo AVERTISSEMENT : Les migrations ont echoue. Retry dans 5s...
    timeout /t 5 /nobreak >nul
    docker compose exec backend alembic upgrade head
)

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
