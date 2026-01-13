"""
Android APK Manager Permissions
Custom Permission Classes für App-Verwaltung
"""

from rest_framework import permissions


class IsAppOwnerOrReadOnly(permissions.BasePermission):
    """
    Nur App-Ersteller können bearbeiten/löschen
    Öffentliche Apps sind für alle lesbar
    """

    def has_permission(self, request, view):
        """Authentifizierung nur für schreibende Operationen"""
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Object-level permission check"""
        # Lesender Zugriff für öffentliche Apps
        if request.method in permissions.SAFE_METHODS:
            if obj.is_public:
                return True
            # Private Apps nur für Owner
            return request.user == obj.created_by

        # Schreibender Zugriff nur für Owner
        return request.user == obj.created_by


class IsVersionOwnerOrReadOnly(permissions.BasePermission):
    """
    Version-Permissions basierend auf App-Ownership
    """

    def has_permission(self, request, view):
        """Authentifizierung nur für schreibende Operationen"""
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Object-level permission check"""
        # Lesender Zugriff für öffentliche Apps
        if request.method in permissions.SAFE_METHODS:
            if obj.app.is_public:
                return True
            return request.user == obj.app.created_by

        # Schreibender Zugriff nur für App-Owner
        return request.user == obj.app.created_by


class IsPublicOrAuthenticated(permissions.BasePermission):
    """
    Öffentliche Endpunkte erlauben unauthentifizierten Zugriff
    """

    def has_permission(self, request, view):
        """Erlaube öffentliche Downloads ohne Auth"""
        return True
