import logging
import requests
from rest_framework.response import Response
from rest_framework import status
from .exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)

class ExternalServiceMixin:
    """
    Mixin para vistas que llaman a servicios externos (Supabase, etc.).
    Envuelve la llamada y convierte fallos de red en errores controlados.

    Uso:
        class MiVista(ExternalServiceMixin, generics.CreateAPIView):
            ...
            response = self.call_external(requests.post, url=url, headers=headers, json=payload)
    """

    def call_external(self, method: callable, **kwargs) -> requests.Response:
        try:
            response = method(**kwargs, verify=False)
            if response.status_code >= 400:
                logger.error(f"Error en servicio externo: {response.status_code} - {response.text}")
                raise ServiceUnavailableError(
                    detail=f"El servicio externo respondió con {response.status_code}."
                )
            return response
        except requests.exceptions.ConnectionError:
            raise ServiceUnavailableError(detail="No se pudo conectar con el servicio externo.")
        except requests.exceptions.Timeout:
            raise ServiceUnavailableError(detail="El servicio externo tardó demasiado en responder.")