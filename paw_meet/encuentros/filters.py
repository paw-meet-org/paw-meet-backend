import django_filters
from .models import Encuentro
from users.models import PetType

class EncuentroFilter(django_filters.FilterSet):
    
    tipo_mascota = django_filters.ModelMultipleChoiceFilter(
        queryset = PetType.objects.all(),
        field_name = 'tipo_mascota',
        conjoined = False  # OR entre tipos — si pongo True sería AND (debe tener TODOS los tipos)
    )

    class Meta:
        model = Encuentro
        fields = {
            'localizacion' : ['icontains'],
            'fecha_realizacion' : ['lte', 'gte']
        }
