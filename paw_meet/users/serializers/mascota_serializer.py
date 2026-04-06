from rest_framework import serializers
from ..models import TipoMascota, Mascota
from ..utils import validate_foto_format

class MascotaCreateSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length = 50, required = True)
    raza = serializers.PrimaryKeyRelatedField(queryset = TipoMascota.objects.all()) # Si no lo encuentra falla automáticamente
    descripcion = serializers.CharField(max_length = 300, required = False)
    foto = serializers.FileField(required = False)

    def validate_foto(self, value):
        return validate_foto_format(value)
    
class TipoMascotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoMascota
        fields = ['nombre', 'codigo']

class MascotaGetSerializer(serializers.ModelSerializer):
    tipo = TipoMascotaSerializer(source = "tipo_mascota")
    class Meta:
        model = Mascota
        fields = ['nombre', 'tipo']