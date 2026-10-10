"""Beat ne doit jamais relancer en bloc les taches periodiques au demarrage d'un conteneur neuf.

Constat du 10/10/2026 : `backend/celerybeat-schedule` (fichier shelve d'ordonnancement, last_run_at = 25/04/2026) etait
versionne et copie dans l'image ; au premier demarrage, les 10 taches "dues" sont parties d'un coup (collectes x3, alertes,
enrichissement, qualite...). Garde-fous : le fichier n'est plus versionne ni copie, et beat ecrit son ordonnancement hors
du code (`beat_schedule_filename`)."""
import os
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from celery.beat import Scheduler

from app.tasks.celery_app import celery_app

BACKEND = Path(__file__).resolve().parents[1]


def _scheduler():
    """Ordonnanceur en memoire avec le calendrier reel de l'application (pas de fichier : l'etat initial est celui d'un
    conteneur neuf)."""
    return Scheduler(app=celery_app)


def test_schedule_file_is_outside_the_code_tree():
    name = Path(celery_app.conf.beat_schedule_filename)
    assert name.is_absolute(), "chemin relatif : serait resolu dans /app (code de l'image)"
    assert BACKEND not in name.parents and not str(name).startswith("/app"), name


def test_no_schedule_file_is_tracked_or_shipped():
    dockerignore = (BACKEND / ".dockerignore").read_text(encoding="utf-8")
    assert "celerybeat-schedule" in dockerignore
    try:
        tracked = subprocess.run(["git", "ls-files", "backend/celerybeat-schedule*", "celerybeat-schedule*"],
                                 cwd=BACKEND.parent, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git indisponible")
    assert tracked == [], f"fichier d'ordonnancement versionne : {tracked}"


def test_fresh_container_fires_nothing_at_startup():
    scheduler = _scheduler()
    assert len(scheduler.schedule) >= 15, "calendrier incomplet"
    due = [name for name, entry in scheduler.schedule.items() if entry.is_due().is_due]
    assert due == [], f"taches lancees au demarrage : {due}"


def test_a_stale_last_run_would_fire_everything_which_is_why_the_file_is_never_loaded():
    """Documente le mode de defaillance : avec un ancien last_run_at, les taches sont toutes dues."""
    scheduler = _scheduler()
    for entry in scheduler.schedule.values():
        entry.last_run_at = entry.last_run_at - timedelta(days=170)
    due = [n for n, e in scheduler.schedule.items() if e.is_due().is_due]
    assert len(due) >= 10
