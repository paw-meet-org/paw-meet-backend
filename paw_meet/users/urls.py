from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .router import root_router

from .views import (
    #RegisterView,
    #CustomTokenObtainPairView,
    MeView,
    ChangePasswordView,
    UserPublicProfileView,
    PetViewSet,
    CreateUsersByAdmin,
    ListUsersRegistered,
    AdminUserDeleteViewSet
)

router = DefaultRouter()
router.register(r'me/pets', PetViewSet, basename='pet')

urlpatterns = [
    # ── Auth ──────────────────────────────────
    #path('auth/register/',      RegisterView.as_view(),                name='auth-register'),
    #path('auth/login/',         CustomTokenObtainPairView.as_view(),   name='auth-login'),
    #path('auth/token/refresh/', TokenRefreshView.as_view(),            name='token-refresh'),
    #path('auth/token/verify/',  TokenVerifyView.as_view(),             name='token-verify'),

    # ── Perfil propio ─────────────────────────
    path('users/me/',                    MeView.as_view(),             name='user-me'),
    path('users/me/change-password/',    ChangePasswordView.as_view(), name='change-password'),

    # ── Perfil público ────────────────────────
    path('users/<uuid:id>/',             UserPublicProfileView.as_view(), name='user-public'),

    # ── Mascotas (router) ─────────────────────
    path('users/', include(router.urls)), # Genera: /users/me/pets/, /users/me/pets/<id>/, /users/me/pets/<id>/restore/

    # ── Tipo Mascotas (router) ─────────────────────
    path('', include(root_router.urls)),

    # ── Admin ──────────
    path('admin/create/', CreateUsersByAdmin.as_view(), name='admin-create'),
    path('admin/users/list/', ListUsersRegistered.as_view(), name='admin-list-users'),
    path('admin/users/delete/', AdminUserDeleteViewSet.as_view({'delete':'delete_by_email'}), name = 'admin-user-delete'),

]