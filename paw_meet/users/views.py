from rest_framework import generics, status, viewsets
from common.pagination import StandardPagination
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.conf import settings
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
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
# AUTH
# ──────────────────────────────────────────────
"""
class RegisterView(generics.CreateAPIView):
    
    POST /api/auth/register/
    Registro público. No requiere autenticación.
    Devuelve tokens JWT directamente tras el registro
    para evitar que el cliente tenga que hacer un segundo request.
    
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generar tokens JWT inmediatamente tras el registro
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

"""
"""
class CustomTokenObtainPairView(TokenObtainPairView):
    
    POST /api/auth/login/
    Login estándar de simplejwt. Extiende la respuesta
    añadiendo datos básicos del usuario al payload de respuesta.
    Uso de email como campo de autenticación.
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # Añadir info del usuario a la respuesta de login
            from django.contrib.auth import authenticate
            # simplejwt ya validó credenciales; recuperamos el usuario
            # a través del serializer interno para enriquecer la respuesta
            from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
            serializer = TokenObtainPairSerializer(data=request.data)
            serializer.is_valid(raise_exception=False)
            user = serializer.user if hasattr(serializer, 'user') else None

            if user:
                response.data['user'] = {
                    'id': str(user.id),
                    'email': user.email,
                    'username': user.username,
                    'role': user.role,
                    'full_name': user.full_name,
                }
        return response
"""

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
            return Response(
                {"detail": "No tienes permiso para reclamar el rol de administrador."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.is_app_admin:
            return Response(
                {"detail": "Ya eres administrador."},
                status=status.HTTP_200_OK,
            )

        user.is_app_admin = True
        user.save(update_fields=["role"])

        return Response(
            {"detail": "Rol de administrador asignado correctamente."},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags = ['admin'])
class CreateUsersByAdmin(generics.CreateAPIView):
    """
    POST /api/admin/create/ -> Crea un nuevo usuario
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        # Obtengo el serializer
        serializer = self.get_serializer(data = request.data)
        serializer.is_valid() # Si es válido, puedo obtener su validated data
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

        response = requests.post(
            url = url,
            headers = headers,
            json = payload,
            verify = False
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
    
def delete_supabase_user(supabase_uid: str) -> tuple[bool, str]:
    """
    Elimina un usuario de Supabase Auth via Admin API REST.
    Retorna (success: bool, error_message: str)
    """
    url = f"{decouple.config('SUPABASE_URL')}/auth/v1/admin/users/{supabase_uid}"
    headers = {
        "apikey": decouple.config('SUPABASE_SERVICE_ROLE_KEY'),
        "Authorization": f"Bearer {decouple.config('SUPABASE_SERVICE_ROLE_KEY')}",
    }

    response = requests.delete(url, headers=headers)

    if response.status_code in (200, 204):
        return True, ""
    return False, response.text
    
@extend_schema(tags=["admin"])
class AdminUserDeleteViewSet(viewsets.GenericViewSet):

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
            return Response(
                {"detail": "El parámetro 'email' es requerido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Buscar usuario en Django
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": f"No existe ningún usuario con email '{email}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        supabase_uid = user.supabase_uid  # ajusta al campo que almacena el UUID de Supabase

        # 2. Eliminar en Supabase primero
        success, error = delete_supabase_user(supabase_uid)
        if not success:
            return Response(
                {"detail": "Error al eliminar el usuario en Supabase.", "error": error},
                status=status.HTTP_502_BAD_GATEWAY,
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
            return Response(
                {'current_password': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

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
            qs = qs.filter(owner=user)

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