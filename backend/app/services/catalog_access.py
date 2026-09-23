"""Server-side publication policy shared by public catalog paths."""
from app.models.device import Device
from app.models.user import User


PUBLIC_VALIDATION_STATUSES = ("auto_published", "approved", "validated")


def can_view_unpublished(user: User | None) -> bool:
    return bool(user and (user.role == "admin" or user.platform_role == "super_admin"))


def public_device_condition():
    return Device.validation_status.in_(PUBLIC_VALIDATION_STATUSES)


def may_view_device(device: Device, user: User | None) -> bool:
    return can_view_unpublished(user) or device.validation_status in PUBLIC_VALIDATION_STATUSES
