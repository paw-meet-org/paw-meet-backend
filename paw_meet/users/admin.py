from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Pet


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Añadimos los campos nuevos al panel de Django Admin
    fieldsets = UserAdmin.fieldsets + (
        ('PAW MEET', {'fields': ('role', 'bio', 'avatar', 'ciudad', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('PAW MEET', {'fields': ('email', 'role')}),
    )
    list_display = ['email', 'username', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['email', 'username', 'first_name', 'last_name']


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ['name', 'pet_type', 'owner', 'size', 'is_active']
    list_filter = ['pet_type', 'size', 'is_active']
    search_fields = ['name', 'owner__email']
    raw_id_fields = ['owner']