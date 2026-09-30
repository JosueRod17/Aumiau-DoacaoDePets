"""Transfere os cadastros do SQLite local para um banco compartilhado vazio."""

import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from hashlib import file_digest
from io import StringIO
from pathlib import Path, PurePosixPath
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction


# Permissões e content types são criados pelas migrações do destino. Sessões não
# são transferidas: a chave secreta do site publicado é diferente da chave local.
MODELOS = (
    'auth.Group',
    'auth.User',
    'usuarios.Perfil',
    'usuarios.DocumentoBloqueado',
    'usuarios.ContaGoogle',
    'ongs.Ong',
    'pets.Pet',
    'pets.FotoPet',
    'adocoes.ChamadoAjuda',
    'adocoes.SolicitacaoAdocao',
    'supervisores.RegistroAtividade',
    'admin.LogEntry',
)
FOTOS = {
    'ongs.ong': 'foto',
    'pets.pet': 'foto_principal',
    'pets.fotopet': 'imagem',
}


def carregar_origem():
    """Serializa a instalação local num processo isolado dos segredos da Neon."""
    ambiente = os.environ.copy()
    ambiente['AUMIAU_DATA_MODE'] = 'local'
    ambiente['DJANGO_DEBUG'] = 'true'
    ambiente['DJANGO_SETTINGS_MODULE'] = 'aumiau.settings'
    # O valor vazio impede que python-dotenv recoloque DATABASE_URL do .env.
    ambiente['DATABASE_URL'] = ''
    ambiente['PYTHONIOENCODING'] = 'utf-8'
    comando = [
        sys.executable,
        str(settings.BASE_DIR / 'manage.py'),
        'dumpdata',
        *MODELOS,
        '--natural-foreign',
    ]
    resultado = subprocess.run(
        comando, env=ambiente, capture_output=True, text=True, encoding='utf-8',
        check=False,
    )
    if resultado.returncode:
        raise CommandError(
            'Não foi possível ler o SQLite local. Pare o runserver local e '
            'confira se as migrações deste checkout foram aplicadas nele.'
        )
    try:
        return resultado.stdout, json.loads(resultado.stdout)
    except (json.JSONDecodeError, TypeError):
        raise CommandError('A exportação local não produziu dados JSON válidos.') from None


def fotos_referenciadas(registros, pasta_media):
    """Recusa caminhos fora de media/ e fotos ausentes antes de tocar no destino."""
    caminhos = set()
    pasta_media = pasta_media.resolve()
    for registro in registros:
        nome = registro['fields'].get(FOTOS.get(registro['model'], ''))
        if not nome:
            continue
        caminho_relativo = PurePosixPath(nome)
        if caminho_relativo.is_absolute() or '..' in caminho_relativo.parts or '\\' in nome:
            raise CommandError('O SQLite contém um caminho de foto inválido.')
        arquivo = pasta_media.joinpath(*caminho_relativo.parts).resolve()
        if not arquivo.is_relative_to(pasta_media) or not arquivo.is_file():
            raise CommandError(f'Foto referenciada pelo SQLite não encontrada: {nome}')
        caminhos.add(nome)
    return sorted(caminhos)


def conferir_destino_vazio():
    ocupados = {
        rotulo: total
        for rotulo in MODELOS if rotulo != 'auth.Group'
        if (total := apps.get_model(rotulo).objects.using('default').count())
    }
    if ocupados:
        raise CommandError(
            'O banco publicado já contém cadastros. Importação interrompida para '
            'não sobrescrever nem duplicar registros. Contagens: '
            + ', '.join(f'{rotulo}={total}' for rotulo, total in ocupados.items())
        )


def bloquear_gravacoes_durante_importacao():
    # Permite leituras do site, mas impede novos cadastros entre a conferência
    # de banco vazio e o carregamento dos IDs originais. Executar em atomic().
    if connection.vendor != 'postgresql':
        return
    tabelas = set()
    for rotulo in MODELOS:
        modelo = apps.get_model(rotulo)
        tabelas.add(modelo._meta.db_table)
        tabelas.update(
            campo.remote_field.through._meta.db_table
            for campo in modelo._meta.local_many_to_many
        )
    nomes = ', '.join(connection.ops.quote_name(nome) for nome in sorted(tabelas))
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = '10s'")
        cursor.execute(f'LOCK TABLE {nomes} IN SHARE ROW EXCLUSIVE MODE')


class Command(BaseCommand):
    help = 'Confere e importa o SQLite/media locais para um banco compartilhado vazio e fotos remotas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Efetua a importação depois das verificações. Sem esta opção, apenas confere.',
        )

    def handle(self, *args, **options):
        if settings.AUMIAU_DATA_MODE != 'shared':
            raise CommandError('Configure .env com AUMIAU_DATA_MODE=shared antes de importar.')

        origem = settings.BASE_DIR / 'db.sqlite3'
        if not origem.is_file():
            raise CommandError('Não encontrei o SQLite local em aumiau/db.sqlite3.')

        _, registros = carregar_origem()
        contagens = Counter(registro['model'] for registro in registros)
        if not contagens['auth.user'] and not contagens['pets.pet'] and not contagens['ongs.ong']:
            raise CommandError('O SQLite local não contém usuários, pets nem ONGs para importar.')

        fotos = fotos_referenciadas(registros, Path(settings.MEDIA_ROOT))
        try:
            conferir_destino_vazio()
        except DatabaseError:
            raise CommandError(
                'Não consegui consultar o banco publicado. Confira DATABASE_URL e a conexão com a Neon.'
            ) from None
        if any(
            item['fields'].get('cpf_hash') for item in registros
            if item['model'] in ('usuarios.perfil', 'usuarios.documentobloqueado')
        ):
            raise CommandError(
                'A origem contém identificadores de CPF. É necessário conferir a chave '
                'DOCUMENT_HASH_KEY usada na origem antes de migrar esses registros.'
            )

        prefixo = f'migracoes/{uuid4().hex}'
        # ImageField limita o caminho a 100 caracteres. Preserve a extensão e
        # use um nome curto, mesmo que o nome original ocupe quase esse limite.
        destinos = {
            nome: f'{prefixo}/{indice:04d}{PurePosixPath(nome).suffix}'
            for indice, nome in enumerate(fotos, start=1)
        }
        for item in registros:
            campo = FOTOS.get(item['model'])
            nome = item['fields'].get(campo) if campo else None
            if nome:
                limite = apps.get_model(item['model'])._meta.get_field(campo).max_length
                if limite and len(destinos[nome]) > limite:
                    raise CommandError('A extensão de uma foto excede o limite do caminho no banco.')
        try:
            conflitos = [nome for nome in destinos.values() if default_storage.exists(nome)]
        except Exception:
            raise CommandError(
                'Não consegui consultar o bucket. Confira endpoint, região e credenciais S3.'
            ) from None
        if conflitos:
            raise CommandError(
                'O bucket já contém arquivos com os caminhos reservados para esta importação. '
                'Importação interrompida para preservar as fotos existentes.'
            )

        resumo = (
            f"{contagens['auth.user']} usuários, {contagens['ongs.ong']} ONGs, "
            f"{contagens['pets.pet']} pets e {len(fotos)} fotos referenciadas"
        )
        if not options['aplicar']:
            self.stdout.write(self.style.SUCCESS(
                f'Verificação concluída: {resumo}. Destino vazio. '
                'Execute novamente com --aplicar para transferir.'
            ))
            return

        for item in registros:
            if item['model'] == 'auth.group':
                # Supervisores já é criado por migrate; encontre o grupo pelo nome.
                # Todos os outros IDs permanecem iguais, incluindo os dos usuários.
                item.pop('pk', None)
            campo = FOTOS.get(item['model'])
            if campo and item['fields'].get(campo):
                item['fields'][campo] = destinos[item['fields'][campo]]

        # loaddata precisa de um arquivo; ele permanece no diretório temporário
        # apenas durante esta execução e nunca deve entrar no Git.
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', suffix='.json', delete=False
        ) as temporario:
            json.dump(registros, temporario, ensure_ascii=False)
            caminho_fixture = Path(temporario.name)

        enviados = set()
        try:
            with transaction.atomic():
                bloquear_gravacoes_durante_importacao()
                conferir_destino_vazio()
                call_command('loaddata', str(caminho_fixture), verbosity=0, stdout=StringIO())
                for nome in fotos:
                    origem_foto = Path(settings.MEDIA_ROOT).joinpath(*PurePosixPath(nome).parts)
                    destino = destinos[nome]
                    # Inclua tentativas: uma falha de rede pode ocorrer depois de o
                    # servidor aceitar o arquivo. O prefixo é exclusivo desta execução.
                    enviados.add(destino)
                    with origem_foto.open('rb') as arquivo:
                        nome_enviado = default_storage.save(destino, File(arquivo))
                    enviados.add(nome_enviado)
                    if nome_enviado != destino:
                        raise CommandError(
                            'O bucket alterou o caminho de uma foto; importação cancelada.'
                        )
                    with origem_foto.open('rb') as arquivo, default_storage.open(destino, 'rb') as remoto:
                        if file_digest(arquivo, 'sha256').digest() != file_digest(remoto, 'sha256').digest():
                            raise CommandError('A leitura da foto enviada não corresponde ao arquivo local.')
                for rotulo in MODELOS:
                    if rotulo != 'auth.Group':
                        total = apps.get_model(rotulo).objects.count()
                        if total != contagens[rotulo.lower()]:
                            raise CommandError(f'A contagem de {rotulo} divergiu; importação cancelada.')
        except BaseException as erro:
            for nome in enviados:
                try:
                    default_storage.delete(nome)
                except Exception:
                    self.stderr.write(f'Confira arquivos remanescentes no bucket sob {prefixo}/.')
            if isinstance(erro, CommandError) or not isinstance(erro, Exception):
                raise
            raise CommandError(
                f'Importação cancelada ({type(erro).__name__}). Confira a conexão '
                'e o bucket; execute a conferência novamente antes de repetir.'
            ) from None
        finally:
            caminho_fixture.unlink(missing_ok=True)

        self.stdout.write(self.style.SUCCESS(f'Importação concluída: {resumo}.'))
