from rest_framework.routers import DefaultRouter
from .views import PetViewSet, PetTypeViewSet

# Rutas asociadas al usuario
user_router = DefaultRouter()
user_router.register(r'me/pets', PetViewSet, basename = 'pet')

# Rutas asociadas a la raiz
root_router = DefaultRouter()
root_router.register(r'pettypes', PetTypeViewSet, basename = 'pettype')