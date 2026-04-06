from rest_framework import serializers
from ..utils import validate_foto_format

class UserUpdateSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length = 50, required = False)
    biografia = serializers.CharField(max_length = 300, required = False)
    foto = serializers.FileField(required = False)

    def validate_foto(self, value):
        return validate_foto_format(value)