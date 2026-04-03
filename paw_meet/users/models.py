from django.db import models
from django.contrib.auth.models import AbstractUser

class Ciudad(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class User(AbstractUser):
    email = models.EmailField(unique=True)
    biography = models.CharField(max_length=300, blank=True, null=True)
    foto = models.FileField(upload_to='users/', null=True, blank=True)

    ciudad = models.ForeignKey(
        Ciudad,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios"
    )

    def __str__(self):
        return self.username


class TipoMascota(models.Model):
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.nombre} - {self.codigo}"


class Mascota(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, blank=True, null=True)
    foto = models.FileField(upload_to='mascotas/', null=True, blank=True)

    tipo_mascota = models.ForeignKey(
        TipoMascota,
        on_delete=models.SET_NULL,
        null=True,
        related_name="mascotas"
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mascotas"
    )

    def __str__(self):
        return self.nombre