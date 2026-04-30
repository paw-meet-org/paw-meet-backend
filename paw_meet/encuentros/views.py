from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Meeting, Attendance, City, MeetingStatus
from .serializers import (
    MeetingListSerializer,
    MeetingDetailSerializer,
    AttendanceSerializer,
    CitySerializer
)
from .notifications import MeetingNotificationService
from . import tasks


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para Ciudades.
    """
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'province']


class MeetingViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar encuentros.
    Las notificaciones se encolan después de confirmar la transacción.
    """
    queryset = Meeting.objects.select_related('city', 'creator').prefetch_related('pets', 'attendees')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['city', 'status', 'date']
    search_fields = ['title', 'description', 'location', 'city__name']
    ordering_fields = ['date', 'start_time', 'created_at']
    ordering = ['date', 'start_time']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return MeetingListSerializer
        return MeetingDetailSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if self.action == 'list':
            queryset = queryset.filter(status__in=['scheduled', 'ongoing'])
        
        city_id = self.request.query_params.get('city')
        if city_id:
            queryset = queryset.filter(city_id=city_id)
        
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Crea el encuentro y encola email de confirmación.
        Usamos transaction.on_commit para asegurar que el email solo se encola
        si la transacción se confirma correctamente.
        """
        with transaction.atomic():
            meeting = serializer.save()
            print("DEBUG: Transacción completada correctamente")
            # Encolar notificación después de confirmar la transacción
            transaction.on_commit(
                lambda: MeetingNotificationService.send_meeting_created(meeting)
            )
    
    def perform_update(self, serializer):
        """Actualiza el encuentro y notifica cambios a los asistentes."""
        with transaction.atomic():
            old_meeting = Meeting.objects.get(pk=self.get_object().pk)
            meeting = serializer.save()
            
            # Detectar campos que cambiaron
            changed_fields = []
            fields_to_check = ['date', 'start_time', 'end_time', 'location', 'max_participants']
            
            for field in fields_to_check:
                old_value = getattr(old_meeting, field)
                new_value = getattr(meeting, field)
                if old_value != new_value:
                    changed_fields.append(field)
            
            # Encolar notificaciones después de confirmar transacción
            if changed_fields:
                transaction.on_commit(
                    lambda: MeetingNotificationService.send_meeting_updated(meeting, changed_fields)
                )
    
    def perform_destroy(self, instance):
        """Cancela el encuentro y notifica a los asistentes."""
        # Guardar datos necesarios antes de eliminar
        meeting_id = instance.id
        meeting_title = instance.title
        creator_email = instance.creator.email
        attendee_emails = list(
            instance.attendees.filter(status='confirmed')
            .values_list('user__email', flat=True)
        )
        
        with transaction.atomic():
            instance.delete()
            
            # Encolar notificación después de confirmar transacción
            if attendee_emails:
                transaction.on_commit(
                    lambda: tasks.send_meeting_cancelled_task.delay(
                        meeting_id=meeting_id,
                        meeting_title=meeting_title,
                        creator_email=creator_email,
                        attendee_emails=attendee_emails
                    )
                )
    
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Endpoint para unirse a un encuentro."""
        meeting : Meeting = self.get_object()
        if not meeting.can_be_joined():
            print(meeting)
            return Response(
                {'error': 'No es posible unirse a este encuentro.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        existing = Attendance.objects.filter(
            meeting=meeting,
            user=request.user,
            status='confirmed'
        ).exists()
        
        if existing:
            return Response(
                {'error': 'Ya estás registrado como asistente.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = AttendanceSerializer(
            data=request.data,
            context={'request': request, 'meeting': meeting}
        )
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            attendance = serializer.save(meeting=meeting)
            
            # Encolar notificación después de confirmar transacción
            transaction.on_commit(
                lambda: MeetingNotificationService.send_attendance_confirmation(attendance)
            )
        
        return Response(
            AttendanceSerializer(attendance).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Endpoint para cancelar asistencia."""
        meeting = self.get_object()
        
        try:
            attendance = meeting.attendees.get(user=request.user, status='confirmed')
        except Attendance.DoesNotExist:
            return Response(
                {'error': 'No estás registrado como asistente.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attendance_id = attendance.id
        user_id = attendance.user_id
        
        with transaction.atomic():
            attendance.status = Attendance.AttendanceStatus.CANCELLED
            attendance.save()
            
            # Encolar notificación después de confirmar transacción
            transaction.on_commit(
                lambda: tasks.send_attendance_cancellation_task.delay(
                    attendance_id=attendance_id,
                    user_id=user_id,
                    meeting_id=meeting.id
                )
            )
        
        return Response({'message': 'Has cancelado tu asistencia correctamente.'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Endpoint para que el creador cancele el encuentro."""
        meeting = self.get_object()
        
        if meeting.creator != request.user:
            return Response(
                {'error': 'Solo el creador puede cancelar este encuentro.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if meeting.status == MeetingStatus.CANCELLED:
            return Response(
                {'error': 'El encuentro ya está cancelado.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attendee_emails = list(
            meeting.attendees.filter(status='confirmed')
            .values_list('user__email', flat=True)
        )
        
        with transaction.atomic():
            meeting.status = MeetingStatus.CANCELLED
            meeting.save()
            
            # Encolar notificación después de confirmar transacción
            transaction.on_commit(
                lambda: tasks.send_meeting_cancelled_task.delay(
                    meeting_id=meeting.id,
                    meeting_title=meeting.title,
                    creator_email=meeting.creator.email,
                    attendee_emails=attendee_emails
                )
            )
        
        return Response({'message': 'Encuentro cancelado correctamente.'})
    
    @action(detail=True, methods=['get'])
    def attendees(self, request, pk=None):
        """
        Endpoint para listar los asistentes confirmados de un encuentro.
        GET /api/meetings/{id}/attendees/
        """
        meeting = self.get_object()
        attendees = meeting.attendees.filter(status='confirmed').select_related('user').prefetch_related('pets')
        serializer = AttendanceSerializer(attendees, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_meetings(self, request):
        """
        Endpoint para listar encuentros donde el usuario es creador o asistente.
        GET /api/meetings/my_meetings/
        """
        user = request.user
        
        created = self.get_queryset().filter(creator=user)
        attending = self.get_queryset().filter(
            attendees__user=user,
            attendees__status='confirmed'
        ).exclude(creator=user)
        
        serializer_created = MeetingListSerializer(created, many=True, context={'request': request})
        serializer_attending = MeetingListSerializer(attending, many=True, context={'request': request})
        
        return Response({
            'created': serializer_created.data,
            'attending': serializer_attending.data
        })
    
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """
        Endpoint para encuentros cercanos (requiere lat/lng).
        GET /api/meetings/nearby/?lat=40.416775&lng=-3.703790&radius=5
        """
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = float(request.query_params.get('radius', 5))
        
        if not lat or not lng:
            return Response(
                {'error': 'Se requieren parámetros lat y lng.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Aquí iría la lógica de búsqueda geoespacial con GeoDjango
        # Por ahora, devolvemos una respuesta indicando que no está implementado
        return Response(
            {'message': 'Funcionalidad en desarrollo', 'lat': lat, 'lng': lng, 'radius': radius},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class AttendanceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar asistencias individualmente.
    """
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'put', 'patch', 'delete', 'head', 'options']
    
    def get_queryset(self):
        """Los usuarios solo ven sus propias asistencias."""
        return Attendance.objects.filter(user=self.request.user).select_related('meeting')
    
    def perform_update(self, serializer):
        """Actualiza asistencia y envía notificaciones si cambia el estado."""
        old_instance = self.get_object()
        attendance = serializer.save()
        
        if old_instance.status == 'confirmed' and attendance.status == 'cancelled':
            MeetingNotificationService.send_attendance_cancellation(attendance)