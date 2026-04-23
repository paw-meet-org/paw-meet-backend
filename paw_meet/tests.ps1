# Ejecutar pruebas con cobertura
coverage run --source='encuentros' manage.py test encuentros
coverage report
coverage html  # Genera reporte HTML en htmlcov/