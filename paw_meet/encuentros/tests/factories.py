import factory
from django.utils import timezone
from datetime import timedelta, time
from django.contrib.auth import get_user_model
from encuentros.models import Meeting, Attendance, City, MeetingStatus
from users.models import Pet, PetType

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory para crear usuarios de prueba."""
    
    class Meta:
        model = User
    
    email = factory.Sequence(lambda n: f'user{n}@test.com')
    username = factory.Sequence(lambda n: f'user{n}')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    
    @factory.post_generation
    def set_password(obj, create, extracted, **kwargs):
        obj.set_password('testpass123')
        obj.save()


class PetTypeFactory(factory.django.DjangoModelFactory):
    """Factory para tipos de mascota."""
    
    class Meta:
        model = PetType
    
    nombre = factory.Iterator(['PetType1', 'PetType2', 'PetType3', 'PetType4'])
    codigo = factory.Iterator(['PERROS', 'GATOS', 'HAMSTER', 'PAJAROS'])


class PetFactory(factory.django.DjangoModelFactory):
    """Factory para mascotas."""
    
    class Meta:
        model = Pet
    
    owner = factory.SubFactory(UserFactory)
    pet_type = factory.SubFactory(PetTypeFactory)
    name = factory.Faker('first_name')
    

class CityFactory(factory.django.DjangoModelFactory):
    """Factory para ciudades."""
    
    class Meta:
        model = City
    
    name = factory.Iterator(['Madrid', 'Barcelona', 'Valencia', 'Sevilla', 'Bilbao'])
    province = factory.Iterator(['Madrid', 'Barcelona', 'Valencia', 'Sevilla', 'Vizcaya'])


class MeetingFactory(factory.django.DjangoModelFactory):
    """Factory para encuentros."""
    
    class Meta:
        model = Meeting
    
    creator = factory.SubFactory(UserFactory)
    city = factory.SubFactory(CityFactory)
    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('paragraph')
    location = factory.Faker('address')
    date = factory.LazyFunction(lambda: timezone.now().date() + timedelta(days=7))
    start_time = time(17, 0)  # 17:00
    end_time = time(19, 0)    # 19:00
    max_participants = 10
    status = MeetingStatus.SCHEDULED
    
    @factory.post_generation
    def pets(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for pet in extracted:
                obj.pets.add(pet)
        else:
            # Añadir una mascota del creador por defecto
            pet = PetFactory(owner=obj.creator)
            obj.pets.add(pet)


class AttendanceFactory(factory.django.DjangoModelFactory):
    """Factory para asistencias."""
    
    class Meta:
        model = Attendance
    
    meeting = factory.SubFactory(MeetingFactory)
    user = factory.SubFactory(UserFactory)
    status = Attendance.AttendanceStatus.CONFIRMED
    notes = factory.Faker('sentence', nb_words=6)
    
    @factory.post_generation
    def pets(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for pet in extracted:
                obj.pets.add(pet)