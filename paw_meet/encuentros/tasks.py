from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from typing import List, Dict, Any, Optional
from django.apps import apps

logger = get_task_logger(__name__)

def resolve_context(context):
    """
    Resuelve automáticamente pares _id/_model en el contexto a objetos Django 

    Conversión:
        'user_id': 1, 'user_model': 'users.CustomUser'
        -> 'user': <CustomUser id=1>
    """
    resolved = {}
    model_keys = {k[:-6] for k in context if k.endswith('_model')}

    for prefix in model_keys:
        id_key = f"{prefix}_id"
        model_key = f'{prefix}_model'

        if id_key not in context:
            logger.warning(f"resolved_context: se encontró {model_key} pero no {id_key} asociada")
            continue

        app_label, model = context[model_key].split('.')
        model = apps.get_model(app_label, model)
        resolved[prefix] = model.objects.get(id = context[id_key])

    # Mantener los campos de contexto que no intersan
    meta_keys = {k for k in context if k.endswith('_id') or k.endswith('_model')}
    for k, v in context.items():
        if k not in meta_keys:
            resolved[k] = v
    
    return resolved

@shared_task(
    name='meetings.tasks.send_email',
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minuto entre reintentos
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,  # Máximo 5 minutos
    retry_jitter=True
)
def send_email_task(
    self,
    subject: str,
    recipient_list: List[str],
    template_name: str,
    context: Dict[str, Any]
) -> int:
    """
    Tarea Celery para enviar emails con plantillas HTML de forma asíncrona.
    
    Args:
        subject: Asunto del correo
        recipient_list: Lista de destinatarios
        template_name: Ruta de la plantilla (ej: 'encuentros/emails/attendance_confirmed.html')
        context: Diccionario con el contexto para la plantilla
    
    Returns:
        Número de emails enviados (1 si éxito, 0 si no hay destinatarios)
    """
    if not recipient_list:
        logger.warning("Intento de enviar email sin destinatarios")
        return 0
    
    try:
        # Mapear objetos de contexto a JSON serializable
        resolved_context = resolve_context(context)
        print(f"DEBUG: {resolved_context}")
        context.update(resolved_context)

        # Añadir contexto común
        context.update({
            'site_name': 'PawMeet',
            'site_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:3000'),
            'current_year': __import__('datetime').datetime.now().year,
        })
        
        # Renderizar plantilla HTML
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)
        
        # Crear y enviar email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            to=recipient_list
        )
        email.attach_alternative(html_content, "text/html")
        
        sent_count = email.send()
        
        logger.info(
            f"Email enviado exitosamente",
            extra={
                'subject': subject,
                'recipients': recipient_list,
                'template': template_name,
                'task_id': self.request.id
            }
        )
        
        return sent_count
        
    except Exception as exc:
        logger.error(
            f"Error al enviar email: {exc}",
            extra={
                'subject': subject,
                'recipients': recipient_list,
                'template': template_name,
                'task_id': self.request.id
            },
            exc_info=True
        )
        # Reintentar con backoff exponencial
        raise self.retry(exc=exc)


@shared_task(
    name='encuentros.tasks.send_attendance_confirmation',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def send_attendance_confirmation_task(self, attendance_id: int) -> Dict[str, Any]:
    """
    Tarea para enviar email de confirmación de asistencia.
    """
    from encuentros.models import Attendance
    
    try:
        attendance = Attendance.objects.select_related(
            'meeting', 'meeting__city', 'meeting__creator', 'user'
        ).prefetch_related('pets').get(id=attendance_id)
    except Attendance.DoesNotExist:
        logger.error(f"Attendance con id {attendance_id} no encontrada")
        return {'status': 'error', 'message': 'Attendance not found'}
    
    # Contexto para el asistente
    context = {
        'user_id': attendance.user.id,
        'user_model': 'users.CustomUser',
        'meeting_id': attendance.meeting.id,
        'meeting_model': 'encuentros.Meeting',
        'attendance_id': attendance.id,
        'attendance_model': 'encuentros.Attendance',
    }
    
    # Enviar al asistente
    send_email_task.delay(
        subject=f"[PawMeet] Has confirmado tu asistencia a: {attendance.meeting.title}",
        recipient_list=[attendance.user.email],
        template_name='encuentros/emails/attendance_confirmed.html',
        context=context
    )
    
    # Notificar al creador (si no es el mismo)
    if attendance.user != attendance.meeting.creator:
        context_creator = {
            'user_id': attendance.meeting.creator.id,
            'user_model': 'users.CustomUser',
            'attendee_id': attendance.user.id,
            'attendee_model': 'users.CustomUser',
            'meeting_id': attendance.meeting.id,
            'meeting_model': 'encuentros.Meeting',
        }
        send_email_task.delay(
            subject=f"[PawMeet] Nuevo asistente en tu encuentro: {attendance.meeting.title}",
            recipient_list=[attendance.meeting.creator.email],
            template_name='encuentros/emails/new_attendee.html',
            context=context_creator
        )
    
    logger.info(f"Tareas de email de confirmación encoladas para attendance {attendance_id}")
    return {'status': 'success', 'attendance_id': attendance_id}


@shared_task(
    name='encuentros.tasks.send_attendance_cancellation',
    bind=True,
    max_retries=3
)
def send_attendance_cancellation_task(self, attendance_id: int, user_id: int, meeting_id: int) -> Dict[str, Any]:
    """
    Tarea para enviar email de cancelación de asistencia.
    Se pasan IDs en lugar de objetos para evitar problemas de serialización.
    """
    from encuentros.models import Meeting, Attendance
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        meeting = Meeting.objects.select_related('city', 'creator').get(id=meeting_id)
        user = User.objects.get(id=user_id)
        attendance = Attendance.objects.select_related(
            'meeting', 'meeting__city', 'meeting__creator', 'user'
        ).prefetch_related('pets').get(id=attendance_id)
    except (Meeting.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Error al obtener objetos para cancelación: {e}")
        return {'status': 'error', 'message': str(e)}
    
    context = {
        'user_id': meeting.creator.id,
        'user_model': 'users.CustomUser',
        'meeting_id': meeting.id,
        'meeting_model': 'encuentros.Meeting',
    }
    
    # Email al usuario que cancela
    send_email_task.delay(
        subject=f"[PawMeet] Has cancelado tu asistencia a: {meeting.title}",
        recipient_list=[user.email],
        template_name='encuentros/emails/attendance_cancelled.html',
        context=context
    )
    
    # Notificar al creador
    if user != meeting.creator:
        context_creator = {
            'user_id': meeting.creator.id,
            'user_model': 'users.CustomUser',
            'attendance_id': attendance.id,
            'attendance_model': 'encuentros.Attendance',
            'meeting_id': meeting.id,
            'meeting_model': 'encuentros.Meeting'
        }
        send_email_task.delay(
            subject=f"[PawMeet] Un asistente ha cancelado: {meeting.title}",
            recipient_list=[meeting.creator.email],
            template_name='encuentros/emails/attendee_cancelled.html',
            context=context_creator
        )
    
    logger.info(f"Tareas de email de cancelación encoladas para meeting {meeting_id}")
    return {'status': 'success', 'meeting_id': meeting_id}


@shared_task(
    bind=True,
    max_retries=3
)
def send_meeting_created_task(self, meeting_id: int) -> Dict[str, Any]:
    """Tarea para enviar email de confirmación al crear un encuentro."""
    from encuentros.models import Meeting
    
    try:
        meeting = Meeting.objects.select_related('city', 'creator').get(id=meeting_id)
    except Meeting.DoesNotExist:
        logger.error(f"Meeting con id {meeting_id} no encontrado")
        return {'status': 'error', 'message': 'Meeting not found'}
    
    context = {
        'user_name': meeting.creator.get_full_name(),
        'user_email': meeting.creator.email,
        'meeting_title': meeting.title,
        'meeting_date': meeting.date.isoformat(),
        'meeting_start_time': meeting.start_time.strftime('%H:%M'),
        'meeting_end_time': meeting.end_time.strftime('%H:%M'),
        'meeting_location': meeting.location,
        'meeting_city': meeting.city.name,
        'metting_max_capacity': meeting.max_participants,
        'meeting_mascotas': list(meeting.pets.values_list('name', flat=True))
    }
    
    send_email_task.delay(
        subject=f"[PawMeet] Has creado un nuevo encuentro: {meeting.title}",
        recipient_list=[meeting.creator.email],
        template_name='encuentros/emails/meeting_created.html',
        context=context
    )
    
    logger.info(f"Tarea de email de creación encolada para meeting {meeting_id}")
    return {'status': 'success', 'meeting_id': meeting_id}


@shared_task(
    name='encuentros.tasks.send_meeting_updated',
    bind=True,
    max_retries=3
)
def send_meeting_updated_task(self, meeting_id: int, changed_fields: List[str]) -> Dict[str, Any]:
    """Tarea para notificar cambios en el encuentro a todos los asistentes."""
    from encuentros.models import Meeting, Attendance
    
    try:
        meeting = Meeting.objects.select_related('city', 'creator').get(id=meeting_id)
        attendees = meeting.attendees.filter(status='confirmed').exclude(user=meeting.creator)
    except Meeting.DoesNotExist:
        logger.error(f"Meeting con id {meeting_id} no encontrado")
        return {'status': 'error', 'message': 'Meeting not found'}
    
    if not attendees.exists():
        logger.info(f"No hay asistentes que notificar para meeting {meeting_id}")
        return {'status': 'success', 'meeting_id': meeting_id, 'notified': 0}
    
    # Traducir nombres de campos para el email
    field_names = {
        'date': 'fecha',
        'start_time': 'hora de inicio',
        'end_time': 'hora de fin',
        'location': 'ubicación',
        'max_participants': 'capacidad máxima',
        'title': 'título',
        'description': 'descripción',
    }
    changed_fields_es = [field_names.get(f, f) for f in changed_fields]
    
    notified = 0
    for attendance in attendees:
        context = {
            'user_id': attendance.user.id,
            'user_model': 'users.CustomUser',
            'meeting_id': meeting.id,
            'meeting_model': 'encuentros.Meeting',
            'changed_fields': changed_fields_es,
        }
        
        send_email_task.delay(
            subject=f"[PawMeet] Cambios en el encuentro: {meeting.title}",
            recipient_list=[attendance.user.email],
            template_name='encuentros/emails/meeting_updated.html',
            context=context
        )
        notified += 1
    
    logger.info(f"Tareas de email de actualización encoladas para {notified} asistentes del meeting {meeting_id}")
    return {'status': 'success', 'meeting_id': meeting_id, 'notified': notified}


@shared_task(
    name='encuentros.tasks.send_meeting_cancelled',
    bind=True,
    max_retries=3
)
def send_meeting_cancelled_task(self, meeting_id: int, meeting_title: str, creator_email: str, attendee_emails: List[str]) -> Dict[str, Any]:
    """
    Tarea para notificar cancelación de encuentro.
    Recibe datos básicos en lugar de objetos para poder ejecutarse incluso si el meeting ya fue eliminado.
    """
    if not attendee_emails:
        logger.info(f"No hay asistentes que notificar para meeting cancelado {meeting_id}")
        return {'status': 'success', 'meeting_id': meeting_id, 'notified': 0}
    
    context = {
        'meeting_title': meeting_title,
        'meeting_id': meeting_id,
        'meeting_model': 'encuentros.Meeting',
    }
    
    # Notificar al creador
    context_creator = {**context, 'is_creator': True}
    send_email_task.delay(
        subject=f"[PawMeet] Has cancelado tu encuentro: {meeting_title}",
        recipient_list=[creator_email],
        template_name='encuentros/emails/meeting_cancelled_creator.html',
        context=context_creator
    )
    
    # Notificar a cada asistente
    notified = 0
    for email in attendee_emails:
        context_attendee = {**context, 'user_email': email}
        send_email_task.delay(
            subject=f"[PawMeet] Encuentro cancelado: {meeting_title}",
            recipient_list=[email],
            template_name='encuentros/emails/meeting_cancelled.html',
            context=context_attendee
        )
        notified += 1
    
    logger.info(f"Tareas de email de cancelación encoladas para {notified} asistentes del meeting {meeting_id}")
    return {'status': 'success', 'meeting_id': meeting_id, 'notified': notified}


@shared_task(
    name='encuentros.tasks.send_meeting_reminder',
    bind=True,
    max_retries=2
)
def send_meeting_reminder_task(self, attendance_id: int) -> Dict[str, Any]:
    """
    Tarea programada para enviar recordatorio 24h antes del encuentro.
    Esta tarea será llamada por Celery Beat.
    """
    from encuentros.models import Attendance
    
    try:
        attendance = Attendance.objects.select_related(
            'meeting', 'meeting__city', 'user'
        ).get(id=attendance_id, status='confirmed')
    except Attendance.DoesNotExist:
        logger.info(f"Attendance {attendance_id} no encontrada o no está confirmada")
        return {'status': 'skipped', 'attendance_id': attendance_id}
    
    context = {
        'user_id': attendance.user.id,
        'user_model': 'users.CustomUser',
        'meeting_id': attendance.meeting.id,
        'meeting_model': 'encuentros.Meeting',
        'attendance_id': attendance.id,
        'attendance_model': 'encuentros.Attendance'
    }
    
    send_email_task.delay(
        subject=f"[PawMeet] ⏰ Recordatorio: {attendance.meeting.title} es mañana",
        recipient_list=[attendance.user.email],
        template_name='encuentros/emails/meeting_reminder.html',
        context=context
    )
    
    logger.info(f"Recordatorio encolado para attendance {attendance_id}")
    return {'status': 'success', 'attendance_id': attendance_id}


@shared_task(
    name='encuentros.tasks.schedule_meeting_reminders',
    bind=True
)
def schedule_meeting_reminders_task(self) -> Dict[str, Any]:
    """
    Tarea periódica que busca encuentros que ocurren en 24h y encola recordatorios.
    Debe ejecutarse diariamente (ej: todos los días a las 10:00).
    """
    from django.utils import timezone
    from datetime import timedelta
    from encuentros.models import Meeting, Attendance
    
    tomorrow = timezone.now().date() + timedelta(days=1)
    
    # Buscar encuentros programados para mañana
    meetings = Meeting.objects.filter(
        date=tomorrow,
        status=Meeting.MeetingStatus.SCHEDULED
    )
    
    reminders_scheduled = 0
    for meeting in meetings:
        attendances = meeting.attendees.filter(status='confirmed')
        for attendance in attendances:
            # Encolar recordatorio con ETA (Estimated Time of Arrival)
            # para que se ejecute exactamente 24h antes
            reminder_time = meeting.datetime_start - timedelta(hours=24)
            
            send_meeting_reminder_task.apply_async(
                args=[attendance.id],
                eta=reminder_time
            )
            reminders_scheduled += 1
    
    logger.info(f"Programados {reminders_scheduled} recordatorios para mañana")
    return {'status': 'success', 'reminders_scheduled': reminders_scheduled}


@shared_task(
    name='encuentros.tasks.update_meeting_statuses',
    bind=True
)
def update_meeting_statuses_task(self) -> Dict[str, Any]:
    """
    Tarea periódica para actualizar estados de encuentros (SCHEDULED -> ONGOING -> COMPLETED).
    Debe ejecutarse frecuentemente (ej: cada 15 minutos).
    """
    from django.utils import timezone
    from encuentros.models import Meeting, MeetingStatus
    
    now = timezone.now()
    
    # Actualizar a ONGOING
    started = Meeting.objects.filter(
        start_time__lte=now.time(),
        end_time__gte=now.time(),
        status=MeetingStatus.SCHEDULED
    ).update(status=MeetingStatus.ONGOING)
    
    # Actualizar a COMPLETED
    completed = Meeting.objects.filter(
        status__in=[MeetingStatus.SCHEDULED, MeetingStatus.ONGOING]
    ).exclude(
        end_time__gt=now.time()
    ).update(status=MeetingStatus.COMPLETED)
    
    logger.info(f"Estados actualizados: {started} a ONGOING, {completed} a COMPLETED")
    return {
        'status': 'success',
        'started': started,
        'completed': completed,
        'timestamp': now.isoformat()
    }