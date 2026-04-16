from django.db import transaction
from .models import Encuentro, Asistencia

class EncuentroService:
    """
    Capa de servicio para la lógica de negocio asociada a los encuentros.
    Las views y serializers delegan aquí cualquier operación que vaya 
    más allá de simples CRUD.
    """

    @staticmethod
    @transaction.atomic
    def actualizar_estado_eliminado(
        
    ):
        pass