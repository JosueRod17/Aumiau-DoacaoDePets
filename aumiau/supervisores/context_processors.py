from pets.models import Pet

from .permissions import usuario_e_supervisor


def acesso_supervisor(request):
    tem_acesso = usuario_e_supervisor(request.user)
    contexto = {
        'tem_acesso_supervisor': tem_acesso,
        'pets_pendentes_menu': 0,
    }

    if tem_acesso and request.user.has_perm('pets.view_pet'):
        contexto['pets_pendentes_menu'] = Pet.objects.filter(
            status=Pet.Status.PENDENTE,
        ).count()

    return contexto
