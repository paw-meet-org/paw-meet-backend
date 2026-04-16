#!/bin/bash

echo "Creando las migraciones..."
python manage.py makemigrations users
python manage.py makemigrations social
python manage.py makemigrations encuentros
python manage.py makemigrations
python manage.py migrate

echo "Iniciando el servidor"
python manage.py runserver 0.0.0.0:8000