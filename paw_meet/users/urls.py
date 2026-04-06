from users.api.auth_api import RegistroAPIView, LoginAPIView
from users.api.user_api import UserAPIView
from users.api.mascota_api import MascotaAPIView
from django.urls import path

urlpatterns = [
    path('registro', RegistroAPIView.as_view(), name = 'user-registro'),
    path('login', LoginAPIView.as_view(), name = 'user-login'),
    path('user', UserAPIView.as_view(), name = 'user-update'),
    path('user/mascota', MascotaAPIView.as_view(), name = 'pet-register-get'),
]