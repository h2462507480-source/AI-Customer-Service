from __future__ import annotations

from .admin_catalog import AdminCatalogMixin
from .admin_core import AdminCoreMixin
from .admin_operations import AdminOperationsMixin


class AdminService(AdminCatalogMixin, AdminOperationsMixin, AdminCoreMixin):
    """Management API for the desktop UI and local administration tools."""


__all__ = ["AdminService"]
