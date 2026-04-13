from rest_framework.routers import DefaultRouter
from views import PetViewSet

router = DefaultRouter()
router.register(r'me/pets', PetViewSet, basename = 'pet')