"""Configuração explícita para dados locais ou compartilhados entre PCs."""
import os
from urllib.parse import urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def data_settings(base_dir, environ=None):
    env = os.environ if environ is None else environ
    mode = env.get('AUMIAU_DATA_MODE', 'local').strip().lower()
    local_storage = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
    storages = {
        'default': local_storage,
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    if mode == 'local':
        if env.get('DATABASE_URL', '').strip():
            raise ImproperlyConfigured('DATABASE_URL foi definida. Use AUMIAU_DATA_MODE=shared para ativar os dados compartilhados.')
        return mode, {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': base_dir / 'db.sqlite3'}}, storages
    if mode != 'shared':
        raise ImproperlyConfigured('AUMIAU_DATA_MODE deve ser local ou shared.')
    required = ('DATABASE_URL', 'DJANGO_SECRET_KEY', 'S3_BUCKET_NAME', 'S3_ACCESS_KEY_ID', 'S3_SECRET_ACCESS_KEY')
    missing = [key for key in required if not env.get(key, '').strip()]
    if missing:
        raise ImproperlyConfigured('Modo compartilhado incompleto. Preencha no .env: ' + ', '.join(missing) + '. O banco local não será usado como alternativa.')
    database_url = env['DATABASE_URL'].strip()
    try:
        parts = urlsplit(database_url)
        if parts.scheme not in ('postgres', 'postgresql') or not parts.hostname or not parts.path.strip('/'):
            raise ValueError
        database = dj_database_url.parse(database_url, conn_max_age=60, conn_health_checks=True, ssl_require=True)
    except (ValueError, TypeError):
        # Não incluir a URL ou sua senha no erro.
        raise ImproperlyConfigured('DATABASE_URL deve ser uma URL PostgreSQL válida fornecida pela hospedagem.') from None
    database['DISABLE_SERVER_SIDE_CURSORS'] = True
    options = {
        'bucket_name': env['S3_BUCKET_NAME'].strip(),
        'access_key': env['S3_ACCESS_KEY_ID'].strip(),
        'secret_key': env['S3_SECRET_ACCESS_KEY'].strip(),
        'region_name': env.get('S3_REGION_NAME', 'us-east-1').strip() or 'us-east-1',
        'addressing_style': env.get('S3_ADDRESSING_STYLE', 'auto').strip() or 'auto',
        'default_acl': None,
        'querystring_auth': True,
        'file_overwrite': False,
    }
    endpoint = env.get('S3_ENDPOINT_URL', '').strip()
    if endpoint:
        endpoint_parts = urlsplit(endpoint)
        if endpoint_parts.scheme != 'https' or not endpoint_parts.hostname:
            raise ImproperlyConfigured('S3_ENDPOINT_URL deve usar HTTPS.')
        options['endpoint_url'] = endpoint
    if options['addressing_style'] not in ('auto', 'path', 'virtual'):
        raise ImproperlyConfigured('S3_ADDRESSING_STYLE deve ser auto, path ou virtual.')
    storages['default'] = {'BACKEND': 'storages.backends.s3.S3Storage', 'OPTIONS': options}
    return mode, {'default': database}, storages
