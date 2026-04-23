from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone


class MeetingStatus(models.TextChoices):
    """Estados posibles de un encuentro."""
    SCHEDULED = 'scheduled', 'Programado'
    ONGOING = 'ongoing', 'En curso'
    COMPLETED = 'completed', 'Completado'
    CANCELLED = 'cancelled', 'Cancelado'


class City(models.Model):
    """Ciudades donde se realizan los encuentros."""
    name = models.CharField(max_length=100, unique=True)
    province = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name}, {self.province}" if self.province else self.name


class Meeting(models.Model):
    """Modelo principal de encuentros."""
    
    # Relaciones
    creator = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='created_meetings'
    )
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name='meetings'
    )
    # Mascotas que asisten al encuentro (solo del creador inicialmente)
    pets = models.ManyToManyField(
        'users.Pet',
        related_name='meetings',
        blank=True
    )
    
    # Información básica
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(
        max_length=255,
        help_text="Dirección o punto de encuentro específico"
    )
    location_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitud para geolocalización"
    )
    location_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitud para geolocalización"
    )
    
    # Fechas
    date = models.DateField(help_text="Fecha del encuentro")
    start_time = models.TimeField(help_text="Hora de inicio")
    end_time = models.TimeField(help_text="Hora de finalización")
    
    # Capacidad y estado
    max_participants = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(2), MaxValueValidator(100)],
        help_text="Número máximo de participantes (incluye al creador)"
    )
    status = models.CharField(
        max_length=20,
        choices=MeetingStatus.choices,
        default=MeetingStatus.SCHEDULED
    )
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Encuentro"
        verbose_name_plural = "Encuentros"
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['city', 'date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.date} {self.start_time}"
    
    def clean(self):
        """Validaciones a nivel de modelo."""
        # Validar que la fecha no sea pasada
        if self.date and self.date < timezone.now().date():
            raise ValidationError({'date': 'La fecha del encuentro no puede ser anterior a hoy.'})
        
        # Validar que la hora de fin sea posterior a la de inicio
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({'end_time': 'La hora de fin debe ser posterior a la hora de inicio.'})
    
    @property
    def datetime_start(self):
        """Combina fecha y hora de inicio en un datetime."""
        return timezone.make_aware(
            timezone.datetime.combine(self.date, self.start_time)
        )
    
    @property
    def datetime_end(self):
        """Combina fecha y hora de fin en un datetime."""
        return timezone.make_aware(
            timezone.datetime.combine(self.date, self.end_time)
        )
    
    @property
    def is_full(self):
        """Verifica si el encuentro ha alcanzado su capacidad máxima."""
        return self.attendees.filter(status='confirmed').count() >= self.max_participants
    
    @property
    def is_past(self):
        """Verifica si el encuentro ya ha pasado."""
        return self.datetime_end < timezone.now()
    
    @property
    def available_spots(self):
        """Número de plazas disponibles."""
        confirmed = self.attendees.filter(status='confirmed').count()
        return max(0, self.max_participants - confirmed)
    
    def can_be_joined(self):
        """Verifica si un usuario puede unirse al encuentro."""
        return (
            self.status == MeetingStatus.SCHEDULED
            and not self.is_past
            and not self.is_full
        )
    
    def update_status(self):
        """Actualiza automáticamente el estado según la fecha/hora actual."""
        now = timezone.now()
        if self.datetime_start <= now <= self.datetime_end:
            if self.status != MeetingStatus.ONGOING:
                self.status = MeetingStatus.ONGOING
                self.save(update_fields=['status'])
        elif now > self.datetime_end and self.status == MeetingStatus.SCHEDULED:
            self.status = MeetingStatus.COMPLETED
            self.save(update_fields=['status'])


class Attendance(models.Model):
    """Modelo para gestionar la asistencia de usuarios a encuentros."""
    
    class AttendanceStatus(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmado'
        CANCELLED = 'cancelled', 'Cancelado'
        ATTENDED = 'attended', 'Asistió'
        NO_SHOW = 'no_show', 'No asistió'
    
    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name='attendees'
    )
    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    pets = models.ManyToManyField(
        'users.Pet',
        related_name='attendances',
        blank=True,
        help_text="Mascotas que trae el usuario a este encuentro"
    )
    status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.CONFIRMED
    )
    notes = models.TextField(blank=True, help_text="Notas adicionales del asistente")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Asistencia"
        verbose_name_plural = "Asistencias"
        unique_together = ['meeting', 'user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.meeting.title} ({self.status})"
    
    def clean(self):
        """Validaciones a nivel de modelo."""
        # No permitir unirse a un encuentro lleno (excepto si ya está confirmado)
        if self.status == self.AttendanceStatus.CONFIRMED:
            if not self.pk and self.meeting.is_full:
                raise ValidationError('El encuentro ha alcanzado su capacidad máxima.')
        
        # No permitir unirse a encuentros pasados o cancelados
        if self.status == self.AttendanceStatus.CONFIRMED:
            if not self.meeting.can_be_joined():
                raise ValidationError('No es posible unirse a este encuentro.')