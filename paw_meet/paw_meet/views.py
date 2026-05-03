from django.http import JsonResponse, HttpResponseForbidden
from os import environ
from encuentros.tasks import update_meeting_statuses_task, schedule_meeting_reminders_task

def trigger_scheduled_tasks(request):
    auth_header = request.headers.get('Authorization')
    expected_token = f'Bearer {environ.get('CRON_SECRET_KEY')}'

    if not auth_header or auth_header != expected_token:
        return HttpResponseForbidden("No autorizado")
    
    update_meeting_statuses_task.delay()
    schedule_meeting_reminders_task.delay()

    return JsonResponse({"status" : "tasks_enqueued"})