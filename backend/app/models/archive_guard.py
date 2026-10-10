"""Garde-fou : une fiche archivée ne peut pas être réactivée « par accident ».

De nombreux scripts ponctuels (app/data/*) réaffectent ``validation_status`` par l'ORM. Sans
garde-fou, l'un d'eux pourrait remettre en ligne une fiche archivée par le nettoyage du
catalogue. Toute sortie de l'état ``archived`` doit passer par la restauration journalisée
(``catalog_cleanup.restore``), qui ouvre explicitement ``allow_unarchive()``.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import event

from app.models.catalog_cleanup import ARCHIVED_STATUS
from app.models.device import Device

_ALLOW_UNARCHIVE: ContextVar[bool] = ContextVar("allow_unarchive", default=False)


class ArchivedDeviceError(ValueError):
    """Tentative de modifier le statut d'une fiche archivée en dehors de la restauration."""


@contextmanager
def allow_unarchive():
    token = _ALLOW_UNARCHIVE.set(True)
    try:
        yield
    finally:
        _ALLOW_UNARCHIVE.reset(token)


@event.listens_for(Device.validation_status, "set", active_history=True)
def _forbid_silent_unarchive(target, value, oldvalue, initiator):
    if oldvalue == ARCHIVED_STATUS and value != ARCHIVED_STATUS and not _ALLOW_UNARCHIVE.get():
        raise ArchivedDeviceError(
            f"La fiche {getattr(target, 'id', '?')} est archivée: utiliser "
            "`python -m app.data.catalog_cleanup restore` (journalisé) pour la réactiver."
        )
