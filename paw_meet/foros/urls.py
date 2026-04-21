from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ForoViewSet,
    PublicacionViewSet,
    CategoriaPublicacionViewSet
)

# El router mapea automáticamente las acciones del ViewSet a URLs
router = DefaultRouter()
router.register(r'foros', ForoViewSet, basename='foro')
router.register(r'publicaciones', PublicacionViewSet, basename='publicacion')
router.register(r'categorias', CategoriaPublicacionViewSet, basename='categoria-publicacion')

urlpatterns = [
    path('', include(router.urls)),
]