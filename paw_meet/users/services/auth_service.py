from paw_meet.globals import APIException
from rest_framework_simplejwt.tokens import RefreshToken, Token
from django.contrib.auth import authenticate
from ..models import User
class RegistroService:

    @staticmethod
    def registrar_usuario(args: dict):
        try:
            if not args:
                raise APIException(
                    success = 'false',
                    code = '400',
                    message = 'No se han proporcionado datos suficientes para registrar un usuario',
                    error = 'Invalid Parameters'
                )
            
            # Compruebo primero que existe
            existe_user = User.objects.filter(
                username = args['nombre'],
                email = args['email']
            ).first()

            if existe_user:
                raise APIException(
                    success = 'false',
                    code = '409',
                    message = 'El uusario que se intenta registrar ya existe',
                    error = 'Already existing'
                )

            usuario = User.objects.create_user(
                username = args['nombre'],
                email = args['correo_electronico'],
                password = args['password'],
                biografia = args.get('biografia'),
                foto = args.get('foto')
            ) 
            
            return usuario
        
        except APIException:
            raise # La subo al nivel superior
        except Exception as e:
            print(f"Error inexperado al registrar un usuario : {e}")
            raise APIException(
                success = 'false',
                code = '500',
                message = 'Error interno del servidor',
                error = 'Internal Server Error'
            )
        
class LoginService:
    @staticmethod
    def login_usuario(args: dict):
        try:
            if not args:
                raise APIException(
                    success = 'false',
                    code = '400',
                    message = 'No se han proporcionado datos suficientes para registrar un usuario',
                    error = 'Invalid Parameters'
                )
            
            existe_user = User.objects.filter(
                username = args['nombre']
            ).first()

            if not existe_user:
                raise APIException(
                    success = 'false',
                    code = '404',
                    message = 'No se encuentran usuarios registrados con las credenciales indicadas',
                    error = 'Data Not Found'
                )
            
            usuario_autenticado = authenticate(username = args['nombre'], password = args['password'])
    
            if not usuario_autenticado:
                raise APIException(
                    success = 'false',
                    code = '401',
                    message = 'Error al validar la autentificación del usuario',
                    error = 'Invalid Token'
                )
            
            refresh_token = RefreshToken.for_user(usuario_autenticado)

            return (str(refresh_token), str(refresh_token.access_token))
        
        except APIException:
            raise
        except Exception as e:
            print(f"Error inesperado al lguear un usuario : {e}")
            raise APIException