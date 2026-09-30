import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.apps import apps
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ongs.models import Ong
from supervisores.models import RegistroAtividade
from usuarios.models import ContaGoogle, Perfil

from .management.commands import importar_cadastros_locais as comando
from .models import FotoPet, Pet


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ImportarCadastrosLocaisTests(TestCase):
    def setUp(self):
        temporario = TemporaryDirectory(prefix='aumiau-test-importacao-')
        self.addCleanup(temporario.cleanup)
        self.base = Path(temporario.name)
        self.media = self.base / 'origem'
        self.destino = self.base / 'destino'
        (self.base / 'db.sqlite3').touch()
        configuracao = override_settings(
            AUMIAU_DATA_MODE='shared',
            BASE_DIR=self.base,
            MEDIA_ROOT=self.media,
            STORAGES={
                'default': {
                    'BACKEND': 'django.core.files.storage.FileSystemStorage',
                    'OPTIONS': {'location': self.destino},
                },
                'staticfiles': {
                    'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
                },
            },
        )
        configuracao.enable()
        self.addCleanup(configuracao.disable)

        self.nome_principal = 'pets/principais/' + 'p' * 72 + '.png'
        self.arquivos = {
            self.nome_principal: b'conteudo da foto principal',
            'pets/galeria/brincando.png': b'conteudo da foto da galeria',
        }
        for nome, conteudo in self.arquivos.items():
            caminho = self.media / nome
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_bytes(conteudo)

        # Construa uma origem com IDs diferentes das sequencias do destino.
        # Toda a origem existe somente no banco de testes e na pasta temporaria.
        Group.objects.all().delete()
        grupo = Group.objects.create(pk=97, name='Supervisores')
        self.permissao_origem = Permission.objects.get(
            content_type__app_label='auth', codename='view_user',
        )
        grupo.permissions.add(self.permissao_origem)
        usuario = get_user_model().objects.create_user(
            pk=41, username='pessoa-importada', password='senha-de-teste',
            email='importacao@example.com',
        )
        self.senha_serializada = usuario.password
        usuario.groups.add(grupo)
        self.permissao_usuario = Permission.objects.get(
            content_type__app_label='pets', codename='add_pet',
        )
        usuario.user_permissions.add(self.permissao_usuario)
        perfil = Perfil.objects.create(
            pk=52, usuario=usuario, telefone='11999990000', cidade='Campinas',
            estado='SP', aceitou_termos_em=timezone.now(), versao_termos='1.1',
        )
        google = ContaGoogle.objects.create(pk=53, usuario=usuario, subject='google-subject-teste')
        ong = Ong.objects.create(
            pk=61, nome='ONG importada', responsavel=usuario, cidade='Campinas',
            estado='SP', status=Ong.Status.APROVADA,
        )
        pet = Pet.objects.create(
            pk=71, nome='Amora', especie='gato', cidade='Campinas', estado='SP',
            ong=ong, responsavel=usuario, criado_por=usuario, moderado_por=usuario,
            foto_principal=self.nome_principal, status=Pet.Status.PUBLICADO,
        )
        foto = FotoPet.objects.create(
            pk=72, pet=pet, imagem='pets/galeria/brincando.png', legenda='Brincando',
        )
        atividade = RegistroAtividade.objects.create(
            pk=81, supervisor=usuario, acao=RegistroAtividade.Acao.ATIVOU,
            entidade='usuario', objeto_id=usuario.pk, descricao='Ativou a conta importada',
        )
        log = LogEntry.objects.create(
            pk=91, user=usuario, content_type=ContentType.objects.get_for_model(usuario),
            object_id=str(usuario.pk), object_repr=usuario.username, action_flag=ADDITION,
        )
        self.fixture = serializers.serialize(
            'json', [grupo, usuario, perfil, google, ong, pet, foto, atividade, log],
            use_natural_foreign_keys=True,
        )
        self.criado_em = parse_datetime(next(
            registro['fields']['criado_em'] for registro in json.loads(self.fixture)
            if registro['model'] == 'pets.pet'
        ))
        for rotulo in reversed(comando.MODELOS):
            apps.get_model(rotulo).objects.all().delete()

        # O migrate do site ja cria esse grupo; seu ID pode ser diferente.
        self.grupo_destino = Group.objects.create(pk=7, name='Supervisores')
        self.permissao_destino = Permission.objects.get(
            content_type__app_label='auth', codename='add_user',
        )
        self.grupo_destino.permissions.add(self.permissao_destino)

        origem = patch.object(
            comando, 'carregar_origem',
            side_effect=lambda: (self.fixture, json.loads(self.fixture)),
        )
        origem.start()
        self.addCleanup(origem.stop)

    def executar(self, aplicar=False):
        saida = StringIO()
        call_command('importar_cadastros_locais', aplicar=aplicar, stdout=saida)
        return saida.getvalue()

    def conferir_banco_vazio(self):
        for rotulo in comando.MODELOS:
            if rotulo != 'auth.Group':
                self.assertEqual(apps.get_model(rotulo).objects.count(), 0, rotulo)

    def arquivos_destino(self):
        return sorted(caminho for caminho in self.destino.rglob('*') if caminho.is_file())

    def test_conferencia_nao_grava_banco_nem_fotos(self):
        saida = self.executar()

        self.assertIn('Verificação concluída', saida)
        self.conferir_banco_vazio()
        self.assertEqual(self.arquivos_destino(), [])
        self.assertEqual(
            list(self.grupo_destino.permissions.all()), [self.permissao_destino],
        )

    def test_aplicar_preserva_ids_senhas_vinculos_historicos_e_fotos(self):
        saida = self.executar(aplicar=True)

        self.assertIn('Importação concluída', saida)
        usuario = get_user_model().objects.get(pk=41)
        self.assertEqual(usuario.password, self.senha_serializada)
        self.assertTrue(usuario.check_password('senha-de-teste'))
        self.assertEqual(list(usuario.groups.values_list('pk', flat=True)), [7])
        self.assertEqual(list(usuario.user_permissions.all()), [self.permissao_usuario])
        self.assertEqual(Group.objects.count(), 1)
        self.assertEqual(list(self.grupo_destino.permissions.all()), [self.permissao_origem])
        self.assertEqual(Perfil.objects.get(pk=52).usuario_id, 41)
        self.assertEqual(ContaGoogle.objects.get(pk=53).usuario_id, 41)
        self.assertEqual(Ong.objects.get(pk=61).responsavel_id, 41)
        pet = Pet.objects.get(pk=71)
        self.assertEqual((pet.responsavel_id, pet.criado_por_id, pet.moderado_por_id), (41, 41, 41))
        self.assertEqual(pet.ong_id, 61)
        self.assertEqual(pet.criado_em, self.criado_em)
        atividade = RegistroAtividade.objects.get(pk=81)
        self.assertEqual((atividade.supervisor_id, atividade.objeto_id), (41, 41))
        log = LogEntry.objects.get(pk=91)
        self.assertEqual((log.user_id, log.object_id), (41, '41'))
        self.assertEqual(log.content_type.get_object_for_this_type(pk=log.object_id), usuario)
        foto = FotoPet.objects.get(pk=72)
        self.assertEqual(foto.pet_id, 71)
        for campo, original in (
            (pet.foto_principal, self.nome_principal),
            (foto.imagem, 'pets/galeria/brincando.png'),
        ):
            self.assertRegex(campo.name, r'^migracoes/[0-9a-f]{32}/')
            self.assertTrue(campo.name.endswith(Path(original).suffix))
            self.assertLessEqual(len(campo.name), campo.field.max_length)
            with campo.open('rb') as arquivo:
                self.assertEqual(arquivo.read(), self.arquivos[original])
            self.assertEqual((self.media / original).read_bytes(), self.arquivos[original])
        self.assertEqual(len(self.arquivos_destino()), 2)

    def test_repeticao_recusada_preserva_importacao_existente(self):
        self.executar(aplicar=True)
        arquivos = {caminho: caminho.read_bytes() for caminho in self.arquivos_destino()}
        with self.assertRaisesMessage(CommandError, 'já contém cadastros'):
            self.executar(aplicar=True)

        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(Pet.objects.count(), 1)
        self.assertEqual(
            {caminho: caminho.read_bytes() for caminho in self.arquivos_destino()}, arquivos,
        )

    def test_falha_no_segundo_upload_reverte_banco_e_remove_arquivos(self):
        salvar = default_storage.save
        tentativas = []

        def salvar_e_falhar(nome, arquivo, **kwargs):
            resultado = salvar(nome, arquivo, **kwargs)
            tentativas.append(resultado)
            if len(tentativas) == 2:
                # Simula o servidor aceitar o arquivo antes da falha da conexao.
                raise OSError('falha de upload simulada')
            return resultado

        with patch.object(default_storage, 'save', side_effect=salvar_e_falhar):
            with self.assertRaisesMessage(CommandError, 'Importação cancelada (OSError)'):
                self.executar(aplicar=True)

        self.assertEqual(len(tentativas), 2)
        self.conferir_banco_vazio()
        self.assertEqual(self.arquivos_destino(), [])
        self.assertEqual(list(self.grupo_destino.permissions.all()), [self.permissao_destino])
        for nome, conteudo in self.arquivos.items():
            self.assertEqual((self.media / nome).read_bytes(), conteudo)
