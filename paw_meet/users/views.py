from rest_framework import generics, status, viewsets
from common.pagination import StandardPagination
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.conf import settings
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from common.mixins import ExternalServiceMixin
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from common.exceptions import BusinessLogicError
import requests
import decouple


from .models import CustomUser, Pet, PetType
from .serializers.user_serializer import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    UserPublicSerializer,
    ChangePasswordSerializer,
    ClaimAdminResponseSerializer
)
from .serializers.mascota_serializer import (
    PetSerializer, 
    PetTypeSerializer
)
from common.permissions import IsOwnerOrAdmin, IsAppAdmin


# ──────────────────────────────────────────────
# USER PROFILE
# ──────────────────────────────────────────────

class MeView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/users/me/   → perfil propio completo
    PATCH /api/users/me/  → actualizar perfil (parcial)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        # Forzamos PATCH (partial=True) por defecto para UX más amigable
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

@extend_schema(tags=['admin'])
class LoginAdminUser(APIView):
    """
    POST /api/admin/login -> Loguea a un nuevo admin en el sistema
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: ClaimAdminResponseSerializer,
            403: ClaimAdminResponseSerializer,
        }
    )
    def post(self, request):
        user = request.user 
        email = user.email.lower()

        if email not in settings.ADMIN_EMAILS:
            raise PermissionDenied("No tienes permiso para reclamar el rol de administrador.")

        if user.is_app_admin:
            raise BusinessLogicError("Ya eres administrador.")

        user.is_app_admin = True
        user.save(update_fields=["role"])

        return Response(
            {"detail": "Rol de administrador asignado correctamente."},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags = ['admin'])
class CreateUsersByAdmin(ExternalServiceMixin, generics.CreateAPIView):
    """
    POST /api/admin/create/ -> Crea un nuevo usuario
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        # Obtengo el serializer
        serializer = self.get_serializer(data = request.data)
        serializer.is_valid(raise_exception = True) # Si es válido, puedo obtener su validated data
        validated_data = serializer.validated_data

        # Estructura de la petición a Supabase
        url = f"{decouple.config('SUPABASE_SIGN_IN_URL')}"
        print(url)
        headers = {
            "apikey": decouple.config('SUPABASE_ANON_KEY'),
            "Authorization": f"Bearer {decouple.config('SUPABASE_SERVICE_ROLE_KEY')}",
            "Content-Type": "application/json"
        }

        payload = {
            'email': validated_data['email'],
            'password': validated_data['password']
        }

        response = self.call_external(
            requests.post,
            url     = url,
            headers = headers,
            json    = {'email': validated_data['email'], 'password': validated_data['password']}
        )

        supabase_data = response.json()
        
        if response.status_code >= 400:
            return Response(
                {
                    'error': 'Error creando un usuario nuevo en Supabase',
                    'details': supabase_data
                }
            )
        print(supabase_data)
        supabase_uid = supabase_data['id']

        serializer.save(
            supabase_uid = supabase_uid
        )

        return Response(
            {
                'message': 'Usuario creado correctamente',
                'supabase_uid': supabase_uid
            },
            status = status.HTTP_201_CREATED
        )
    
@extend_schema(tags = ['admin'])
class ListUsersRegistered(generics.ListAPIView):
    """
    GET /api/admin/users/list -> Lista todos los usuarios almacenados en el sistema, paginados de 25 en 25
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return CustomUser.objects.all()
    
@extend_schema(tags=["admin"])
class AdminUserDeleteViewSet(ExternalServiceMixin, viewsets.GenericViewSet):

    @extend_schema(
        summary="Elimina un usuario por email",
        parameters=[
            OpenApiParameter(
                name="email",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Email del usuario a eliminar",
            )
        ],
        responses={204: None},
    )
    @action(detail=False, methods=["delete"], url_path="delete")
    def delete_by_email(self, request):
        email = request.query_params.get("email")

        if not email:
            raise ValidationError({"email": "El parámetro 'email' es requerido."})

        # 1. Buscar usuario en Django
        
        user = CustomUser.objects.get(email=email)
        if not user:
            raise NotFound(f"No existe ningún usuario con email '{email}'.")

        supabase_uid = user.supabase_uid  # ajusta al campo que almacena el UUID de Supabase

        # 2. Eliminar en Supabase primero
        url = f"{decouple.config('SUPABASE_URL')}/auth/v1/admin/users/{user.supabase_uid}"
        self.call_external(
            requests.delete,
            url     = url,
            headers = {
                "apikey"       : decouple.config('SUPABASE_SERVICE_ROLE_KEY'),
                "Authorization": f"Bearer {decouple.config('SUPABASE_SERVICE_ROLE_KEY')}",
            }
        )

        # 3. Eliminar en Django solo si Supabase tuvo éxito
        user.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

class ChangePasswordView(generics.GenericAPIView):
    """
    POST /api/users/me/change-password/
    Requiere autenticación. Verifica contraseña actual antes de cambiar.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            UserService.change_password(
                user=request.user,
                current_password=serializer.validated_data['current_password'],
                new_password=serializer.validated_data['new_password'],
            )
        except ValueError as e:
            raise ValidationError({"current_password": str(e)})

        return Response(
            {'detail': 'Contraseña actualizada correctamente.'},
            status=status.HTTP_200_OK
        )


class UserPublicProfileView(generics.RetrieveAPIView):
    """
    GET /api/users/<uuid>/
    Perfil público de cualquier usuario. No requiere autenticación.
    Solo expone datos públicos (sin email, sin role, etc.).
    """
    permission_classes = [AllowAny]
    serializer_class = UserPublicSerializer
    queryset = CustomUser.objects.filter(is_active=True).prefetch_related('pets')
    lookup_field = 'id'


# ──────────────────────────────────────────────
# PETS
# ──────────────────────────────────────────────

@extend_schema(tags = ['pets'])
class PetViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para mascotas del usuario autenticado.

    GET    /api/users/me/pets/          → lista mis mascotas
    POST   /api/users/me/pets/          → crear mascota
    GET    /api/users/me/pets/<id>/     → detalle
    PATCH  /api/users/me/pets/<id>/     → editar parcial
    DELETE /api/users/me/pets/<id>/     → eliminar (soft si is_active=False)
    """
    serializer_class = PetSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        """
        Un usuario normal solo ve SUS mascotas.
        Un admin puede ver todas (útil para moderación).
        Filtramos por is_active=True por defecto; ?include_inactive=1 para ver todas.
        """
        user = self.request.user
        qs = Pet.objects.select_related('owner')
        if not user.is_app_admin:
            qs = qs.filter(owner=user.id)
        if not self.request.query_params.get('include_inactive'):
            qs = qs.filter(is_active=True)

        return qs

    def perform_create(self, serializer):
        """Inyecta el owner automáticamente. El cliente nunca lo envía."""
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        """
        Soft delete: en lugar de eliminar, desactivamos la mascota.
        Preserva el historial de encuentros en los que participó.
        """
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])

    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """
        POST /api/users/me/pets/<id>/restore/
        Reactiva una mascota archivada.
        """
        pet = self.get_object()
        pet.is_active = True
        pet.save(update_fields=['is_active', 'updated_at'])
        return Response(self.get_serializer(pet).data)
    
# ──────────────────────────────────────────────
# PETS TYPE
# ──────────────────────────────────────────────

@extend_schema(tags = ['pet-type'])
class PetTypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo sobre tipos de mascota para administradores.

    GET    /api/pettypes/          → lista los tipos de mascota registrados
    POST   /api/pettypes/          → crear tipo de mascota
    GET    /api/pettypes/<id>/     → detalle
    PATCH  /api/pettypes/<id>/     → editar parcial
    DELETE /api/pettypes/<id>/     → eliminar
    """
    queryset = PetType.objects.all()
    serializer_class = PetTypeSerializer

    def get_permissions(self):
        """
        Permisos por acción.
        """

        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]