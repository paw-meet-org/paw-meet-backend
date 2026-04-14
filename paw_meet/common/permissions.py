from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAppAdmin(BasePermission):
    """
    Permite acceso solo a usuarios con role='admin'.
    Distinto de is_staff (acceso al Django Admin).
    """
    message = "Se requiere rol de administrador."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_app_admin
        )


class IsOwnerOrAdmin(BasePermission):
    """
    A nivel de objeto: permite acceso al dueño del recurso o a un admin.
    El objeto debe tener un campo 'owner' o ser el propio usuario.
    """
    message = "No tienes permiso para acceder a este recurso."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_app_admin:
            return True
        # Soporta objetos con .owner (Pet, Encuentro) o el propio User
        owner = getattr(obj, 'owner', obj)
        return owner == request.user


class IsOwnerOrReadOnly(BasePermission):
    """
    Lectura pública, escritura solo para el dueño o admin.
    Útil para perfiles públicos de usuario.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_app_admin:
            return True
        owner = getattr(obj, 'owner', obj)
        return owner == request.user