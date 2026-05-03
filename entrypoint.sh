#!/bin/bash

# PARA TODO SI ALGUNA COSA FALLA POR EL CAMINO
set -e

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Aplicando migraciones a la base de datos..."
# Solo aplico las migraciones que ya subí a GitHub
python manage.py migrate

echo "Iniciando el Celery beat..."
python -m celery -A paw_meet beat --loglevel=info &

echo "Iniciando el Celery worker..."
python -m celery -A paw_meet worker --loglevel=info &

echo "Iniciando el servidor web (Gunicorn)..."
exec gunicorn paw_meet.wsgi:application --bind 0.0.0.0:${PORT:-8000}