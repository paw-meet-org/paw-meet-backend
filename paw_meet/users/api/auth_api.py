from rest_framework.views import APIView
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from ..serializers.auth_serializer import RegistroSerializer, LoginSerializer
from ..services.auth_service import LoginService, RegistroService
class RegistroAPIView(APIView):

    """
    POST /api/registro > Registra un nuevo usuario en el sistema
    """
    def post(self, request):
        # Obtengo los datos pasados en la peticion
        datos = request.data.dict()

        if not datos:
            payload = {
                'message' : 'Se debe proveer datos en el cuerpo de la peticion',
                'error' : 'Bad Request'
            }
            return Response(
                status = 400,
                data = payload
            )
        
        serializer = RegistroSerializer(data = datos)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status = status.HTTP_400_BAD_REQUEST
            )
        
        validate_data = serializer.validated_data
        

class LoginAPIView(APIView):

    pass