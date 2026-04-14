from django.db import models
from common.models import BaseModel
from django.core.validators import MaxValueValidator

class Estado(models.TextChoices):
        BORRADOR = 'borrador', 'Borrador'
        CONFIRMADO = 'publicado', 'Publicado'
        ELIMINADO = 'eliminado', 'Eliminado'

class Asistencia(BaseModel):
    """
    Registro de asistencia por un usuario al encuentro.

    Relaciones: [Un encuentro puede tener varias asistencias, pero una 
    asistencia solo puede estar asociada a un encuentro (one-to-many).],
    [Una asistencia puede contener varios usuarios asociados, y un usuario puede 
    contar con varias asistencias (many-to-many)].
    """

    encuentro = models.ForeignKey(
        'encuentros.Encuentro',
        on_delete = models.SET_NULL,
        null = True,
        blank = True,
        related_name = 'asistencias_de_encuentro',
        help_text = "Asistencias registradas para el encuentro."
    )

    usuarios = models.ManyToManyField('users.CustomUser')

    contador_usuarios = models.IntegerField(
        blank = False,
        default = 0,
        validators = [MaxValueValidator(
            limit_value = 10,
            message = "Al registrar una asistencia, no se puede superar el límite de usuarios " \
            "establecido en el encuentro."
        )]
    )

    contador_mascotas = models.IntegerField(
        blank = False,
        default = 0
    )

    estado = models.CharField(
        max_length = 30,
        choices = Estado.choices,
        blank = True,
        default = '',
        help_text = "Estado actual del encuentro formalizado."
    )

    class Meta:
        verbose_name = 'asistencia'
        verbose_name_plural = 'asistencias'
        
    def __str__(self):
        return f"Mascotas: {self.contador_mascotas} - Usuarios: {self.contador_usuarios}"


class Encuentro(BaseModel):
    """
    Encuentros de PAW MEET.

    Hereda de BaseModel para mentener un registro de cuándo se ha creado y el identificador uuid.
    """

    creador = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='encuentros'
    )

    localizacion = models.CharField(
        max_length = 150,
        blank = False,
        default = '',
        help_text = "Ciudad o zona donde se realizará el encuentro."
    )

    tipo_mascota = models.ManyToManyField('users.PetType')

    limite_usuarios = models.IntegerField(
        blank = False,
        default = 2,
        validators = [MaxValueValidator(
            limit_value = 10, 
            message = "No se puede incluir un límite superior a 10"
        )],
        help_text = "Número máximo de usuarios que pueden asistir al encuentro."
    )

    duracion_minutos = models.IntegerField(
        blank = False,
        default = 15,
        validators = [MaxValueValidator(
            limit_value = 120,
            message = "No puede durar el encuentro más de 2 horas"
        )],
        help_text = "Número de minutos que va a durar el encuentro.º"
    )

    descripcion = models.CharField(
        max_length = 300,
        blank = True,
        default = '',
        help_text = "Descripción del encuentro formalizado."
    )

    titulo = models.CharField(
        max_length = 50,
        blank = False,
        default = 'Prueba Encuentro',
        help_text = "Título asociado al encuentro formalizado."
    )

    estado = models.CharField(
        max_length = 30,
        choices = Estado.choices,
        blank = True,
        default = '',
        help_text = "Estado actual del encuentro formalizado."
    )

    asistencia = models.ForeignKey(
        'encuentros.Asistencia',
        on_delete = models.SET_NULL,
        null = True,
        blank = True,
        related_name = 'asistencias_de_encuentro',
        help_text = "Asistencias registradas para el encuentro."
    )

    class Meta:
        verbose_name = 'encuentro'
        verbose_name_plural = 'encuentros'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.titulo} - {self.estado}"