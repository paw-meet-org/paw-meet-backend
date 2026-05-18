from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from common.pagination import StandardPagination
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend


from .models import Foro, Publicacion, CategoriaPublicacion
from .serializer import (
    ForoListSerializer,
    ForoDetailSerializer,
    PublicacionListSerializer,
    PublicacionDetailSerializer,
    CategoriaPublicacionSerializer
)
from common.permissions import IsOwnerOrAdmin, IsAppAdmin

# ──────────────────────────────────────────────
# CATEGORIA PUBLICACION
# ──────────────────────────────────────────────

@extend_schema(tags=['categorias-publicacion'])
class CategoriaPublicacionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para Categorías de Publicación.
    - GET: Disponible para cualquier usuario autenticado (para rellenar desplegables al crear posts).
    - POST/PATCH/DELETE: Solo para Administradores de la app.
    """
    queryset = CategoriaPublicacion.objects.all()
    serializer_class = CategoriaPublicacionSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            # Solo admins pueden crear, editar o borrar categorías
            permission_classes = [IsAuthenticated, IsAppAdmin]
        return [permission() for permission in permission_classes]


# ──────────────────────────────────────────────
# FOROS
# ──────────────────────────────────────────────

@extend_schema(tags=['foros'])
class ForoViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para Foros.
    - Todos los usuarios autenticados pueden ver foros y crearlos.
    - Solo el creador original (owner) o un admin pueden editar o eliminar un foro.
    """
    queryset = Foro.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['encuentro']

    def get_serializer_class(self):
        """
        Usa el serializador ligero para la lista y el detallado (con publicaciones)
        para ver un foro concreto o crearlo.
        """
        if self.action == 'list':
            return ForoListSerializer
        return ForoDetailSerializer

    def perform_create(self, serializer):
        """Inyecta el usuario creador automáticamente."""
        serializer.save(usuario=self.request.user)


# ──────────────────────────────────────────────
# PUBLICACIONES
# ──────────────────────────────────────────────

@extend_schema(tags = ['admin'])
class ListTodasPublicaciones(ListModelMixin, viewsets.GenericViewSet):
    """
    GET /api/admin/social/publicaciones/list/ -> Lista todas las publicaciones del sistema
    """
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    serializer_class = PublicacionDetailSerializer

    def get_queryset(self):
        return Publicacion.objects.all()

@extend_schema(tags=['publicaciones'])
class PublicacionViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para Publicaciones.
    - Todos los usuarios autenticados pueden ver publicaciones y crearlas.
    - Solo el autor original (owner) o un admin pueden editar o eliminarlas.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        """
        Por defecto, vemos todas las publicaciones.
        Permitimos filtrar por foro_id pasando un query param: ?foro_id=X
        """
        qs = Publicacion.objects.select_related('usuario', 'foro', 'categoria')
        
        foro_id = self.request.query_params.get('foro_id')
        if foro_id:
            qs = qs.filter(foro_id=foro_id)
            
        return qs

    def get_serializer_class(self):
        """
        Usa el serializador ligero para listas y el detallado para ver/crear/editar.
        """
        if self.action == 'list':
            return PublicacionListSerializer
        return PublicacionDetailSerializer

    def perform_create(self, serializer):
        """Inyecta el usuario autor automáticamente."""
        serializer.save(usuario=self.request.user)