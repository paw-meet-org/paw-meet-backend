from rest_framework import serializers
from .models import Asistencia, Encuentro, Estado
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

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

class EncuentroInsertSerializer(serializers.ModelSerializer):
    """
    Serializer genérico para la inserción de datos sobre encuentros.
    Crear + Actualizar
    """
    class Meta:
        model = Encuentro
        fields = [
            'localizacion', 'tipo_mascota', 'limite_usuarios',
            'duracion_minutos', 'descripcion', 'titulo', 'fecha_realizacion'
        ]


class EncuentroCreateSerializer(EncuentroInsertSerializer):
    """
    Serializer para la creación de encuentros.
    Hereda de EncuentroInsertSerializer
    """
    
    def validate_fecha_realizacion(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("La fecha de realización del encuentro debe ser futura.")
        return value
    
    def validate_limite_usuarios(self, value):
        if value < 2:
            raise serializers.ValidationError("El límite mínimo de usuarios es de 2.")
        return value

class EncuentroUpdateSerializer(EncuentroInsertSerializer):
    """
    Serializer para la actualización de encuentros.
    Hereda de EncuentroInsertSerializer
    """

    def validate(self, attrs):
        # No se puede modificar un encuentro finalizado o eliminado
        if self.isinstance and self.instance.estado in [Estado.ELIMINADO, Estado.FINALIZADO]:
            raise serializers.ValidationError("No se puede actualizar un encuentro finalizado o eliminado")
        return attrs

class EncuentroListSerializer(serializers.ModelSerializer):
    num_asistentes = serializers.SerializerMethodField()

    class Meta:
        model = Encuentro
        fields = [
            'id', 'titulo', 'localizacion', 'tipo_mascota',
            'fecha_realizacion', 'limite_usuarios', 'num_asistentes',
            'estado', 'descripcion'
        ]

    def get_num_asistentes(self, obj):
        # Cuenta el número de usuarios que han confirmado la asistencia
        if obj.asistencia:
            return obj.asistencia.contador_usuarios
        return 0
    
class InvitarSerializer(serializers.Serializer):
    """
    Serializer para controlar las invitaciones a los encuentros
    """
    usuario_id = serializers.UUIDField()

    def validate_usuario_id(self, value):
        from users.models import CustomUser
        if not CustomUser.objects.filter(id = value).exists():
            raise serializers.ValidationError("El usuario indicado no existe.")
        return value

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