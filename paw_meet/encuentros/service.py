from django.db import transaction
from .models import Encuentro, Asistencia, Estado
from django.core.exceptions import PermissionDenied
from users.models import CustomUser
from django.core.mail import send_mail, send_mass_mail
from django.conf import settings
from django.contrib import messages
from .tasks import enviar_recordatorio
from django.utils import timezone

class EncuentroService:

    @staticmethod
    @transaction.atomic
    def crear_encuentro(datos: dict, creador) -> Encuentro:
        encuentro = Encuentro.objects.create(
            **datos,
            creador = creador,
            estado = Estado.BORRADOR
        )

        # Crear asistencia vinculada vacía
        asistencia = Asistencia.objects.create(
            encuentro = encuentro,
            estado = Estado.BORRADOR
        )

        encuentro.asistencia = asistencia
        encuentro.save()
        return encuentro

    @staticmethod
    @transaction.atomic
    def modificar_encuentro(datos: dict, encuentro: Encuentro, usuario) -> Encuentro:
        if encuentro.creador != usuario:
            raise PermissionDenied("Solo el creador puede actualizar el encuentro seleccionado.")
        
        for campo, valor in datos.items():
            setattr(encuentro, campo, valor)
        encuentro.save()
        return encuentro
    
    @staticmethod
    @transaction.atomic
    def eliminar_encuentro(encuentro: Encuentro, usuario):
        if encuentro.creador != usuario:
            raise PermissionDenied("Solo el creador puede eliminar el encuentro seleccionado.")
        
        if encuentro.estado in [Estado.FINALIZADO, Estado.ELIMINADO]:
            raise ValueError("No se puede eliminar un encuentro ya finalizado")
        
        encuentro.estado = Estado.ELIMINADO
        encuentro.save()

        # Lanzar la notificación a participantes

    @staticmethod
    @transaction.atomic
    def confirmar_asistencia(encuentro: Encuentro, usuario) -> Asistencia:
        if encuentro.estado != Estado.CONFIRMADO:
            raise ValueError("No se puede asistir a un encuentro que no esté finalizado.")
        
        asistencia: Asistencia = encuentro.asistencia

        if asistencia.contador_usuarios >= encuentro.limite_usuarios:
            raise ValueError("El encuentro ya cuenta con el límite de asistencia.")
        
        asistencia.usuarios.add(usuario)
        asistencia.contador_usuarios += 1
        asistencia.save()
        return asistencia
    
    @staticmethod
    @transaction.atomic
    def invitar_usuario(encuentro: Encuentro, usuarios_invitados : list, usuario_invitador):
        if encuentro.asistencia.contador_usuarios >= encuentro.limite_usuarios:
            raise ValueError("No se puede invitar a un encuentro lleno.")
        
        if usuarios_invitados >= encuentro.limite_usuarios:
            raise ValueError("El numero de usuarios a invitar excede el limite de usuarios permitido en el encuentro")
        
        try:
            for usuario in usuarios_invitados:
                if usuario in encuentro.asistencia.usuarios:
                    raise ValueError(f"El usuario {usuario} ya va a asistir a este encuentro")
            
            NotificationService.notificar_invitacion(
                encuentro = Encuentro,
                usuarios_invitado = usuarios_invitados,
                usuario_invitador = usuario_invitador
            )
        except Exception as e:
            print(f"Excepción al invitar un usuario : {e}")


class NotificationService:
    
    @staticmethod
    def notificar_cancelacion(encuentro: Encuentro):
        # 1. Obtengo todos los participantes asociados al encuentro
        participantes = encuentro.asistencia.usuarios.all()
        
        # 2. Obtengo la lista de correos asociados a los participantes.
        destinatarios = list(participantes.value_list('email', flat = True))

        if destinatarios:
            # 3. Configuro el envío de correos
            send_mail(
                subject = f"Cancelación: {encuentro.titulo}",
                message = f"El encuentro {encuentro.titulo} programado para {encuentro.fecha_realizacion} ha sido cancelado.",
                from_email = settings.EMAIL_HOST_USER,
                recipient_list = destinatarios,
                fail_silently = False,
            )

    @staticmethod
    def notificar_invitacion(encuentro: Encuentro, usuarios_invitado: list, usuario_invitador):
        # 1. Obtener los correos de los usuarios a invitar 
        destinatarios = list(CustomUser.objects.filter(username__in=usuarios_invitado).values_list('email', flat = True))

        if destinatarios:
            send_mail(
                subject = f"Invitación: {encuentro.titulo}",
                message = (f'{usuario_invitador.get_full_name()} te ha invitado al encuentro '
                           f'"{encuentro.titulo}" el {encuentro.fecha_realizacion}.'),
                from_email = settings.EMAIL_HOST_USER,
                recipient_list = destinatarios,
                fail_silently = False,
            )

        
        pass

    @staticmethod
    def notificar_recordatorio(encuentro: Encuentro) -> bool:
        try:
            # 1. Obtengo la fecha de realización del encuentro seleccionado
            fecha = encuentro.fecha_realizacion

            # 2. La comparo con la fecha actual del sistema
            diferencia = fecha - timezone.now()

            if (diferencia.days == 0) and (diferencia.total_seconds / 3600 <= 24):
                enviar_recordatorio.delay(encuentro)
                return True
            
            return False
        except Exception as e:
            raise