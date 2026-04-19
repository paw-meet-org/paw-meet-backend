from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .mascota_serializer import PetPublicSerializer, PetSerializer

from ..models import CustomUser

# ──────────────────────────────────────────────
# USER SERIALIZERS
# ──────────────────────────────────────────────

class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Registro de nuevo usuario.
    - Valida que password y password_confirm coincidan.
    - Aplica los validadores de contraseña de Django (settings.AUTH_PASSWORD_VALIDATORS).
    - NO devuelve el password en la respuesta.
    """
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'username',
            'first_name', 'last_name',
            'password', 'password_confirm',
        ]
        read_only_fields = ['id']

    def validate_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este email.")
        return value.lower()

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({
                'password_confirm': "Las contraseñas no coinciden."
            })
        # Ejecutar validadores de Django (longitud, similitud, contraseñas comunes, etc.)
        try:
            validate_password(attrs['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        return attrs

    def create(self, validated_data):
        # Delegamos al service layer
        from ..services.user_service import UserService
        return UserService.register_user(**validated_data)


class UserPublicSerializer(serializers.ModelSerializer):
    """
    Perfil público de un usuario. Lo ven otros usuarios de la app.
    Expone solo información no sensible.
    """
    pets = PetPublicSerializer(many=True, read_only=True)
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'full_name',
            'bio', 'avatar', 'ciudad',
            'pets',
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Perfil privado: solo accesible por el propio usuario autenticado.
    Permite editar datos de perfil. El email se puede actualizar
    con validación de unicidad. El password NO se cambia desde aquí
    (hay endpoint dedicado para eso).
    """
    pets = PetSerializer(many=True, read_only=True)
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'username', 'full_name',
            'first_name', 'last_name',
            'bio', 'avatar', 'ciudad', 'phone',
            'role', 'is_active',
            'date_joined', 'last_login',
            'pets',
        ]
        read_only_fields = [
            'id', 'role', 'is_active',
            'date_joined', 'last_login',
        ]

    def validate_email(self, value):
        value = value.lower()
        qs = CustomUser.objects.filter(email__iexact=value)
        # Excluimos el propio usuario en caso de PATCH
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Este email ya está en uso.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """
    Cambio de contraseña autenticado.
    Requiere la contraseña actual como verificación.
    """
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': "Las contraseñas nuevas no coinciden."
            })
        try:
            validate_password(attrs['new_password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})
        return attrs