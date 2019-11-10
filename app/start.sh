#!/bin/bash

if [ ! -f /apps/initialized ]; then
    pip3 install django-cors-headers
    echo "WAITING FOR DATABASES..."
    sleep 20
fi

cd /apps/corpora
#git pull
#python3 setup.py install
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py collectstatic --no-input
python3 manage.py initialize_corpora
touch /apps/initialized

# Start Gunicorn processes
echo Starting Gunicorn.
exec gunicorn corpora.wsgi:application\
    --bind 0.0.0.0:8000 \
    --workers ${CRP_DJANGO_WORKERS} &

# Start Huey
python3 manage.py run_huey -w ${CRP_HUEY_WORKERS}
