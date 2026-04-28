from rest_framework.permissions import BasePermission


class IsProjectOwner(BasePermission):
    """Erlaubt Zugriff nur auf eigene MagvisProject-Objekte."""

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, 'user', None)
        if owner is None:
            owner = getattr(getattr(obj, 'project', None), 'user', None)
        return owner == request.user
