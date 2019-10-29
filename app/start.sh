#!/bin/bash

# temporary pip installs
pip3 install djangorestframework django-rest-framework-mongoengine pymysql djongo neo4j

# allow databases to come up
sleep 20

cd /apps/corpora
#git pull
#python3 setup.py install
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py collectstatic --no-input
python3 manage.py initialize_corpora

# Start Gunicorn processes
echo Starting Gunicorn.
exec gunicorn corpora.wsgi:application\
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --workers ${CRP_DJANGO_WORKERS} &

# Start Huey
python3 manage.py run_huey -w ${CRP_HUEY_WORKERS}
