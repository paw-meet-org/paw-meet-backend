from django.contrib import admin

from .models import CategoriaPublicacion, Foro, Publicacion

admin.site.register(CategoriaPublicacion)
admin.site.register(Foro)
@admin.register(Publicacion)
class PublicacionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'usuario', 'foro', 'categoria', 'uploaded_at', 'likes')
    list_filter = ('foro', 'categoria', 'uploaded_at')
    search_fields = ('titulo', 'texto')