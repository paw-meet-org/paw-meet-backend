from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, ProhibitNullCharactersValidator

from common.models import BaseModel
from .managers import CustomUserManager

class CustomUser(AbstractUser, BaseModel):
    """
    Usuario principal de PAW MEET.

    Hereda de AbstractUser para mantener los campos de autentificación de Django (password, hashing, permisos, sesiones) 
    y se extiende con campos específicos de la aplicación.

    NOTA: AbstractUser ya tiene: username, email, first_name, last_name,
    is_active, is_staff, date_joined, last_login.
    No redefinimos lo que ya existe.
    """
    class Role(models.TextChoices):
        USER = 'user', 'Usuario'
        ADMIN = 'admin', 'Administrador'

    email = models.EmailField(unique = True)

    role = models.CharField(
        max_length = 10,
        choices = Role.choices,
        default = Role.USER
    )

    bio = models.TextField(
        blank = True,
        default = '',
        validators = [MinLengthValidator(0)],
        help_text="Descripción personal del usuario. Máx. 500 caracteres recomendados."
    )

    avatar = models.ImageField(
        upload_to = 'media/users/%Y/%m',
        null = True,
        blank = True,
        help_text = "Foto de perfil del usuario."
    )

    ciudad = models.CharField(
        max_length=150,
        blank=True,
        default='',
        help_text="Ciudad o zona del usuario para filtros de encuentros."
    )

    phone = models.CharField(
        max_length = 20,
        blank = True,
        default = '',
        help_text = "Teléfono de contacto opcional"
    )

    # Hacemos login por email en vez de por username.
    USERNAME_FIELD = 'email'

    # AbstractUser necesita el campo username pero no es necesario para el login.
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
    
    @property
    def is_app_admin(self) -> bool:
        """
        Propiedad helper para chequeos de permisos en la app.
        Distinto de is_staff.
        """
        return self.role == self.Role.ADMIN
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.username


class PetType(BaseModel):
    """
    Tipo de mascota asociada a una mascota.

    Relación: Un tipo de mascota puede estar asociada a MUCHAS mascotas (one-to-many).
    Una mascota pertenece a un único tipo de mascota registrado.
    """

    nombre = models.CharField(
        max_length = 100,
        blank = False,
        default = ''
    )

    codigo = models.CharField(
        max_length = 8,
        blank = False,
        default = '',
        validators = [ProhibitNullCharactersValidator]
    )

    class Meta:
        verbose_name = 'pet_type'
        verbose_name_plural = 'pets_type'
        ordering = ['-codigo']
        constraints = [
            models.UniqueConstraint(
                fields = ['nombre', 'codigo'],
                name = 'unique_pet_types'
            )
        ]

    def __str__(self):
        return f"{self.nombre} - {self.codigo}"

class Pet(BaseModel):
    """
    Mascota asociada a un usuario.

    Relación: Un usuario puede tener MUCHAS mascotas (one-to-many).
    Una mascota pertenece a UN único usuario registrado.
    """

    class Size(models.TextChoices):
        SMALL = 'small', 'Pequeño (< 10kg)'
        MEDIUM = 'medium', 'Mediano (10-25kg)'
        LARGE = 'large', 'Grande (> 25kg)'

    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='pets',
        help_text="Dueño registrado de la mascota."
    )

    name = models.CharField(max_length=100)

    pet_type = models.ForeignKey(
        'users.PetType',
        on_delete = models.CASCADE,
        related_name = 'pets_type', # A la hora de consultar a la base de datos la asociación de ambos, en vez de usar mascota.pet_type_set (default) usas mascota.pets_type
        help_text = "Tipo de mascota registrada."
    )

    # Sólo relevante si pet_type == OTHER. Permite especificar especie libre.
    species = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Especie libre (rellenar solo si tipo es 'Otro')."
    )

    breed = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Raza de la mascota."
    )

    size = models.CharField(
        max_length=10,
        choices=Size.choices,
        blank=True,
        default='',
        help_text="Tamaño aproximado. Especialmente relevante para perros."
    )

    birth_date = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha de nacimiento. Permite calcular edad en la API."
    )

    bio = models.TextField(
        blank=True,
        default='',
        help_text="Descripción de la mascota: carácter, gustos, etc."
    )

    avatar = models.ImageField(
        upload_to='media/mascotas/%Y/%m/',
        null=True,
        blank=True,
        help_text="Foto de la mascota."
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Permite 'archivar' mascotas sin eliminarlas (fallecidas, etc.)."
    )

    class Meta:
        verbose_name = 'Mascota'
        verbose_name_plural = 'Mascotas'
        ordering = ['name']
        # Un usuario no puede tener dos mascotas con el mismo nombre
        # (restricción razonable, evita duplicados por error).
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'name'],
                name='unique_pet_name_per_owner'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.pet_type}) — {self.owner.email}"

    @property
    def age_years(self) -> int | None:
        """Calcula la edad en años si birth_date está definida."""
        if not self.birth_date:
            return None
        from datetime import date
        today = date.today()
        return (today - self.birth_date).days // 365