from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, date, time

from encuentros.models import Meeting, Attendance, City, MeetingStatus
from .factories import (
    UserFactory, PetFactory, PetTypeFactory,
    CityFactory, MeetingFactory, AttendanceFactory
)


class CityModelTest(TestCase):
    """Pruebas para el modelo City."""
    
    def test_create_city(self):
        city = CityFactory(name='Madrid', province='Madrid')
        self.assertEqual(str(city), 'Madrid, Madrid')
    
    def test_city_without_province(self):
        city = CityFactory(name='Madrid', province='')
        self.assertEqual(str(city), 'Madrid')
    
    def test_city_unique_name(self):
        CityFactory(name='Madrid')
        with self.assertRaises(Exception):
            CityFactory(name='Madrid')


class MeetingModelTest(TestCase):
    """Pruebas para el modelo Meeting."""
    
    def setUp(self):
        self.creator = UserFactory()
        self.city = CityFactory()
        self.pet = PetFactory(owner=self.creator)
    
    def test_create_meeting(self):
        meeting = MeetingFactory(
            creator=self.creator,
            city=self.city,
            title='Paseo por el parque',
            date=date.today() + timedelta(days=7),
            start_time=time(17, 0),
            end_time=time(19, 0)
        )
        meeting.pets.add(self.pet)
        
        self.assertEqual(str(meeting), f"Paseo por el parque - {meeting.date} 17:00:00")
        self.assertEqual(meeting.status, MeetingStatus.SCHEDULED)
        self.assertFalse(meeting.is_full)
        self.assertFalse(meeting.is_past)
        self.assertEqual(meeting.available_spots, 10)
    
    def test_meeting_past_date_validation(self):
        """No se puede crear un encuentro con fecha pasada."""
        meeting = MeetingFactory.build(
            creator=self.creator,
            city=self.city,
            date=date.today() - timedelta(days=1)
        )
        with self.assertRaises(ValidationError) as context:
            meeting.clean()
        self.assertIn('date', context.exception.error_dict)

    def test_clean_valid_meeting(self):
        """Un encuentro válido no debería lanzar errores."""
        from datetime import date, timedelta, time
        
        encuentro = Meeting(
            creator=self.creator,
            city=self.city,
            title='Paseo válido',
            date=date.today() + timedelta(days=7),
            start_time=time(10, 0),
            end_time=time(12, 0),
            max_participants=10,
            status = self.status
        )
        
        # No debería lanzar excepción
        try:
            encuentro.clean()
        except ValidationError:
            self.fail("clean() lanzó ValidationError inesperadamente")
    
    def test_end_time_before_start_time_validation(self):
        """La hora de fin debe ser posterior a la de inicio."""
        meeting = MeetingFactory.build(
            creator=self.creator,
            city=self.city,
            start_time=time(19, 0),
            end_time=time(17, 0)
        )
        with self.assertRaises(ValidationError) as context:
            meeting.clean()
        self.assertIn('end_time', context.exception.error_dict)
    
    def test_is_full_property(self):
        meeting = MeetingFactory(max_participants=2)
        
        # Añadir un asistente (total: 1 creador implícito? No, el creador no cuenta como asistente)
        # Añadir 2 asistentes confirmados
        AttendanceFactory(meeting=meeting, status=Attendance.AttendanceStatus.CONFIRMED)
        self.assertFalse(meeting.is_full)
        
        AttendanceFactory(meeting=meeting, status=Attendance.AttendanceStatus.CONFIRMED)
        self.assertTrue(meeting.is_full)
    
    def test_is_past_property(self):
        past_meeting = MeetingFactory(
            date=date.today() - timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(12, 0)
        )
        self.assertTrue(past_meeting.is_past)
        
        future_meeting = MeetingFactory(
            date=date.today() + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(12, 0)
        )
        self.assertFalse(future_meeting.is_past)
    
    def test_can_be_joined(self):
        # Encuentro válido
        valid_meeting = MeetingFactory(status=MeetingStatus.SCHEDULED)
        self.assertTrue(valid_meeting.can_be_joined())
        
        # Encuentro cancelado
        cancelled_meeting = MeetingFactory(status=MeetingStatus.CANCELLED)
        self.assertFalse(cancelled_meeting.can_be_joined())
        
        # Encuentro lleno
        full_meeting = MeetingFactory(max_participants=1)
        AttendanceFactory(meeting=full_meeting, status=Attendance.AttendanceStatus.CONFIRMED)
        self.assertFalse(full_meeting.can_be_joined())
        
        # Encuentro pasado
        past_meeting = MeetingFactory(
            date=date.today() - timedelta(days=1),
            status=MeetingStatus.SCHEDULED
        )
        self.assertFalse(past_meeting.can_be_joined())
    
    def test_update_status(self):
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        # Encuentro en curso (hora actual entre start y end)
        now = timezone.now()
        ongoing_meeting = MeetingFactory(
            date=now.date(),
            start_time=(now - timedelta(hours=1)).time(),
            end_time=(now + timedelta(hours=1)).time(),
            status=MeetingStatus.SCHEDULED
        )
        ongoing_meeting.update_status()
        ongoing_meeting.refresh_from_db()
        self.assertEqual(ongoing_meeting.status, MeetingStatus.ONGOING)


class AttendanceModelTest(TestCase):
    """Pruebas para el modelo Attendance."""
    
    def setUp(self):
        self.meeting = MeetingFactory(max_participants=5)
        self.user = UserFactory()
        self.pet = PetFactory(owner=self.user)
    
    def test_create_attendance(self):
        attendance = AttendanceFactory(
            meeting=self.meeting,
            user=self.user,
            status=Attendance.AttendanceStatus.CONFIRMED
        )
        attendance.pets.add(self.pet)
        
        self.assertEqual(
            str(attendance),
            f"{self.user.email} - {self.meeting.title} (confirmed)"
        )
    
    def test_unique_together_meeting_user(self):
        """Un usuario no puede tener dos asistencias al mismo encuentro."""
        AttendanceFactory(meeting=self.meeting, user=self.user)
        with self.assertRaises(Exception):
            AttendanceFactory(meeting=self.meeting, user=self.user)
    
    def test_cannot_join_full_meeting(self):
        """No se puede unir a un encuentro lleno."""
        meeting = MeetingFactory(max_participants=1)
        AttendanceFactory(meeting=meeting)  # Primera asistencia (llena)
        
        attendance = AttendanceFactory.build(meeting=meeting, user=self.user)
        with self.assertRaises(ValidationError):
            attendance.clean()
    
    def test_cannot_join_past_meeting(self):
        """No se puede unir a un encuentro pasado."""
        past_meeting = MeetingFactory(
            date=date.today() - timedelta(days=1),
            status=MeetingStatus.SCHEDULED
        )
        attendance = AttendanceFactory.build(meeting=past_meeting, user=self.user)
        with self.assertRaises(ValidationError):
            attendance.clean()