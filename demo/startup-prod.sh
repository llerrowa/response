#! /bin/bash

pip install -e /response

wait_for_db()
{
    while ! nc -z ${DB_HOST:-db} ${DB_PORT:-5432};
    do sleep 1;
    done;
}

echo "[INFO] Collectstastic"
cd /app
python3 manage.py collectstatic --noinput

echo "[INFO] Waiting for DB"
wait_for_db

echo "[INFO] Migrating database"
cd /app
python3 manage.py migrate --noinput

exec "$@"