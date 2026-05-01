from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelListSerializer
from django.utils import timezone
from django.db import transaction
from .models import Meeting, Attendance, City, MeetingStatus
from users.models import Pet
from users.serializers.mascota_serializer import PetSerializer
from django.conf import settings
from datetime import datetime


class CitySerializer(serializers.ModelSerializer):
    """Serializer para el modelo City."""
    
    class Meta:
        model = City
        fields = ['id', 'name', 'province']

class NearbySerializer(GeoFeatureModelListSerializer):
    """
    Serializer para controlar los puntos espaciales de los encuentros.    
    """
    class Meta:
        model = Meeting
        geo_field = "location_point"
        fields = [
            'id', 'title', 'description', 'date', 'start_time', 'end_time',
            'location', 'city', 'city_name', 'creator', 'creator_name',
            'max_participants', 'confirmed_attendees', 'available_spots',
            'status', 'is_attending', 'created_at'
        ]


class MeetingListSerializer(serializers.ModelSerializer):
    """
    Serializer para listados de encuentros.
    """
    city_name = serializers.CharField(source='city.name', read_only=True)
    creator_name = serializers.CharField(source='creator.get_full_name', read_only=True)
    confirmed_attendees = serializers.SerializerMethodField()
    is_attending = serializers.SerializerMethodField()
    available_spots = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'date', 'start_time', 'end_time',
            'location', 'city', 'city_name', 'creator', 'creator_name',
            'max_participants', 'confirmed_attendees', 'available_spots',
            'status', 'is_attending', 'created_at'
        ]
    
    def get_confirmed_attendees(self, obj):
        return obj.attendees.filter(status='confirmed').count()
    
    def get_is_attending(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.attendees.filter(
                user=request.user,
                status='confirmed'
            ).exists()
        return False


class AttendanceSerializer(serializers.ModelSerializer):
    """
    Serializer para gestionar asistencias.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    pets_details = PetSerializer(source='pets', many=True, read_only=True)
    pet_ids = serializers.PrimaryKeyRelatedField(
        queryset=Pet.objects.all(),
        source='pets',
        many=True,
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'meeting', 'user', 'user_email', 'user_name',
            'pets', 'pet_ids', 'pets_details', 'status', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'meeting', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validaciones personalizadas para asistencia."""
        request = self.context.get('request')
        meeting = self.context.get('meeting')
        
        if request and request.method == 'POST':
            # Verificar si ya existe una asistencia
            if Attendance.objects.filter(
                meeting=meeting,
                user=request.user,
                status='confirmed'
            ).exists():
                raise serializers.ValidationError(
                    "Ya estás registrado como asistente a este encuentro."
                )
            
            # Verificar que el encuentro se pueda unir
            if not meeting.can_be_joined():
                raise serializers.ValidationError(
                    "No es posible unirse a este encuentro. Puede estar lleno, cancelado o ya ha pasado."
                )
        
        # Validar que las mascotas pertenezcan al usuario
        if 'pets' in data:
            user = request.user if request else self.instance.user if self.instance else None
            if user:
                user_pet_ids = set(user.pets.values_list('id', flat=True))
                selected_pet_ids = {pet.id for pet in data['pets']}
                if not selected_pet_ids.issubset(user_pet_ids):
                    raise serializers.ValidationError({
                        'pet_ids': 'Solo puedes seleccionar mascotas que te pertenecen.'
                    })
        
        return data
    
    def create(self, validated_data):
        """Asigna automáticamente el usuario autenticado."""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class MeetingDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para encuentros (incluye información de asistentes).
    """
    city = CitySerializer(read_only=True)
    city_id = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.all(),
        source='city',
        write_only=True
    )
    creator_email = serializers.EmailField(source='creator.email', read_only=True)
    creator_name = serializers.CharField(source='creator.get_full_name', read_only=True)
    pets_details = PetSerializer(source='pets', many=True, read_only=True)
    pet_ids = serializers.PrimaryKeyRelatedField(
        queryset=Pet.objects.all(),
        source='pets',
        many=True,
        write_only=True,
        required=False
    )
    attendees = AttendanceSerializer(many=True, read_only=True)
    confirmed_attendees_count = serializers.SerializerMethodField()
    available_spots = serializers.IntegerField(read_only=True)
    is_creator = serializers.SerializerMethodField()
    user_attendance = serializers.SerializerMethodField()
    can_join = serializers.SerializerMethodField()
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'date', 'start_time', 'end_time',
            'location', 'location_lat', 'location_lng',
            'city', 'city_id', 'creator', 'creator_email', 'creator_name',
            'pets', 'pet_ids', 'pets_details', 'max_participants',
            'confirmed_attendees_count', 'available_spots', 'status',
            'attendees', 'is_creator', 'user_attendance', 'can_join',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'creator', 'status', 'created_at', 'updated_at']
    
    def get_confirmed_attendees_count(self, obj):
        return obj.attendees.filter(status='confirmed').count()
    
    def get_is_creator(self, obj):
        request = self.context.get('request')
        return request and request.user == obj.creator
    
    def get_user_attendance(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                attendance = obj.attendees.get(user=request.user)
                return AttendanceSerializer(attendance).data
            except Attendance.DoesNotExist:
                return None
        return None
    
    def get_can_join(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return (
                obj.can_be_joined()
                and not obj.attendees.filter(user=request.user, status='confirmed').exists()
                and request.user != obj.creator
            )
        return False
    
    def validate_date(self, value):
        """Validar que la fecha no sea pasada para nuevos encuentros."""
        if not self.instance and value < timezone.now().date():
            raise serializers.ValidationError(
                "La fecha del encuentro no puede ser anterior a hoy."
            )
        return value
    
    def validate(self, data):
        """Validaciones adicionales."""
        date = data.get('date')        
        start_time = data.get('start_time')
        # Validar hora de fin > hora de inicio
        if data.get('start_time') and data.get('end_time'):
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError({
                    'end_time': 'La hora de fin debe ser posterior a la hora de inicio.'
                })
        if date and start_time:
            start_datetime = timezone.make_aware(
                datetime.combine(date, start_time)
            )
            if start_datetime < timezone.now():
                raise serializers.ValidationError({
                    'start_time': 'La hora de inicio debe ser igual o posterior a la hora actual'
                })
        
        # Validar que las mascotas pertenezcan al creador
        if 'pets' in data:
            request = self.context.get('request')
            if request:
                user_pet_ids = set(request.user.pets.values_list('id', flat=True))
                selected_pet_ids = {pet.id for pet in data['pets']}
                if not selected_pet_ids.issubset(user_pet_ids):
                    raise serializers.ValidationError({
                        'pet_ids': 'Solo puedes seleccionar mascotas que te pertenecen.'
                    })
        
        return data
    
    def create(self, validated_data):
        """Asigna automáticamente el creador."""
        validated_data['creator'] = self.context['request'].user
        return super().create(validated_data)