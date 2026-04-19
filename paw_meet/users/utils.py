from rest_framework import serializers
import re
import os

def validate_password_strength(value):
    if not re.match(r'.{8,}', value):
        raise serializers.ValidationError("Error al validar la contrseña: largo menor que ocho")
    if not re.match(r'\d+', value):
        raise serializers.ValidationError("Error al validar la contrseña: no tiene digitos")
    if not re.match(r'[A-Z]+', value):
        raise serializers.ValidationError("Error al validar la contrseña: no tiene letras maysuculas")
    if not re.match(r'[a-z]+', value):
        raise serializers.ValidationError("Error al validar la contrseña: no tiene letras mayusculas")
    
    return value

def validate_foto_format(value):
    ALLOWED_FORMATS = ['.png', '.jpg', '.jpeg']
    format = os.path.splitext(value.name)[1] # Cogemos la extensión que se encuentra en la posición 1 de la tupla
    
    if format not in ALLOWED_FORMATS:
        raise serializers.ValidationError("La extenión de la foto de usuario adjuntada no es válida")
    return value