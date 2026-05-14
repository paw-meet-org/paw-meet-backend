from django.urls import path, include
from .router import router
from .views import ListTodosEncuentros

urlpatterns = [
    path('', include(router.urls)),
    path('admin/encuentros/list/', ListTodosEncuentros.as_view({'get': 'list'}), name='admin-encuentros-list')
]