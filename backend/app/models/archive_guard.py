"""Garde-fous sur les fiches archivées : ni réactivation « par accident », ni suppression physique.

1. Réactivation. De nombreux scripts ponctuels (app/data/*) réaffectent ``validation_status`` par l'ORM.
   Sans garde-fou, l'un d'eux pourrait remettre en ligne une fiche archivée par le nettoyage du catalogue.
   Toute sortie de l'état ``archived`` doit passer par la restauration journalisée
   (``catalog_cleanup.restore``), qui ouvre explicitement ``allow_unarchive()``.

2. Suppression physique. Une fiche archivée, ou qui porte un journal d'archivage (``device_archive_log``),
   ou qui est la fiche conservée d'un doublon archivé, ne peut pas être supprimée par l'ORM : la clé
   étrangère du journal cascadait, donc supprimer la fiche effaçait le journal qui permet de la restaurer et
   rompait les références externes (dossiers Finnovatix via ``kafundo_id``). Les ``DELETE`` SQL directs sont
   arrêtés par la contrainte ``RESTRICT`` (migration c8e1f4a7b2d9). Un outil d'exploitation délibéré peut
   ouvrir ``allow_journaled_delete()`` ; aucun chemin applicatif ne le fait.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import event, text

from app.models.catalog_cleanup import ARCHIVED_STATUS
from app.models.device import Device

_ALLOW_UNARCHIVE: ContextVar[bool] = ContextVar("allow_unarchive", default=False)
_ALLOW_JOURNALED_DELETE: ContextVar[bool] = ContextVar("allow_journaled_delete", default=False)


class ArchivedDeviceError(ValueError):
    """Tentative de modifier le statut d'une fiche archivée en dehors de la restauration."""


class DeviceDeletionForbidden(ValueError):
    """Suppression physique refusée : fiche archivée ou porteuse d'un journal d'archivage."""


@contextmanager
def allow_unarchive():
    token = _ALLOW_UNARCHIVE.set(True)
    try:
        yield
    finally:
        _ALLOW_UNARCHIVE.reset(token)


@contextmanager
def allow_journaled_delete():
    token = _ALLOW_JOURNALED_DELETE.set(True)
    try:
        yield
    finally:
        _ALLOW_JOURNALED_DELETE.reset(token)


@event.listens_for(Device.validation_status, "set", active_history=True)
def _forbid_silent_unarchive(target, value, oldvalue, initiator):
    if oldvalue == ARCHIVED_STATUS and value != ARCHIVED_STATUS and not _ALLOW_UNARCHIVE.get():
        raise ArchivedDeviceError(
            f"La fiche {getattr(target, 'id', '?')} est archivée: utiliser "
            "`python -m app.data.catalog_cleanup restore` (journalisé) pour la réactiver."
        )


@event.listens_for(Device, "before_delete")
def _forbid_physical_delete_of_journaled(mapper, connection, target):
    if _ALLOW_JOURNALED_DELETE.get():
        return
    if target.validation_status == ARCHIVED_STATUS:
        raise DeviceDeletionForbidden(f"La fiche {target.id} est archivée: suppression physique refusée.")
    hit = connection.execute(
        text("SELECT 1 FROM device_archive_log WHERE device_id = :i OR merged_into_id = :i LIMIT 1"),
        {"i": target.id},
    ).first()
    if hit is not None:
        raise DeviceDeletionForbidden(
            f"La fiche {target.id} porte un journal d'archivage (ou est la fiche conservée d'un doublon archivé): "
            "suppression physique refusée."
        )
