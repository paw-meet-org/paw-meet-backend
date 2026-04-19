from rest_framework import serializers
from ..utils import validate_foto_format
from ..models import Pet, PetType

# ──────────────────────────────────────────────
# PET SERIALIZERS
# ──────────────────────────────────────────────

class PetSerializer(serializers.ModelSerializer):
    """
    Serializer completo de mascota para el dueño autenticado.
    Lectura + escritura. El campo 'owner' se inyecta desde la view,
    nunca lo envía el cliente (evita asignación arbitraria de propiedad).
    """
    age_years = serializers.ReadOnlyField()  # property del modelo

    class Meta:
        model = Pet
        fields = [
            'id', 'name', 'pet_type', 'species', 'breed',
            'size', 'birth_date', 'bio', 'avatar',
            'is_active', 'age_years', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'age_years']

    def validate(self, attrs):
        pet_type = attrs.get('pet_type', getattr(self.instance, 'pet_type', None))
        species = attrs.get('species', getattr(self.instance, 'species', ''))

        if pet_type == "OTHER" and not species.strip():
            raise serializers.ValidationError({
                'species': (
                    "El campo 'species' es obligatorio cuando "
                    "el tipo de mascota es 'Otro'."
                )
            })
        return attrs

class PetPublicSerializer(serializers.ModelSerializer):
    """
    Vista reducida de mascota para mostrar en perfiles públicos
    y en los encuentros. No expone owner_id directamente.
    """
    class Meta:
        model = Pet
        fields = ['name', 'pet_type', 'species', 'breed', 'size', 'avatar']
        read_only_fields = ['id']

# ──────────────────────────────────────────────
# PET TYPE SERIALIZERS
# ──────────────────────────────────────────────
class PetTypeSerializer(serializers.ModelSerializer):
    """
    Serializer completo de tipo de mascota para los administradores.
    Lectura + Escritura. 
    """
    class Meta:
        model = PetType
        fields = [
            'id', 'nombre', 'codigo'
        ]
        # No se incluye read_only_fields porque el admin puede tocar los atributos del BaseModel
        