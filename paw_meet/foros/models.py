from django.db import models
from django.conf import settings

# 1. CATEGORÍA (Debe ir primero porque Publicacion depende de ella)
class CategoriaPublicacion(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


# 2. FORO
class Foro(models.Model):
    # Relación 1:N con User (Un usuario puede crear varios foros)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='foros')
    tipo_foro = models.CharField(max_length=100)
    titulo = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.titulo} ({self.tipo_foro})"


# 3. PUBLICACIÓN
class Publicacion(models.Model):
    # Relaciones (Foreign Keys) según tu diagrama
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='publicaciones')
    foro = models.ForeignKey(Foro, on_delete=models.CASCADE, related_name='publicaciones')
    # Uso SET_NULL por si borráis una categoría, que no se borren todos los posts de golpe
    categoria = models.ForeignKey(CategoriaPublicacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='publicaciones')
    
    # Atributos propios
    titulo = models.CharField(max_length=200)
    texto = models.TextField()
    # Para el "blob" de la foto. upload_to crea la carpeta automáticamente
    foto = models.ImageField(upload_to='fotos_publicaciones/', null=True, blank=True)
    # timestamp de tu diagrama. auto_now_add=True guarda la fecha y hora exacta de creación
    uploaded_at = models.DateTimeField(auto_now_add=True)
    likes = models.IntegerField(default=0)

    def __str__(self):
        return self.titulo