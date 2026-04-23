from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta, date

from encuentros.models import Meeting, Attendance, MeetingStatus
from .factories import UserFactory, PetFactory, CityFactory, MeetingFactory, AttendanceFactory


class MeetingViewSetTest(TestCase):
    """Pruebas para MeetingViewSet."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.city = CityFactory()
        self.pet = PetFactory(owner=self.user)
        
        self.client.force_authenticate(user=self.user)
    
    def test_list_meetings(self):
        """GET /api/meetings/ - Listar encuentros."""
        MeetingFactory.create_batch(3, status=MeetingStatus.SCHEDULED)
        
        url = reverse('meeting-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
    
    def test_create_meeting(self):
        """POST /api/meetings/ - Crear encuentro."""
        url = reverse('meeting-list')
        data = {
            'title': 'Paseo por el parque',
            'description': 'Un paseo divertido',
            'date': (date.today() + timedelta(days=7)).isoformat(),
            'start_time': '17:00:00',
            'end_time': '19:00:00',
            'location': 'Parque Central',
            'city_id': self.city.id,
            'max_participants': 10,
            'pet_ids': [self.pet.id]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Meeting.objects.count(), 1)
        self.assertEqual(Meeting.objects.first().creator, self.user)
    
    def test_retrieve_meeting(self):
        """GET /api/meetings/{id}/ - Ver detalle de encuentro."""
        meeting = MeetingFactory(creator=self.user, city=self.city)
        
        url = reverse('meeting-detail', kwargs={'pk': meeting.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], meeting.id)
        self.assertTrue(response.data['is_creator'])
    
    def test_update_meeting_only_creator(self):
        """Solo el creador puede actualizar el encuentro."""
        meeting = MeetingFactory(creator=self.user, city=self.city)
        
        url = reverse('meeting-detail', kwargs={'pk': meeting.id})
        data = {'title': 'Nuevo título'}
        
        # El creador puede actualizar
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Otro usuario no puede
        self.client.force_authenticate(user=self.other_user)
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_delete_meeting_only_creator(self):
        """Solo el creador puede eliminar el encuentro."""
        meeting = MeetingFactory(creator=self.user, city=self.city)
        
        url = reverse('meeting-detail', kwargs={'pk': meeting.id})
        
        # Otro usuario no puede
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # El creador sí puede
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_join_meeting(self):
        """POST /api/meetings/{id}/join/ - Unirse a encuentro."""
        meeting = MeetingFactory(city=self.city, max_participants=10)
        other_user_pet = PetFactory(owner=self.other_user)
        
        self.client.force_authenticate(user=self.other_user)
        url = reverse('meeting-join', kwargs={'pk': meeting.id})
        data = {'pet_ids': [other_user_pet.id], 'notes': 'Allá voy'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Attendance.objects.filter(
                meeting=meeting,
                user=self.other_user,
                status=Attendance.AttendanceStatus.CONFIRMED
            ).exists()
        )
    
    def test_cannot_join_full_meeting(self):
        """No se puede unir a un encuentro lleno."""
        meeting = MeetingFactory(city=self.city, max_participants=1)
        AttendanceFactory(meeting=meeting)  # Llena el encuentro
        
        self.client.force_authenticate(user=self.other_user)
        url = reverse('meeting-join', kwargs={'pk': meeting.id})
        
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_leave_meeting(self):
        """POST /api/meetings/{id}/leave/ - Cancelar asistencia."""
        meeting = MeetingFactory(city=self.city)
        attendance = AttendanceFactory(
            meeting=meeting,
            user=self.other_user,
            status=Attendance.AttendanceStatus.CONFIRMED
        )
        
        self.client.force_authenticate(user=self.other_user)
        url = reverse('meeting-leave', kwargs={'pk': meeting.id})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, Attendance.AttendanceStatus.CANCELLED)
    
    def test_cancel_meeting_creator_only(self):
        """POST /api/meetings/{id}/cancel/ - Cancelar encuentro (solo creador)."""
        meeting = MeetingFactory(creator=self.user, city=self.city)
        
        # Otro usuario no puede cancelar
        self.client.force_authenticate(user=self.other_user)
        url = reverse('meeting-cancel', kwargs={'pk': meeting.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # El creador sí puede
        self.client.force_authenticate(user=self.user)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, MeetingStatus.CANCELLED)
    
    def test_my_meetings(self):
        """GET /api/meetings/my_meetings/ - Encuentros del usuario."""
        # Encuentro creado por el usuario
        created_meeting = MeetingFactory(creator=self.user, city=self.city)
        
        # Encuentro donde asiste
        attending_meeting = MeetingFactory(city=self.city)
        AttendanceFactory(
            meeting=attending_meeting,
            user=self.user,
            status=Attendance.AttendanceStatus.CONFIRMED
        )
        
        # Encuentro que no le interesa
        MeetingFactory(city=self.city)
        
        url = reverse('meeting-my-meetings')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['created']), 1)
        self.assertEqual(len(response.data['attending']), 1)
    
    def test_attendees_list(self):
        """GET /api/meetings/{id}/attendees/ - Listar asistentes."""
        meeting = MeetingFactory(city=self.city)
        AttendanceFactory.create_batch(
            3,
            meeting=meeting,
            status=Attendance.AttendanceStatus.CONFIRMED
        )
        
        url = reverse('meeting-attendees', kwargs={'pk': meeting.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
    
    def test_filter_meetings_by_city(self):
        """Filtrar encuentros por ciudad."""
        city1 = CityFactory(name='Madrid')
        city2 = CityFactory(name='Barcelona')
        
        MeetingFactory.create_batch(2, city=city1, status=MeetingStatus.SCHEDULED)
        MeetingFactory.create_batch(3, city=city2, status=MeetingStatus.SCHEDULED)
        
        url = reverse('meeting-list') + f'?city={city1.id}'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_filter_meetings_by_date_range(self):
        """Filtrar encuentros por rango de fechas."""
        today = date.today()
        
        MeetingFactory(date=today + timedelta(days=1), status=MeetingStatus.SCHEDULED)
        MeetingFactory(date=today + timedelta(days=5), status=MeetingStatus.SCHEDULED)
        MeetingFactory(date=today + timedelta(days=10), status=MeetingStatus.SCHEDULED)
        
        url = reverse('meeting-list') + f'?date_from={today.isoformat()}&date_to={(today + timedelta(days=7)).isoformat()}'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_search_meetings(self):
        """Buscar encuentros por título/descripción."""
        MeetingFactory(title='Paseo por el Retiro', status=MeetingStatus.SCHEDULED)
        MeetingFactory(title='Quedada en la playa', status=MeetingStatus.SCHEDULED)
        MeetingFactory(description='Otro paseo diferente', status=MeetingStatus.SCHEDULED)
        
        url = reverse('meeting-list') + '?search=Retiro'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Paseo por el Retiro')


class CityViewSetTest(TestCase):
    """Pruebas para CityViewSet."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
    
    def test_list_cities(self):
        CityFactory.create_batch(5)
        
        url = reverse('city-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)
    
    def test_search_cities(self):
        CityFactory(name='Madrid', province='Madrid')
        CityFactory(name='Barcelona', province='Barcelona')
        CityFactory(name='Valencia', province='Valencia')
        
        url = reverse('city-list') + '?search=Madrid'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Madrid')