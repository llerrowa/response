#! /bin/bash
pip install -e ./

create_admin_user()
{
    cat << EOF | python3 manage.py shell
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
User = get_user_model()
try:
    User.objects.create_superuser('admin', '', 'admin')
except IntegrityError:
    pass
EOF
}

echo "[INFO] Migrating database"
cd /app/demo

python3 manage.py migrate --noinput

echo "[INFO] Creating Admin User"
create_admin_user

echo "[INFO] Starting Response Dev Server"
pip install debugpy -t /tmp && python3 /tmp/debugpy --wait-for-client --listen 0.0.0.0:5678 manage.py runserver 0.0.0.0:8000