from rest_framework import serializers
from .models import Foro, Publicacion, CategoriaPublicacion
from users.serializers.user_serializer import UserPublicSerializer  
from encuentros.models import Meeting
from encuentros.serializers import MeetingDetailSerializer

# ──────────────────────────────────────────────
# CATEGORY SERIALIZER
# ──────────────────────────────────────────────

class CategoriaPublicacionSerializer(serializers.ModelSerializer):
    """
    Serializador sencillo para las categorías.
    Normalmente, los usuarios solo las leen (GET). La creación suele ser de admin.
    """
    class Meta:
        model = CategoriaPublicacion
        fields = ['id', 'nombre']


# ──────────────────────────────────────────────
# PUBLICACION SERIALIZERS
# ──────────────────────────────────────────────

class PublicacionListSerializer(serializers.ModelSerializer):
    """
    Serializador para listar publicaciones (ej: en el feed o dentro de un foro).
    Anidamos la categoría para que el frontend no tenga que hacer peticiones extra,
    y mostramos un resumen del usuario autor.
    """
    usuario = UserPublicSerializer(read_only=True)
    categoria = CategoriaPublicacionSerializer(read_only=True)
    
    class Meta:
        model = Publicacion
        fields = [
            'id', 'titulo', 'usuario', 'categoria', 
            'foto', 'uploaded_at', 'likes'
            # Nota: Omitimos 'texto' completo para no sobrecargar listas si son muy largas
        ]


class PublicacionDetailSerializer(serializers.ModelSerializer):
    """
    Serializador para ver el detalle de una publicación (al hacer clic en ella).
    Aquí sí enviamos el texto completo.
    También se usa para CREAR (POST) o ACTUALIZAR (PUT/PATCH).
    """
    # En lectura, mostramos los objetos anidados.
    usuario_detail = UserPublicSerializer(source='usuario', read_only=True)
    categoria_detail = CategoriaPublicacionSerializer(source='categoria', read_only=True)
    
    # En escritura, aceptamos solo los IDs para vincular.
    categoria_id = serializers.PrimaryKeyRelatedField(
        queryset=CategoriaPublicacion.objects.all(),
        source='categoria',
        write_only=True,
        required=False,
        allow_null=True
    )
    # Asumimos que el foro se manda por ID al crear la publicación
    foro_id = serializers.PrimaryKeyRelatedField(
        queryset=Foro.objects.all(),
        source='foro',
        write_only=True
    )

    class Meta:
        model = Publicacion
        fields = [
            'id', 'titulo', 'texto', 'foto', 'uploaded_at', 'likes',
            'usuario_detail', 'categoria_detail', 
            'categoria_id', 'foro_id'
        ]
        read_only_fields = ['id', 'uploaded_at', 'likes']

        extra_kwargs = {
            'foto' : {
                'required': False,
                'allow_null': True
            }
        }

    def create(self, validated_data):
        """
        Al crear una publicación, asignamos automáticamente el usuario 
        que hace la petición como autor.
        """
        # Obtenemos el usuario del request desde el contexto del serializador
        user = self.context['request'].user
        validated_data['usuario'] = user
        return super().create(validated_data)


# ──────────────────────────────────────────────
# FORO SERIALIZERS
# ──────────────────────────────────────────────

class ForoListSerializer(serializers.ModelSerializer):
    """
    Serializador para listar los foros disponibles.
    Muestra información general y el creador.
    """
    usuario = UserPublicSerializer(read_only=True)
    # Podríamos añadir un campo calculado para saber cuántos posts tiene
    total_publicaciones = serializers.SerializerMethodField()
    publicaciones = PublicacionListSerializer(many = True, read_only = True)
    encuentro = MeetingDetailSerializer(read_only = True)

    class Meta:
        model = Foro
        fields = ['id', 'titulo', 'tipo_foro', 'usuario', 'publicaciones', 'total_publicaciones', 'encuentro']
        
    def get_total_publicaciones(self, obj):
        # Cuenta cuántas publicaciones están en este foro
        return obj.publicaciones.count()


class ForoDetailSerializer(serializers.ModelSerializer):
    """
    Serializador detallado de un foro.
    Incluye la lista de publicaciones que contiene.
    Se usa para ver un foro concreto y para crearlo.
    """
    usuario = UserPublicSerializer(read_only=True)
    # Anidamos el serializador de lista de publicaciones
    publicaciones = PublicacionListSerializer(many=True, read_only=True)

    encuentro = serializers.PrimaryKeyRelatedField(
        queryset=Meeting.objects.all(),
        required = False,
        allow_null = True
    )

    class Meta:
        model = Foro
        fields = ['id', 'titulo', 'tipo_foro', 'usuario', 'publicaciones', 'encuentro']
        read_only_fields = ['id']

    def create(self, validated_data):
        """
        Al crear un foro, el usuario creador es el que hace la petición.
        """
        user = self.context['request'].user
        validated_data['usuario'] = user
        return super().create(validated_data)