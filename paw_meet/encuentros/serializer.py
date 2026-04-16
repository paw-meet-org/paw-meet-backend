from rest_framework import serializers
from .models import Asistencia, Encuentro, Estado
from django.core.exceptions import ValidationError as DjangoValidationError

# ──────────────────────────────────────────────
# ENCUENTROS SERIALIZERS
# ──────────────────────────────────────────────

class EncuentroSerializer(serializers.ModelSerializer):
    """
    Serializer sobre encuentros.
    Lectura + escritura
    """

    class Meta:
        model = Encuentro
        fields = [
            'localizacion', 'tipo_mascota', 'limite_usuarios', 
            'duracion_minutos', 'descripcion', 'titulo', 
            'estado'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class AsistenciaSerialzer(serializers.ModelSerializer):
    """
    Serializer sobre asistencias.
    Lectura + escritura
    """

    class Meta:
        model = Asistencia
        fields = [
            'encuentro', 'contador_usuarios', 
            'contador_mascotas', 'estado'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        encuentro_formulario = attrs.get('encuentro')
        estado = attrs.get('estado')
        contador_usuarios = attrs.get('contador_usuarios', 0)

        # Valida la existencia del encuentro asociado a la asistencia
        if not encuentro_formulario:
            raise serializers.ValidationError("No hay registros en el sistema sobre el encuentro indicado")
        
        # Valida el estado del encuentro respecto al estado de la asistencia
        if (encuentro_formulario.estado in [Estado.BORRADOR, Estado.ELIMINADO]) and (estado == Estado.CONFIRMADO):
            raise serializers.ValidationError("No se puede mantener confirmada la asistencia sobre un encuentro no confirmado")
        
        # Valida los límites de usuarios 
        if contador_usuarios > encuentro_formulario.limite_usuarios:
            raise serializers.ValidationError(
                f"No se puede superar el límite de {encuentro_formulario.limite_usuarios} usuarios."
            )
        
        return attrs