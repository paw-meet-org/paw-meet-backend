from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser, Pet
from .serializers.user_serializer import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    UserPublicSerializer,
    ChangePasswordSerializer,
    PetSerializer,
)
from common.permissions import IsOwnerOrAdmin, IsOwnerOrReadOnly


# ──────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Registro público. No requiere autenticación.
    Devuelve tokens JWT directamente tras el registro
    para evitar que el cliente tenga que hacer un segundo request.
    """
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


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Login estándar de simplejwt. Extiende la respuesta
    añadiendo datos básicos del usuario al payload de respuesta.
    Uso de email como campo de autenticación.
    """
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

        from .services import UserService
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