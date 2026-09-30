from pets.models import Pet
from adocoes.models import ChamadoAjuda, SolicitacaoAdocao

from .permissions import usuario_e_supervisor


def acesso_supervisor(request):
    tem_acesso = usuario_e_supervisor(request.user)
    contexto = {
        'tem_acesso_supervisor': tem_acesso,
        'pets_pendentes_menu': 0,
        'chamados_pendentes_menu': 0,
    }

    if tem_acesso and request.user.has_perm('pets.view_pet'):
        contexto['pets_pendentes_menu'] = Pet.objects.filter(
            status=Pet.Status.PENDENTE,
        ).count()

    if tem_acesso and request.user.has_perm('adocoes.view_chamadoajuda'):
        contexto['chamados_pendentes_menu'] = ChamadoAjuda.objects.filter(
            status__in=[ChamadoAjuda.Status.ABERTO, ChamadoAjuda.Status.EM_ANALISE],
        ).count()

    if tem_acesso and request.user.has_perm('supervisores.moderar_pet'):
        contexto['adocoes_pendentes_menu'] = SolicitacaoAdocao.objects.filter(status='pendente').count()
    return contexto
