from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.core import mail
from django.utils import timezone
from datetime import timedelta, date
from unittest.mock import patch
import logging

from encuentros.models import Meeting, Attendance, MeetingStatus
from .factories import UserFactory, PetFactory, CityFactory, MeetingFactory, AttendanceFactory


logger = logging.getLogger(__name__)

@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CELERY_TASK_EAGER_PROPAGATES=True,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_BROKER_URL='memory://',      # <-- sin Redis, sin Docker
    CELERY_BACKEND='cache+memory://',   # <-- sin backend externo
)
class MeetingWorkflowIntegrationTest(TestCase):
    """
    Pruebas de integración que simulan el flujo completo de uso de la app.
    """
    
    def setUp(self):
        self.client = APIClient()
        
        # Crear usuarios
        self.creator = UserFactory(email='creator@test.com')
        self.attendee1 = UserFactory(email='attendee1@test.com')
        self.attendee2 = UserFactory(email='attendee2@test.com')
        
        # Crear mascotas
        self.creator_pet = PetFactory(owner=self.creator, name='Max')
        self.attendee1_pet = PetFactory(owner=self.attendee1, name='Luna')
        self.attendee2_pet = PetFactory(owner=self.attendee2, name='Rocky')
        
        # Crear ciudad
        self.city = CityFactory(name='Madrid')
        
        # Limpiar buzón de correo
        mail.outbox = []
    
    def test_complete_meeting_lifecycle(self):
        """
        Flujo completo:
        1. Creador crea un encuentro
        2. Usuarios se unen al encuentro
        3. Creador actualiza detalles
        4. Un usuario cancela asistencia
        5. Creador cancela el encuentro
        """
        
        # ========== 1. CREAR ENCUENTRO ==========
        self.client.force_authenticate(user=self.creator)
        
        create_url = reverse('meeting-list')
        meeting_data = {
            'title': 'Paseo por el Retiro',
            'description': 'Paseo dominical por el parque',
            'date': (date.today() + timedelta(days=7)).isoformat(),
            'start_time': '10:00:00',
            'end_time': '12:00:00',
            'location': 'Puerta de Alcalá',
            'city_id': self.city.id,
            'max_participants': 5,
            'pet_ids': [self.creator_pet.id]
        }
        with patch('django.db.transaction.on_commit', lambda f: f()):
            response = self.client.post(create_url, meeting_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        meeting_id = response.data['id']
        
        # Verificar email de creación
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Has creado un nuevo encuentro', mail.outbox[0].subject)
        mail.outbox = []
        
        # ========== 2. ASISTENTES SE UNEN ==========
        
        # Asistente 1 se une
        self.client.force_authenticate(user=self.attendee1)
        join_url = reverse('meeting-join', kwargs={'pk': meeting_id})
        
        join_data = {'pet_ids': [self.attendee1_pet.id], 'notes': '¡Allá vamos!'}
        print(join_data)
        response = self.client.post(join_url, join_data, format='json')
        print(response)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verificar emails (confirmación al asistente + notificación al creador)
        self.assertEqual(len(mail.outbox), 2)
        mail.outbox = []
        
        # Asistente 2 se une
        self.client.force_authenticate(user=self.attendee2)
        join_data = {'pet_ids': [self.attendee2_pet.id]}
        
        response = self.client.post(join_url, join_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        self.assertEqual(len(mail.outbox), 2)
        mail.outbox = []
        
        # ========== 3. VER LISTA DE ASISTENTES ==========
        attendees_url = reverse('meeting-attendees', kwargs={'pk': meeting_id})
        response = self.client.get(attendees_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # ========== 4. CREADOR ACTUALIZA ENCUENTRO ==========
        self.client.force_authenticate(user=self.creator)
        update_url = reverse('meeting-detail', kwargs={'pk': meeting_id})
        update_data = {
            'location': 'Puerta del Ángel Caído',  # Cambio de ubicación
            'start_time': '10:30:00'  # Cambio de hora
        }
        
        response = self.client.patch(update_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar que se notificó a los 2 asistentes
        self.assertEqual(len(mail.outbox), 2)
        for email in mail.outbox:
            self.assertIn('Cambios en el encuentro', email.subject)
        mail.outbox = []
        
        # ========== 5. ASISTENTE CANCELA ==========
        self.client.force_authenticate(user=self.attendee1)
        leave_url = reverse('meeting-leave', kwargs={'pk': meeting_id})
        
        response = self.client.post(leave_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar emails de cancelación
        self.assertEqual(len(mail.outbox), 2)
        mail.outbox = []
        
        # Verificar que ya no aparece en asistentes confirmados
        response = self.client.get(attendees_url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['user_email'], 'attendee2@test.com')
        
        # ========== 6. CREADOR CANCELA ENCUENTRO ==========
        self.client.force_authenticate(user=self.creator)
        cancel_url = reverse('meeting-cancel', kwargs={'pk': meeting_id})
        
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar que se notificó a los asistentes restantes
        self.assertGreater(len(mail.outbox), 0)
        
        # Verificar estado del encuentro
        meeting = Meeting.objects.get(id=meeting_id)
        self.assertEqual(meeting.status, MeetingStatus.CANCELLED)
    
    def test_capacity_limit_workflow(self):
        """Prueba el flujo cuando se alcanza el límite de capacidad."""
        
        # Crear encuentro con capacidad 2
        self.client.force_authenticate(user=self.creator)
        create_url = reverse('meeting-list')
        meeting_data = {
            'title': 'Paseo limitado',
            'description': 'Solo 2 plazas',
            'date': (date.today() + timedelta(days=7)).isoformat(),
            'start_time': '10:00:00',
            'end_time': '12:00:00',
            'location': 'Parque',
            'city_id': self.city.id,
            'max_participants': 2,
            'pet_ids': [self.creator_pet.id]
        }
        
        response = self.client.post(create_url, meeting_data, format='json')
        meeting_id = response.data['id']
        
        # Asistente 1 se une
        self.client.force_authenticate(user=self.attendee1)
        join_url = reverse('meeting-join', kwargs={'pk': meeting_id})
        response = self.client.post(join_url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Asistente 2 se une
        self.client.force_authenticate(user=self.attendee2)
        response = self.client.post(join_url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Tercer asistente intenta unirse (debe fallar)
        third_attendee = UserFactory(email='third@test.com')
        self.client.force_authenticate(user=third_attendee)
        response = self.client.post(join_url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_search_and_filter_workflow(self):
        """Prueba búsqueda y filtrado de encuentros."""
        
        city_madrid = self.city
        city_barcelona = CityFactory(name='Barcelona')
        
        # Crear varios encuentros
        self.client.force_authenticate(user=self.creator)
        create_url = reverse('meeting-list')
        
        # Encuentro en Madrid (hoy + 3 días)
        meeting1_data = {
            'title': 'Paseo matutino',
            'description': 'Por la mañana',
            'date': (date.today() + timedelta(days=3)).isoformat(),
            'start_time': '09:00:00',
            'end_time': '11:00:00',
            'location': 'Parque Retiro',
            'city_id': city_madrid.id,
            'max_participants': 10,
        }
        self.client.post(create_url, meeting1_data, format='json')
        
        # Encuentro en Madrid (hoy + 5 días)
        meeting2_data = {
            'title': 'Paseo vespertino',
            'description': 'Por la tarde',
            'date': (date.today() + timedelta(days=5)).isoformat(),
            'start_time': '17:00:00',
            'end_time': '19:00:00',
            'location': 'Casa de Campo',
            'city_id': city_madrid.id,
            'max_participants': 10,
        }
        self.client.post(create_url, meeting2_data, format='json')
        
        # Encuentro en Barcelona
        meeting3_data = {
            'title': 'Paseo playero',
            'description': 'Por la playa',
            'date': (date.today() + timedelta(days=4)).isoformat(),
            'start_time': '10:00:00',
            'end_time': '12:00:00',
            'location': 'Barceloneta',
            'city_id': city_barcelona.id,
            'max_participants': 10,
        }
        self.client.post(create_url, meeting3_data, format='json')
        
        # Probar filtro por ciudad
        list_url = reverse('meeting-list')
        response = self.client.get(f'{list_url}?city={city_madrid.id}')
        self.assertEqual(len(response.data), 2)
        
        # Probar búsqueda por texto
        response = self.client.get(f'{list_url}?search=playero')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Paseo playero')
        
        # Probar filtro por rango de fechas
        date_from = date.today() + timedelta(days=2)
        date_to = date.today() + timedelta(days=4)
        response = self.client.get(
            f'{list_url}?date_from={date_from.isoformat()}&date_to={date_to.isoformat()}'
        )
        self.assertEqual(len(response.data), 2)  # Madrid día 3 y Barcelona día 4