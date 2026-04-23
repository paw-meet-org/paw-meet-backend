from rest_framework.routers import DefaultRouter
from .views import MeetingViewSet, AttendanceViewSet, CityViewSet

router = DefaultRouter()
router.register(r'cities', CityViewSet, basename='city')
router.register(r'attendances', AttendanceViewSet, basename='attendance')
router.register(r'', MeetingViewSet, basename='meeting')