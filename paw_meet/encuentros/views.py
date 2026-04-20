from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from .models import Encuentro
from .serializer import (
    EncuentroCreateSerializer, EncuentroUpdateSerializer,
    EncuentroListSerializer, InvitarSerializer
)
from .service import EncuentroService
from .filters import EncuentroFilter

class EncuentroViewSet(ModelViewSet):
    queryset = Encuentro.objects.exclude(estado = 'ELIMINADO')
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = EncuentroFilter
    ordering_fileds = ['fecha_realizacion', 'limite_usuarios']

    def get_serializer_class(self):
        if self.action == 'create':
            return EncuentroCreateSerializer
        if self.action in ['update', 'partial_update']:
            return EncuentroUpdateSerializer
        return EncuentroListSerializer
    
    def perform_create(self, serializer):
        EncuentroService.crear_encuentro(
            datos = serializer.validate_data,
            creador = self.request.user
        )

    def destroy(self, request, *args, **kwargs):
        EncuentroService.eliminar_encuentro(
            encuentro = self.get_object(),
            usuario = request.user
        )
        return Response(status = status.HTTP_204_NO_CONTENT)
    
    @action(detail = True, methods = ['post'], url_path = 'asistencia')
    def confirmar_asistencia(self, request, pk = None):
        EncuentroService.confirmar_asistencia(
            encuentro = self.get_object(),
            usuario = request.user
        )
        return Response({'detail' : 'Asistencia confirmada'})
    
    @action(detail = True, methods = ['post'], url_path = 'invitar')
    def invitar(self, request, pk = None):
        serializer = InvitarSerializer(data = request.data)
        serializer.is_valid(raise_exception = True)
        EncuentroService.invitar_usuario(
            encuentro = self.get_object(),
            usuarios_invitados = serializer.validated_data['usuario_id'],
            usuario_invitador = request.user
        )
        return Response({'detail' : 'Invitaciones enviadas.'})