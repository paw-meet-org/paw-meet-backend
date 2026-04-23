from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory
from datetime import timedelta, date

from encuentros.serializers import (
    MeetingDetailSerializer,
    MeetingListSerializer,
    AttendanceSerializer,
    CitySerializer
)
from encuentros.models import Meeting, MeetingStatus
from .factories import UserFactory, PetFactory, CityFactory, MeetingFactory, AttendanceFactory


class CitySerializerTest(TestCase):
    """Pruebas para CitySerializer."""
    
    def test_city_serializer(self):
        city = CityFactory(name='Madrid', province='Madrid')
        serializer = CitySerializer(city)
        
        self.assertEqual(serializer.data['name'], 'Madrid')
        self.assertEqual(serializer.data['province'], 'Madrid')


class MeetingListSerializerTest(TestCase):
    """Pruebas para MeetingListSerializer."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = UserFactory()
        self.meeting = MeetingFactory()
    
    def test_meeting_list_serializer(self):
        request = self.factory.get('/')
        request.user = self.user
        
        serializer = MeetingListSerializer(
            self.meeting,
            context={'request': request}
        )
        
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('title', data)
        self.assertIn('city_name', data)
        self.assertIn('creator_name', data)
        self.assertIn('confirmed_attendees', data)
        self.assertIn('available_spots', data)
        self.assertIn('is_attending', data)


class MeetingDetailSerializerTest(TestCase):
    """Pruebas para MeetingDetailSerializer."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.creator = UserFactory()
        self.city = CityFactory()
        self.pet = PetFactory(owner=self.creator)
    
    def test_create_meeting_serializer(self):
        request = self.factory.post('/')
        request.user = self.creator
        
        data = {
            'title': 'Paseo por el Retiro',
            'description': 'Un paseo agradable',
            'date': (date.today() + timedelta(days=7)).isoformat(),
            'start_time': '17:00:00',
            'end_time': '19:00:00',
            'location': 'Puerta de Alcalá',
            'city_id': self.city.id,
            'max_participants': 10,
            'pet_ids': [self.pet.id]
        }
        
        serializer = MeetingDetailSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid(), serializer.errors)
        meeting = serializer.save()
        
        self.assertEqual(meeting.creator, self.creator)
        self.assertEqual(meeting.title, 'Paseo por el Retiro')
        self.assertEqual(meeting.pets.count(), 1)
    
    def test_validate_pets_belong_to_creator(self):
        """Validar que las mascotas pertenezcan al creador."""
        request = self.factory.post('/')
        request.user = self.creator
        
        other_user = UserFactory()
        other_pet = PetFactory(owner=other_user)
        
        data = {
            'title': 'Paseo por el Retiro',
            'description': 'Un paseo agradable',
            'date': (date.today() + timedelta(days=7)).isoformat(),
            'start_time': '17:00:00',
            'end_time': '19:00:00',
            'location': 'Puerta de Alcalá',
            'city_id': self.city.id,
            'max_participants': 10,
            'pet_ids': [other_pet.id]  # Mascota de otro usuario
        }
        
        serializer = MeetingDetailSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('pet_ids', serializer.errors)
    
    def test_validate_future_date(self):
        """Validar que la fecha no sea pasada."""
        request = self.factory.post('/')
        request.user = self.creator
        
        data = {
            'title': 'Paseo por el Retiro',
            'description': 'Un paseo agradable',
            'date': (date.today() - timedelta(days=1)).isoformat(),  # Fecha pasada
            'start_time': '17:00:00',
            'end_time': '19:00:00',
            'location': 'Puerta de Alcalá',
            'city_id': self.city.id,
            'max_participants': 10,
        }
        
        serializer = MeetingDetailSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('date', serializer.errors)


class AttendanceSerializerTest(TestCase):
    """Pruebas para AttendanceSerializer."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = UserFactory()
        self.meeting = MeetingFactory(max_participants=10)
        self.pet = PetFactory(owner=self.user)
    
    def test_create_attendance_serializer(self):
        request = self.factory.post('/')
        request.user = self.user
        
        data = {
            'meeting': self.meeting.id,
            'pet_ids': [self.pet.id],
            'notes': 'Llegaré puntual'
        }
        
        serializer = AttendanceSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid(), serializer.errors)
        attendance = serializer.save()
        
        self.assertEqual(attendance.user, self.user)
        self.assertEqual(attendance.meeting, self.meeting)
        self.assertEqual(attendance.pets.count(), 1)
        self.assertEqual(attendance.notes, 'Llegaré puntual')
    
    def test_cannot_join_full_meeting(self):
        """No se puede unir a un encuentro lleno."""
        meeting = MeetingFactory(max_participants=1)
        AttendanceFactory(meeting=meeting)  # Llena el encuentro
        
        request = self.factory.post('/')
        request.user = self.user
        
        data = {
            'meeting': meeting.id,
            'pet_ids': [self.pet.id]
        }
        
        serializer = AttendanceSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)