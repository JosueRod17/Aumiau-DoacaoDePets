from .permissions import usuario_e_supervisor


def acesso_supervisor(request):
    return {
        'tem_acesso_supervisor': usuario_e_supervisor(
            request.user,
        ),
    }
