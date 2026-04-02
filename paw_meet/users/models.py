from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db import transaction

class Ciudad(models.Model):
    pass

class User(AbstractUser):

    username = models.CharField(_('Username'), max_length = 100, null = False, blank = False) # blank hace referencia al formulario, obligatoriedad de campo o no, null es DB
    password = models.CharField(_('Password'), max_length = 12, null = False, blank = False)
    email = models.EmailField(unique = True, null = False, blank = False)
    biography = models.CharField(_('Biography'), max_length = 300, null = True, blank = True)
    foto = models.FileField(upload_to = 'media/')

    ciudad = models.ForeignKey(Ciudad, on_delete = models.SET_NULL, null = True, blank = True, related_query_name = _("Ubicado en ciudad"))

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return f"{self.username} {self.email}" if self.email else self.username
