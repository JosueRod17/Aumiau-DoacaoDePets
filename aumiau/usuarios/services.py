"""Operações de conta mantêm moderação, publicações e privacidade consistentes."""
import logging
import uuid

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import ContaGoogle, DocumentoBloqueado, Perfil

logger = logging.getLogger(__name__)


def _pets_do_usuario(usuario):
    Pet = apps.get_model('pets', 'Pet')
    return Pet.objects.filter(
        Q(ong__responsavel=usuario)
        | Q(ong__isnull=True, responsavel=usuario)
        | Q(ong__isnull=True, responsavel__isnull=True, criado_por=usuario)
    ).distinct()


def _arquivar_publicacoes(usuario):
    Pet = apps.get_model('pets', 'Pet')
    Ong = apps.get_model('ongs', 'Ong')
    _pets_do_usuario(usuario).exclude(status=Pet.Status.ADOTADO).update(status=Pet.Status.ARQUIVADO, destaque=False)
    Ong.objects.filter(responsavel=usuario).update(status=Ong.Status.SUSPENSA, aprovada=False)


@transaction.atomic
def alterar_situacao_usuario(usuario, situacao):
    if situacao not in {Perfil.Situacao.ATIVA, Perfil.Situacao.SUSPENSA, Perfil.Situacao.BANIDA}:
        raise ValueError('Situação inválida.')
    usuario = get_user_model().objects.select_for_update().get(pk=usuario.pk)
    perfil, _ = Perfil.objects.get_or_create(usuario=usuario, defaults={
        'telefone': '', 'cidade': '', 'estado': '',
        'aceitou_termos_em': timezone.now(), 'versao_termos': '',
    })
    if perfil.situacao == Perfil.Situacao.EXCLUIDA:
        raise ValueError('Uma conta excluída não pode ser reativada.')
    if situacao == Perfil.Situacao.BANIDA and perfil.cpf_hash:
        DocumentoBloqueado.objects.get_or_create(cpf_hash=perfil.cpf_hash)
    elif situacao == Perfil.Situacao.ATIVA and perfil.cpf_hash:
        DocumentoBloqueado.objects.filter(cpf_hash=perfil.cpf_hash).delete()
    perfil.situacao = situacao
    perfil.save(update_fields=['situacao', 'atualizado_em'])
    usuario.is_active = situacao == Perfil.Situacao.ATIVA
    usuario.save(update_fields=['is_active'])
    if not usuario.is_active:
        _arquivar_publicacoes(usuario)
    return usuario


def _apagar_arquivos(arquivos):
    for storage, nome in arquivos:
        try:
            storage.delete(nome)
        except Exception:
            # Falha externa não reativa uma conta já anonimizada.
            logger.exception('Falha ao remover um arquivo de uma conta excluída.')


@transaction.atomic
def excluir_conta(usuario):
    """Anonimiza a conta mantendo somente referências históricas sem identificação."""
    # A chave não muda; permite a verificação de FK de um envio de chat em
    # andamento enquanto a exclusão aguarda a trava da conversa.
    usuario = get_user_model().objects.select_for_update(no_key=True).get(pk=usuario.pk)
    perfil, _ = Perfil.objects.get_or_create(usuario=usuario, defaults={
        'telefone': '', 'cidade': '', 'estado': '',
        'aceitou_termos_em': timezone.now(), 'versao_termos': '',
    })
    if perfil and perfil.situacao == Perfil.Situacao.BANIDA and perfil.cpf_hash:
        DocumentoBloqueado.objects.get_or_create(cpf_hash=perfil.cpf_hash)
    Pet = apps.get_model('pets', 'Pet')
    FotoPet = apps.get_model('pets', 'FotoPet')
    Ong = apps.get_model('ongs', 'Ong')
    pets = _pets_do_usuario(usuario)
    ids_pets = list(pets.values_list('pk', flat=True))
    arquivos = []
    for pet in pets:
        if pet.foto_principal and not Pet.objects.exclude(pk__in=ids_pets).filter(foto_principal=pet.foto_principal.name).exists():
            arquivos.append((pet.foto_principal.storage, pet.foto_principal.name))
    fotos = FotoPet.objects.filter(pet_id__in=ids_pets)
    for foto in fotos:
        if foto.imagem and not FotoPet.objects.exclude(pet_id__in=ids_pets).filter(imagem=foto.imagem.name).exists():
            arquivos.append((foto.imagem.storage, foto.imagem.name))
    fotos.delete()
    for ong in Ong.objects.filter(responsavel=usuario):
        if ong.foto and not Ong.objects.exclude(responsavel=usuario).filter(foto=ong.foto.name).exists():
            arquivos.append((ong.foto.storage, ong.foto.name))
    Pet.objects.filter(pk__in=ids_pets).update(
        status=Pet.Status.ARQUIVADO, destaque=False, email_contato='', telefone_contato='',
        descricao='', descricao_necessidades_especiais='', foto_principal='', motivo_rejeicao='',
    )
    Ong.objects.filter(responsavel=usuario).update(
        status=Ong.Status.SUSPENSA, aprovada=False, email='', telefone='', descricao='', motivo_rejeicao='', foto='',
    )
    apps.get_model('adocoes', 'ChamadoAjuda').objects.filter(usuario=usuario).delete()
    Conversa = apps.get_model('adocoes', 'ConversaAdocao')
    # Espere envios em andamento antes de coletar as mensagens da cascata.
    # Assim nenhum envio novo aparece entre a coleta e a exclusão da conversa.
    conversas = list(Conversa.objects.filter(
        Q(anunciante=usuario) | Q(solicitacao__usuario=usuario),
    ).order_by('pk').select_for_update(of=('self',)).values_list('pk', flat=True))
    Conversa.objects.filter(pk__in=conversas).delete()
    apps.get_model('adocoes', 'SolicitacaoAdocao').objects.filter(usuario=usuario).delete()
    apps.get_model('supervisores', 'RegistroAtividade').objects.filter(
        entidade='usuario', objeto_id=usuario.pk,
    ).update(descricao='Atividade de conta posteriormente excluída.')
    if perfil:
        perfil.telefone = perfil.cidade = perfil.estado = perfil.cpf_final = perfil.versao_termos = ''
        perfil.cpf_hash = None
        perfil.situacao = Perfil.Situacao.EXCLUIDA
        perfil.save()
    ContaGoogle.objects.filter(usuario=usuario).delete()
    usuario.username = f'conta-excluida-{uuid.uuid4().hex}'
    usuario.email = usuario.first_name = usuario.last_name = ''
    usuario.is_active = usuario.is_staff = usuario.is_superuser = False
    usuario.set_unusable_password()
    usuario.save()
    usuario.groups.clear()
    usuario.user_permissions.clear()
    transaction.on_commit(lambda: _apagar_arquivos(arquivos))
