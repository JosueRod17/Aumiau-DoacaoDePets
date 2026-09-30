#!/usr/bin/env bash
set -euo pipefail

python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
# O plano gratuito do Render não oferece comando de pré-deploy.
python manage.py migrate --noinput
