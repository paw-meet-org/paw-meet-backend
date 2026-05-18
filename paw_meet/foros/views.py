from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from common.pagination import StandardPagination
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError
from common.exceptions import BusinessLogicError, ResourceNotFoundError

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

    def destroy(self, request, *args, **kwargs):
        """Eliminar categoría con validación de que no tenga publicaciones asociadas."""
        instance = self.get_object()
        
        # Validar regla de negocio: no eliminar categoría con publicaciones
        if instance.publicaciones.exists():
            raise BusinessLogicError(
                detail="No se puede eliminar la categoría porque tiene publicaciones asociadas."
            )
        
        return super().destroy(request, *args, **kwargs)


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

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['encuentro']

    def get_permissions(self):

        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]


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
    def perform_create(self, serializer):
        """Inyecta el usuario autor automáticamente."""
        serializer.save(usuario=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Crear una nueva publicación con validaciones adicionales.
        """
        # Validar que el foro existe antes de crear
        foro_id = request.data.get('foro')
        if foro_id and not Foro.objects.filter(id=foro_id).exists():
            raise ResourceNotFoundError(detail=f"El foro con id {foro_id} no existe.")
        
        return super().create(request, *args, **kwargs)