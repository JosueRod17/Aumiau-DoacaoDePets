from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from aumiau.data_settings import data_settings


class DadosEntreMaquinasTests(SimpleTestCase):
    def env(self, **changes):
        return {
            'AUMIAU_DATA_MODE': 'shared', 'DJANGO_SECRET_KEY': 'chave-de-teste',
            'DATABASE_URL': 'postgresql://user:p%40ss@db.example.com:5432/aumiau',
            'S3_BUCKET_NAME': 'aumiau-test', 'S3_ACCESS_KEY_ID': 'test-key',
            'S3_SECRET_ACCESS_KEY': 'test-secret',
        } | changes

    def test_modo_local_preserva_banco_existente(self):
        mode, databases, storages = data_settings(Path('/projeto'), {})
        self.assertEqual(mode, 'local')
        self.assertEqual(databases['default']['NAME'], Path('/projeto/db.sqlite3'))
        self.assertIn('FileSystemStorage', storages['default']['BACKEND'])

    def test_dois_pcs_usam_os_mesmos_dados_remotos(self):
        a = data_settings(Path('/pc-a'), self.env())
        b = data_settings(Path('/pc-b'), self.env())
        self.assertEqual(a, b)
        self.assertEqual(a[1]['default']['PASSWORD'], 'p@ss')
        self.assertEqual(a[1]['default']['OPTIONS']['sslmode'], 'require')
        self.assertTrue(a[2]['default']['OPTIONS']['querystring_auth'])
        self.assertFalse(a[2]['default']['OPTIONS']['file_overwrite'])

    def test_configuracao_incompleta_nao_cai_no_sqlite(self):
        for key in ('DATABASE_URL', 'DJANGO_SECRET_KEY', 'S3_BUCKET_NAME', 'S3_ACCESS_KEY_ID', 'S3_SECRET_ACCESS_KEY'):
            with self.subTest(key=key), self.assertRaisesMessage(ImproperlyConfigured, key):
                data_settings(Path('/projeto'), self.env(**{key: ''}))

    def test_nao_ignora_url_remota_em_modo_local(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'AUMIAU_DATA_MODE=shared'):
            data_settings(Path('/projeto'), self.env(AUMIAU_DATA_MODE='local'))

    def test_urls_invalidas_nao_revelam_senha(self):
        for url in ('mysql://usuario:segredo@host/db', 'postgresql://', 'segredo'):
            with self.assertRaises(ImproperlyConfigured) as error:
                data_settings(Path('/projeto'), self.env(DATABASE_URL=url))
            self.assertNotIn('segredo', str(error.exception))

    def test_endpoint_s3_customizado_exige_https(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'HTTPS'):
            data_settings(Path('/projeto'), self.env(S3_ENDPOINT_URL='http://storage.example.com'))
        _, _, storages = data_settings(Path('/projeto'), self.env(S3_ENDPOINT_URL='https://storage.example.com'))
        self.assertEqual(storages['default']['OPTIONS']['endpoint_url'], 'https://storage.example.com')
