"""
Servicio de notificaciones para meetings.
Este módulo ahora delega el envío real de emails a tareas Celery.
"""

from typing import List, Dict, Any
from . import tasks


class MeetingNotificationService:
    """
    Servicio para encolar notificaciones de encuentros.
    Todos los métodos son síncronos pero delegan en tareas asíncronas de Celery.
    """
    
    @staticmethod
    def send_attendance_confirmation(attendance) -> None:
        """
        Encola email de confirmación cuando un usuario se une a un encuentro.
        """
        tasks.send_attendance_confirmation_task.delay(attendance.id)
    
    @staticmethod
    def send_attendance_cancellation(attendance) -> None:
        """
        Encola email cuando un usuario cancela su asistencia.
        """
        tasks.send_attendance_cancellation_task.delay(
            attendance_id=attendance.id,
            user_id=attendance.user_id,
            meeting_id=attendance.meeting_id
        )
    
    @staticmethod
    def send_meeting_created(meeting) -> None:
        """
        Encola email de confirmación al creador cuando crea un encuentro.
        """
        print(f"DEBUG: Identificador del meeting: {meeting.id}")
        tasks.send_meeting_created_task.delay(meeting.id)
    
    @staticmethod
    def send_meeting_updated(meeting, changed_fields: List[str]) -> None:
        """
        Encola emails a todos los asistentes cuando el encuentro es modificado.
        """
        tasks.send_meeting_updated_task.delay(meeting.id, changed_fields)
    
    @staticmethod
    def send_meeting_cancelled(meeting) -> None:
        """
        Encola emails a todos los asistentes cuando el encuentro es cancelado.
        """
        attendee_emails = list(
            meeting.attendees.filter(status='confirmed')
            .values_list('user__email', flat=True)
        )
        
        tasks.send_meeting_cancelled_task.delay(
            meeting_id=meeting.id,
            meeting_title=meeting.title,
            creator_email=meeting.creator.email,
            attendee_emails=attendee_emails
        )
    
    @staticmethod
    def send_reminder(attendance) -> None:
        """
        Encola email de recordatorio al asistente.
        """
        tasks.send_meeting_reminder_task.delay(attendance.id)