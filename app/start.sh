#!/bin/bash

echo "CHECKING PLUGIN DEPENDENCIES..."
export PYTHONUSERBASE=/conf/plugin_modules
mkdir -p /conf/plugin_modules
cd /apps/corpora/plugins
find ./ -type f -name "requirements.txt" -exec pip3 install --user -r "{}" \;

if [ ! -f /apps/initialized ]; then
    echo "WAITING 60 SECONDS FOR DATABASES..."
    sleep 60
fi

cd /apps/corpora
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py collectstatic --no-input
python3 manage.py initialize_corpora
touch /apps/initialized

if [ "$CRP_DEVELOPMENT" = "yes" ]; then
    # DEVELOPMENT
    echo Starting Django Development Server
    exec python3 manage.py runserver 0.0.0.0:8000 &
else
    # PRODUCTION
    echo Starting Daphne
    export DJANGO_SETTINGS_MODULE=corpora.settings
    exec daphne corpora.asgi:application -b 0.0.0.0 -p 8000 -v 0 &
fi

# Start Huey
python3 manage.py run_huey -w ${CRP_HUEY_WORKERS}
