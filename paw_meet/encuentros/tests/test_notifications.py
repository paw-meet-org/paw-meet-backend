from django.test import TestCase, override_settings
from django.core import mail
from django.utils import timezone
from datetime import timedelta, date

from encuentros.notifications import MeetingNotificationService
from encuentros.models import Attendance, MeetingStatus
from .factories import UserFactory, PetFactory, CityFactory, MeetingFactory, AttendanceFactory


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='http://localhost:3000',
    DEFAULT_FROM_EMAIL='noreply@pawmeet.com'
)
class MeetingNotificationServiceTest(TestCase):
    """Pruebas para el servicio de notificaciones por email."""
    
    def setUp(self):
        self.creator = UserFactory(email='creator@test.com', first_name='Creador')
        self.attendee = UserFactory(email='attendee@test.com', first_name='Asistente')
        self.city = CityFactory()
        self.pet = PetFactory(owner=self.creator)
        
        self.meeting = MeetingFactory(
            creator=self.creator,
            city=self.city,
            title='Paseo de prueba',
            date=date.today() + timedelta(days=7),
            max_participants=10
        )
        self.meeting.pets.add(self.pet)
    
    def test_send_attendance_confirmation(self):
        """Verificar envío de email de confirmación de asistencia."""
        mail.outbox = []
        
        attendance = AttendanceFactory(
            meeting=self.meeting,
            user=self.attendee,
            status=Attendance.AttendanceStatus.CONFIRMED
        )
        
        sent = MeetingNotificationService.send_attendance_confirmation(attendance)
        
        # Debe enviar 2 emails: uno al asistente y otro al creador
        self.assertEqual(sent, 1)  # El método retorna el número de emails enviados al asistente
        self.assertEqual(len(mail.outbox), 2)
        
        # Verificar email al asistente
        attendee_email = mail.outbox[0]
        self.assertEqual(attendee_email.subject, '[PawMeet] Has confirmado tu asistencia a: Paseo de prueba')
        self.assertIn('attendee@test.com', attendee_email.to)
        self.assertIn('Has confirmado tu asistencia', attendee_email.body)
        self.assertIn('text/html', attendee_email.alternatives[0][1])
        
        # Verificar email al creador
        creator_email = mail.outbox[1]
        self.assertEqual(creator_email.subject, '[PawMeet] Nuevo asistente en tu encuentro: Paseo de prueba')
        self.assertIn('creator@test.com', creator_email.to)
    
    def test_send_attendance_cancellation(self):
        """Verificar envío de email de cancelación de asistencia."""
        mail.outbox = []
        
        attendance = AttendanceFactory(
            meeting=self.meeting,
            user=self.attendee,
            status=Attendance.AttendanceStatus.CANCELLED
        )
        
        MeetingNotificationService.send_attendance_cancellation(attendance)
        
        self.assertEqual(len(mail.outbox), 2)
        
        attendee_email = mail.outbox[0]
        self.assertIn('Has cancelado tu asistencia', attendee_email.subject)
        self.assertIn('attendee@test.com', attendee_email.to)
    
    def test_send_meeting_created(self):
        """Verificar envío de email al crear un encuentro."""
        mail.outbox = []
        
        MeetingNotificationService.send_meeting_created(self.meeting)
        
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, '[PawMeet] Has creado un nuevo encuentro: Paseo de prueba')
        self.assertIn('creator@test.com', email.to)
    
    def test_send_meeting_updated(self):
        """Verificar envío de email cuando se actualiza un encuentro."""
        # Añadir asistentes
        AttendanceFactory(meeting=self.meeting, user=self.attendee, status=Attendance.AttendanceStatus.CONFIRMED)
        another_attendee = UserFactory(email='another@test.com')
        AttendanceFactory(meeting=self.meeting, user=another_attendee, status=Attendance.AttendanceStatus.CONFIRMED)
        
        mail.outbox = []
        
        changed_fields = ['date', 'location']
        sent = MeetingNotificationService.send_meeting_updated(self.meeting, changed_fields)
        
        self.assertEqual(sent, 2)  # 2 asistentes notificados
        self.assertEqual(len(mail.outbox), 2)
        
        for email in mail.outbox:
            self.assertIn('Cambios en el encuentro', email.subject)
            self.assertIn('text/html', email.alternatives[0][1])
    
    def test_send_meeting_cancelled(self):
        """Verificar envío de email cuando se cancela un encuentro."""
        # Añadir asistentes
        AttendanceFactory(meeting=self.meeting, user=self.attendee, status=Attendance.AttendanceStatus.CONFIRMED)
        
        mail.outbox = []
        
        sent = MeetingNotificationService.send_meeting_cancelled(self.meeting)
        
        self.assertEqual(sent, 2)  # Creador + asistente
        self.assertEqual(len(mail.outbox), 2)
        
        for email in mail.outbox:
            self.assertIn('Encuentro cancelado', email.subject)
    
    def test_send_reminder(self):
        """Verificar envío de email de recordatorio."""
        mail.outbox = []
        
        attendance = AttendanceFactory(
            meeting=self.meeting,
            user=self.attendee,
            status=Attendance.AttendanceStatus.CONFIRMED
        )
        
        MeetingNotificationService.send_reminder(attendance)
        
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('Recordatorio', email.subject)
        self.assertIn('attendee@test.com', email.to)
    
    def test_email_html_content(self):
        """Verificar que los emails contienen contenido HTML válido."""
        mail.outbox = []
        
        attendance = AttendanceFactory(
            meeting=self.meeting,
            user=self.attendee,
            status=Attendance.AttendanceStatus.CONFIRMED
        )
        
        MeetingNotificationService.send_attendance_confirmation(attendance)
        
        email = mail.outbox[0]
        html_content = email.alternatives[0][0]
        
        # Verificar elementos HTML clave
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<div class="meeting-card">', html_content)
        self.assertIn(self.meeting.title, html_content)
        self.assertIn('🐾 PawMeet', html_content)
    
    def test_empty_recipient_list(self):
        """No debe enviar emails si no hay destinatarios."""
        mail.outbox = []
        
        # Crear meeting sin asistentes adicionales
        MeetingNotificationService.send_meeting_updated(self.meeting, ['date'])
        
        # Solo el creador, pero send_meeting_updated excluye al creador
        self.assertEqual(len(mail.outbox), 0)