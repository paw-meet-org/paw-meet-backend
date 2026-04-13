import uuid
from django.db import models

class BaseModel(models.Model):
    """
    Modelo abstracto base. Todos los modelos del proyecto heredan de aquí.
    Proporciona:
    - id UUID en lugar de autoincremental
    - timestamp de auditoría automáticos
    """
    id = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = True) # Evita exponer secuencias numéricas predecibles en la API
    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now = True)

    class Meta:
        abstract = True