#!/bin/bash

python manage.py makemigrations web
python manage.py migrate
echo yes | python manage.py collectstatic
gunicorn --timeout=300 --workers=4 config.wsgi -b 0.0.0.0