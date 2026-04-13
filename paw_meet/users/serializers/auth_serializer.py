from rest_framework import serializers
from ..utils import validate_password_strength, validate_foto_format
import re
import os
# ──────────────────────────────────────────────
# JWT SERIALIZER PERSONALIZADO
# ──────────────────────────────────────────────

class CustomTokenObtainPairSerializer(serializers.Serializer):
    """
    Solo documentación de entrada para el login.
    La lógica real está en el TokenObtainPairView extendido.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

"""class RegistroSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length = 50, required = True)
    correo_electronico = serializers.EmailField(required = True)
    password = serializers.CharField(write_only = True, required = True)
    biografia = serializers.CharField(max_length = 300, required = False)
    foto = serializers.FileField(required = False)

    def validate_password(self, value):
        return validate_password_strength(value)
    
    def validate_foto(self, value):
        return validate_foto_format(value)
    
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length = 50, required = True)
    password = serializers.CharField(write_only = True, required = True)

    def validate_password(self, value):
        return validate_password_strength(value)"""