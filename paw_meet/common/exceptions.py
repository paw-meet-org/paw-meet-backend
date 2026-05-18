from rest_framework.exceptions import APIException
from rest_framework import status

class ServiceUnavailableError(APIException):
    """Para fallos de integraciones externas (Supabase, etc.)"""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = 'service_unavailable'
    default_detail = 'Un servicio externo no está disponible.'

class BusinessLogicError(APIException):
    """Para violaciones de reglas de negocio"""
    status_code = status.HTTP_409_CONFLICT
    default_code = 'business_logic_error'
    default_detail = 'Operación no permitida.'

class ResourceNotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = 'not_found'
    default_detail = 'El recurso solicitado no existe.'