from django.urls import path, include
from .router import encuentros_router

urlpatterns = [
    path('', include(encuentros_router.urls))
]