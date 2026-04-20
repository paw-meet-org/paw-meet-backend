from rest_framework.routers import DefaultRouter
from .views import EncuentroViewSet

encuentros_router = DefaultRouter()
encuentros_router.register(r'encuentros', EncuentroViewSet, basename = 'encuentros')