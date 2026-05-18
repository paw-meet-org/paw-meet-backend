import logging
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import (
    ValidationError, AuthenticationFailed,
    NotAuthenticated, PermissionDenied, NotFound
)
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404

logger = logging.getLogger(__name__)

def _error_response(status_code: int, code: str, message) -> Response:
    """Estructura de respuesta de error unificada para toda la API."""
    return Response(
        {
            "status"  : status_code,
            "code"    : code,
            "message" : message,
        },
        status=status_code
    )

def custom_exception_handler(exc, context):
    # 1. Dejamos que DRF procese lo que conoce
    response = drf_exception_handler(exc, context)

    view = context.get('view')
    logger.error(
        f"[{exc.__class__.__name__}] en {view.__class__.__name__}: {exc}",
        exc_info=True
    )

    # 2. Si DRF ya lo manejó, normalizamos su formato
    if response is not None:
        return _normalize_drf_response(exc, response)

    # 3. Excepciones de Django no manejadas por DRF
    if isinstance(exc, (Http404, ObjectDoesNotExist)):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            'not_found',
            'El recurso solicitado no existe.'
        )

    # 4. Cualquier excepción no controlada → 500
    logger.exception(f"Excepción no controlada en {view.__class__.__name__ if view else 'unknown'}")
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        'internal_server_error',
        'Ha ocurrido un error interno. Por favor, inténtalo más tarde.'
    )


def _normalize_drf_response(exc, response) -> Response:
    """
    Normaliza la respuesta de DRF al formato unificado.
    DRF devuelve estructuras variadas según el tipo de error;
    aquí las aplanamos todas.
    """
    data    = response.data
    code    = getattr(exc, 'default_code', 'error')
    message = data

    # ValidationError: {"field": ["error1", "error2"], ...}
    if isinstance(exc, ValidationError):
        return _error_response(
            response.status_code,
            'validation_error',
            data  # dejamos el dict completo para que el cliente sepa qué campo falló
        )

    # Errores con detail simple
    if isinstance(data, dict) and 'detail' in data:
        message = data['detail']

    return _error_response(response.status_code, code, message)