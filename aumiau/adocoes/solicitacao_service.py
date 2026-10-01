from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from pets.models import Pet
from supervisores.models import RegistroAtividade
from supervisores.permissions import usuario_e_supervisor
from supervisores.services import registrar_atividade
from usuarios.models import Perfil

from .models import SolicitacaoAdocao
from .contato_adocao import mensagem_aprovacao


def decidir_solicitacao(*, solicitacao_id, ator, aprovar, resposta=''):
    """Decide uma solicitação pendente e registra a adoção na mesma transação."""
    if not usuario_e_supervisor(ator) or not ator.has_perm('supervisores.moderar_pet'):
        raise PermissionDenied('Sua conta não possui permissão para analisar adoções.')

    resposta = resposta.strip()
    if len(resposta) > 5000:
        raise ValidationError('A resposta deve ter no máximo 5000 caracteres.')
    if not aprovar and not resposta:
        raise ValidationError('Informe o motivo da recusa da solicitação.')

    with transaction.atomic():
        # Toda decisão bloqueia primeiro o pet. Duas aprovações para o mesmo
        # anúncio ficam em sequência mesmo quando atendem solicitações distintas.
        pet_id = SolicitacaoAdocao.objects.values_list('pet_id', flat=True).get(pk=solicitacao_id)
        pet = Pet.objects.select_for_update().get(pk=pet_id)
        solicitacao = SolicitacaoAdocao.objects.select_for_update().get(pk=solicitacao_id, pet=pet)
        if solicitacao.status != SolicitacaoAdocao.Status.PENDENTE:
            raise ValidationError('Esta solicitação já foi analisada ou cancelada.')

        if aprovar:
            if not Pet.objects.publicos().filter(pk=pet.pk).exists():
                raise ValidationError('O pet precisa estar publicado e disponível para adoção.')
            usuario = solicitacao.usuario
            if not usuario.is_active or Perfil.objects.filter(usuario=usuario).exclude(
                situacao=Perfil.Situacao.ATIVA,
            ).exists():
                raise ValidationError('A conta do solicitante precisa estar ativa para aprovar a adoção.')
            if Pet.objects.gerenciaveis_por(usuario).filter(pk=pet.pk).exists():
                raise ValidationError('O responsável pelo anúncio não pode adotar o próprio pet.')

        agora = timezone.now()
        solicitacao.status = (
            SolicitacaoAdocao.Status.APROVADA if aprovar else SolicitacaoAdocao.Status.RECUSADA
        )
        solicitacao.resposta = resposta or (mensagem_aprovacao(pet) if aprovar else '')
        solicitacao.analisado_por = ator
        solicitacao.analisado_em = agora
        campos_decisao = ['status', 'resposta', 'analisado_por', 'analisado_em', 'atualizado_em']
        solicitacao.save(update_fields=campos_decisao)
        acao = RegistroAtividade.Acao.APROVOU if aprovar else RegistroAtividade.Acao.REJEITOU
        verbo = 'Aprovou' if aprovar else 'Recusou'
        registrar_atividade(
            ator, acao, 'solicitacao_adocao', solicitacao,
            f'{verbo} a solicitação de adoção #{solicitacao.pk} de {pet.nome}.',
        )

        if aprovar:
            pet.status = Pet.Status.ADOTADO
            pet.adotado_em = agora
            pet.moderado_por = ator
            pet.moderado_em = agora
            pet.destaque = False
            pet.motivo_rejeicao = ''
            pet.save(update_fields=[
                'status', 'adotado_em', 'moderado_por', 'moderado_em',
                'destaque', 'motivo_rejeicao', 'atualizado_em',
            ])
            registrar_atividade(
                ator, RegistroAtividade.Acao.ADOTOU, 'pet', pet,
                f'Adoção de {pet.nome} aprovada pela solicitação #{solicitacao.pk}.',
            )
            outras = SolicitacaoAdocao.objects.select_for_update().filter(
                pet=pet, status=SolicitacaoAdocao.Status.PENDENTE,
            ).order_by('pk')
            for outra in outras:
                outra.status = SolicitacaoAdocao.Status.RECUSADA
                outra.resposta = 'Outra solicitação foi aprovada e este pet já foi adotado.'
                outra.analisado_por = ator
                outra.analisado_em = agora
                outra.save(update_fields=campos_decisao)
                registrar_atividade(
                    ator, RegistroAtividade.Acao.REJEITOU, 'solicitacao_adocao', outra,
                    f'Solicitação #{outra.pk} recusada após a aprovação de outra adoção de {pet.nome}.',
                )

        # Devolve o pet atualizado também ao acessar solicitacao.pet.
        solicitacao.pet = pet
        return solicitacao
