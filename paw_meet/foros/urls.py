from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ForoViewSet,
    PublicacionViewSet,
    CategoriaPublicacionViewSet,
    ListTodasPublicaciones
)

router = DefaultRouter()
router.register(r'sociasl/foros', ForoViewSet, basename='foro')
router.register(r'social/publicaciones', PublicacionViewSet, basename='publicacion')
router.register(r'social/categorias', CategoriaPublicacionViewSet, basename='categoria-publicacion')

urlpatterns = [
    path('', include(router.urls)),
    path('admin/social/publicaciones/list/', ListTodasPublicaciones.as_view({'get':'list'}), name = 'admin-list-publicaciones')
]