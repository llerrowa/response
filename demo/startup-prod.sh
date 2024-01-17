#! /bin/bash

pip install -e ./

echo "[INFO] Collectstastic"
cd /app/demo
python3 manage.py collectstatic --noinput

echo "[INFO] Migrating database"
cd /app/demo
python3 manage.py migrate --noinput

#exec "$@"
python3 manage.py runserver 0.0.0.0:8000