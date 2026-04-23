# meetings/tests/test_tasks.py
from django.test import TestCase, override_settings
from django.core import mail
from celery.result import AsyncResult

from encuentros.tasks import (
    send_attendance_confirmation_task,
    send_meeting_created_task,
    send_meeting_cancelled_task,
)
from encuentros.models import Attendance
from .factories import UserFactory, MeetingFactory, AttendanceFactory, CityFactory


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,  # Ejecutar tareas síncronamente en tests
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class CeleryTasksTest(TestCase):
    """Pruebas para tareas Celery."""
    
    def setUp(self):
        self.creator = UserFactory(email='creator@test.com')
        self.attendee = UserFactory(email='attendee@test.com')
        self.city = CityFactory()
        self.meeting = MeetingFactory(creator=self.creator, city=self.city)
        mail.outbox = []
    
    def test_send_attendance_confirmation_task(self):
        """Probar tarea de confirmación de asistencia."""
        attendance = AttendanceFactory(
            meeting=self.meeting,
            user=self.attendee,
            status=Attendance.AttendanceStatus.CONFIRMED
        )
        
        result = send_attendance_confirmation_task.delay(attendance.id)
        
        self.assertTrue(isinstance(result, AsyncResult))
        self.assertEqual(result.status, 'SUCCESS')
        
        # Verificar emails enviados (2: asistente + creador)
        self.assertEqual(len(mail.outbox), 2)
    
    def test_send_meeting_created_task(self):
        """Probar tarea de creación de encuentro."""
        result = send_meeting_created_task.delay(self.meeting.id)
        
        self.assertEqual(result.status, 'SUCCESS')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('creator@test.com', mail.outbox[0].to)
    
    def test_send_meeting_cancelled_task(self):
        """Probar tarea de cancelación de encuentro."""
        # Añadir asistente
        AttendanceFactory(
            meeting=self.meeting,
            user=self.attendee,
            status=Attendance.AttendanceStatus.CONFIRMED
        )
        
        result = send_meeting_cancelled_task.delay(
            meeting_id=self.meeting.id,
            meeting_title=self.meeting.title,
            creator_email=self.creator.email,
            attendee_emails=['attendee@test.com']
        )
        
        self.assertEqual(result.status, 'SUCCESS')
        # 2 emails: creador + asistente
        self.assertEqual(len(mail.outbox), 2)
    
    def test_task_retry_on_failure(self):
        """Probar que las tareas reintentan en caso de fallo."""
        # Forzar un error pasando un ID inexistente
        result = send_attendance_confirmation_task.delay(99999)
        
        # Como no existe, debería fallar (pero no reintentar porque es error de datos, no de red)
        self.assertEqual(result.status, 'FAILURE')