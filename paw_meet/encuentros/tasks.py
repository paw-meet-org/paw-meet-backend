import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from .models import Encuentro, Asistencia
from datetime import timedelta

logger = logging.getLogger(__name__)

def generic_estado_change(self, tipo : str):
    # 1. Obtengo todos los encuentros dado el tipo indicado por parámetros
    encuentros = Encuentro.objects.filter(estado = tipo.upper())

    # Si no existen los encuentros asociados al tipo, no se realiza la tarea
    if not encuentros.exists():
        return {'status' : 'NO_DATA', 'objetos_actualizados' : 0}
    
    # 2. Itero sobre los encuentros recopilados
    ahora = timezone.now()
    objetos_actualizados = 0

    for encuentro in encuentros:
        # 3. Obtengo la fecha del encuentro
        fecha = encuentro.fecha_realizacion

        # Dependiendo del tipo indicado por parámetros, obtengo y comparo con la duración del encuentro o no
        if tipo == 'finalizado':
            fin = fecha + timedelta(minutes = encuentro.duracion_minutos)

            # 4. Comprobar la fecha del encuentro con la actual
            if ahora >= fin:
                # 5. Si ya ha cumplido su tiempo actualizo el estado
                encuentro.estado = 'FINALIZADO'
                encuentro.save()
                objetos_actualizados += 1
                continue # Evito una compración más
        
        elif tipo == 'pendiente':
            if ahora >= fecha:
                # Ya ha concluido con su programación
                encuentro.estado = 'CONFIRMADO'
                encuentro.save()
                objetos_actualizados += 1

    return {
            'status' : 'SUCCESS',
            'objetos_actualizados' : objetos_actualizados
    }

@shared_task(name = 'encuentros.tasks.actualizar_estado_eliminado', bind = True, max_retires = 2)
@transaction.atomic
def actualizar_estado_eliminado_task(self):
    generic_estado_change(tipo = 'finalizado')
    
@shared_task(name = 'encuentros.tasks.registrar_encuentros_programados', bind = True, max_retries = 2)
def registrar_encuentros_programados_task(self):
    generic_estado_change(tipo = 'pendiente')