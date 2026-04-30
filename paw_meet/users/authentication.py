import jwt
import json
import logging
import requests
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from jwt.algorithms import ECAlgorithm
from django.conf import settings
from django.core.cache import cache
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import CustomUser
from drf_spectacular.extensions import OpenApiAuthenticationExtension

logger = logging.getLogger(__name__)

class SupabaseJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'users.authentication.SupabaseJWTAuthentication'
    name = 'SupabaseJWT'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': 'JWT emitido por Supabase. Header: Authorization: Bearer <token>',
        }


def get_supabase_public_key():
    """Obtiene el JWK de Supabase cacheando solo el JSON, no el objeto clave."""
    cached_jwk = cache.get('supabase_jwk_data')
    
    if not cached_jwk:
        url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        cached_jwk = response.json()['keys'][0]  # dict serializable
        cache.set('supabase_jwk_data', cached_jwk, timeout=3600)

    # Reconstruir el objeto clave (no se cachea, solo el dict)
    return ECAlgorithm.from_jwk(json.dumps(cached_jwk))


class SupabaseJWTAuthentication(BaseAuthentication):

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ', 1)[1]

        try:
            public_key = get_supabase_public_key()
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['ES256'],
                audience='authenticated',
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token expirado.')
        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed(f'Token inválido: {e}')
        except Exception as e:
            logger.error(f"Error al verificar token de Supabase: {e}")
            raise AuthenticationFailed('Error al verificar el token.')

        user = self._get_or_create_user(payload)
        return (user, payload)

    def _get_or_create_user(self, payload):
        supabase_uid = payload.get('sub')
        email = payload.get('email', '')

        if not supabase_uid:
            raise AuthenticationFailed('Token sin sub.')

        user, created = CustomUser.objects.get_or_create(
            supabase_uid=supabase_uid,
            defaults={
                'email': email,
                'username': email.split('@')[0],
            }
        )

        if not created and user.email != email:
            user.email = email
            user.save(update_fields=['email'])

        return user