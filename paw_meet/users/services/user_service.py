from django.db import transaction
from ..models import CustomUser


class UserService:
    """
    Capa de servicio para lógica de negocio relacionada con usuarios.
    Las views y serializers delegan aquí cualquier operación
    que vaya más allá de simple CRUD.
    """

    @staticmethod
    @transaction.atomic # Sirve para hacer commit en la base de datos
    def register_user(
        email: str,
        username: str,
        password: str,
        first_name: str = '',
        last_name: str = '',
    ) -> CustomUser:
        """
        Crea un nuevo usuario con contraseña hasheada.
        """
        user = CustomUser(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=CustomUser.Role.USER,
            is_active=True,
        )
        user.set_password(password)  # hashea con PBKDF2 por defecto
        user.save()
        return user

    @staticmethod
    @transaction.atomic
    def change_password(user: CustomUser, current_password: str, new_password: str) -> None:
        """
        Cambia la contraseña verificando primero la actual.
        Lanza ValueError si la contraseña actual no es correcta.
        """
        if not user.check_password(current_password):
            raise ValueError("La contraseña actual no es correcta.")
        user.set_password(new_password)
        user.save(update_fields=['password', 'updated_at'])

    @staticmethod
    def deactivate_user(user: CustomUser) -> None:
        """
        Soft-delete: desactiva el usuario en lugar de eliminarlo.
        Preserva historial de encuentros, etc.
        """
        user.is_active = False
        user.save(update_fields=['is_active', 'updated_at'])