"""
Desktop App Manager Permissions
Custom Permission Classes fuer App-Verwaltung
"""

from rest_framework import permissions


class IsAppOwnerOrReadOnly(permissions.BasePermission):
    """
    Nur App-Ersteller koennen bearbeiten/loeschen
    Oeffentliche Apps sind fuer alle lesbar
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            if obj.is_public:
                return True
            return request.user == obj.created_by
        return request.user == obj.created_by


class IsVersionOwnerOrReadOnly(permissions.BasePermission):
    """
    Version-Permissions basierend auf App-Ownership
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            if obj.app.is_public:
                return True
            return request.user == obj.app.created_by
        return request.user == obj.app.created_by
