"""Instala exemplos locais sem substituir dados já editados."""

import json
from hashlib import sha256
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ongs.models import Ong
from pets.models import Pet


DEMO_DIR = Path(__file__).resolve().parents[2] / 'demo_data'

# Impressões das descrições distribuídas antes da revisão dos textos. Somente uma
# cópia ainda idêntica à original pode ser atualizada; alterações feitas no painel
# permanecem intactas quando o comando é executado novamente.
DESCRICOES_ANTERIORES = {
    'demo-ong-sp': {'descricao': 'a20c535863f2956dc344dc44fd4bb74f01057fdb800b31f3961cdbbc33ac82f1'},
    'demo-ong-rj': {'descricao': 'c22dab59443fffded845d400af136c05d39bd2a4378fcb3b9f7e338e4e895562'},
    'demo-ong-pr': {'descricao': '30a67a98fb5423728544a9d2e51065aa565bc2678ce63ff36cf44df3f1864c9d'},
    'demo-pet-01': {'descricao': '57bf34566242654c7aec7f710f251e184969d108f363261a319f182d1efb1fda'},
    'demo-pet-02': {'descricao': 'd274cf8aede4f94a5b07236c66ddf3df7e33077aab7d0019c70ac14104bfa55f'},
    'demo-pet-03': {
        'descricao': '52230cec31ed3927e23693554b7341533d444c1115a043f337875ad278faaaf5',
        'descricao_necessidades_especiais': '24b0bdfa432a8ba1d966b5836e8ea7fb61e23500043104277babadbb922e6864',
    },
    'demo-pet-04': {'descricao': '30e81b392e665505961ada4394d4fe7131c826393fe610fa3110704954122c94'},
    'demo-pet-05': {'descricao': 'de7ea711210bda64773ad3b39f9f387c2b66720a590f1695fb26fe3dff2724c8'},
    'demo-pet-06': {'descricao': 'bee394ae0c0a0b1376e69640b6b38f2a92224c0ad045ce807eb791e2a0b420d9'},
    'demo-pet-07': {'descricao': 'd836c06f74b29cab9a76e0d5a8774f350f7d9033959a1f52c512a9f0299eaa02'},
    'demo-pet-08': {'descricao': 'c68df0b7a90597474e594247932492fab57e2aa1b3bc69da81cd6298a833009e'},
    'demo-pet-09': {'descricao': '531a101ad304bd6207e2631260581f41328b6bf0ee4e06f3ab21acc0b81265ce'},
    'demo-pet-10': {'descricao': '2a861bea8e147ae29de15eb9775a75b69ab81e79d9eb482f4b94bcd7eb4cf57f'},
    'demo-pet-11': {'descricao': '786d3091b88c58820850ac59294d039d86deda47175cb4c34e3190af71ed77f5'},
    'demo-pet-12': {'descricao': '0d489de62c85298e0cc29c5a78114ea478afb0cc1ebc852936c0ffbe27f7da5e'},
}


def atualizar_descricoes_originais(objeto, item):
    alterados = []
    for campo, impressao in DESCRICOES_ANTERIORES.get(item['codigo'], {}).items():
        atual = getattr(objeto, campo)
        if atual != item[campo] and sha256(atual.encode('utf-8')).hexdigest() == impressao:
            setattr(objeto, campo, item[campo])
            alterados.append(campo)
    if alterados:
        objeto.save(update_fields=alterados)
    return bool(alterados)


class Command(BaseCommand):
    help = 'Cria 3 ONGs e 12 pets fictícios, com fotos, somente no ambiente local. Preserva edições anteriores.'
    requires_migrations_checks = True

    def handle(self, *args, **options):
        if getattr(settings, 'AUMIAU_DATA_MODE', None) != 'local':
            raise CommandError('Os exemplos só podem ser criados com AUMIAU_DATA_MODE=local.')
        try:
            dados = json.loads((DEMO_DIR / 'cadastros.json').read_text(encoding='utf-8'))
            for item in dados['ongs'] + dados['pets']:
                if not (DEMO_DIR / 'images' / item['foto']).is_file():
                    raise CommandError(f"Foto de demonstração não encontrada: {item['foto']}.")
        except (OSError, ValueError) as error:
            raise CommandError('Não foi possível ler os dados de demonstração incluídos no projeto.') from error

        agora = timezone.now()
        criados = {'ongs': 0, 'pets': 0, 'fotos': 0, 'textos': 0}
        arquivos_criados = []

        def preencher_foto(objeto, campo, nome):
            foto = getattr(objeto, campo)
            if foto:
                return
            with (DEMO_DIR / 'images' / nome).open('rb') as arquivo:
                foto.save(f"{objeto.codigo_demonstracao}.jpg", File(arquivo), save=False)
            arquivos_criados.append((foto.storage, foto.name))
            objeto.save(update_fields=[campo])
            criados['fotos'] += 1

        try:
            with transaction.atomic():
                ongs = {}
                for item in dados['ongs']:
                    defaults = {chave: valor for chave, valor in item.items() if chave not in {'codigo', 'foto'}}
                    defaults.update(status=Ong.Status.APROVADA, moderado_em=agora)
                    ong, nova = Ong.objects.get_or_create(codigo_demonstracao=item['codigo'], defaults=defaults)
                    ongs[item['codigo']] = ong
                    criados['ongs'] += int(nova)
                    if not nova:
                        criados['textos'] += int(atualizar_descricoes_originais(ong, item))
                    preencher_foto(ong, 'foto', item['foto'])

                for item in dados['pets']:
                    defaults = {chave: valor for chave, valor in item.items() if chave not in {'codigo', 'foto', 'ong'}}
                    ong = ongs[item['ong']]
                    defaults.update(ong=ong, cidade=ong.cidade, estado=ong.estado, idade_estimada_informada=True)
                    if item['status'] in {Pet.Status.PUBLICADO, Pet.Status.ADOTADO}:
                        defaults.update(moderado_em=agora - timedelta(days=30), publicado_em=agora - timedelta(days=30))
                    if item['status'] == Pet.Status.ADOTADO:
                        defaults['adotado_em'] = agora - timedelta(days=2)
                    pet, novo = Pet.objects.get_or_create(codigo_demonstracao=item['codigo'], defaults=defaults)
                    criados['pets'] += int(novo)
                    if not novo:
                        criados['textos'] += int(atualizar_descricoes_originais(pet, item))
                    preencher_foto(pet, 'foto_principal', item['foto'])
        except Exception as error:
            # Apenas nomes retornados pelo storage nesta execução são removidos.
            for storage, nome in arquivos_criados:
                try:
                    storage.delete(nome)
                except OSError:
                    self.stderr.write(f'Não foi possível remover a foto incompleta: {nome}')
            raise CommandError(f'Não foi possível criar os exemplos: {error}') from error

        self.stdout.write(self.style.SUCCESS(
            f"Demonstração pronta: {criados['ongs']} ONGs e {criados['pets']} pets criados; "
            f"{criados['fotos']} fotos preenchidas; {criados['textos']} textos originais atualizados. "
            f"Edições feitas nos cadastros e fotos existentes foram preservadas."
        ))
