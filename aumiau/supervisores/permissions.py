from functools import wraps
from urllib.parse import urlencode

from django.shortcuts import redirect, render
from django.urls import reverse


GRUPO_SUPERVISORES = 'Supervisores'


def usuario_e_supervisor(usuario):
    if not usuario.is_authenticated or not usuario.is_active:
        return False

    if usuario.is_superuser:
        return True

    return usuario.groups.filter(
        name=GRUPO_SUPERVISORES,
    ).exists()


def _redirecionar_para_login(request):
    parametros = urlencode({
        'next': request.get_full_path(),
    })

    return redirect(
        f"{reverse('home')}?{parametros}"
    )


def _acesso_negado(request, mensagem):
    return render(
        request,
        'supervisores/acesso_negado.html',
        {'mensagem_acesso_negado': mensagem},
        status=403,
    )


def supervisor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirecionar_para_login(request)

        if not usuario_e_supervisor(request.user):
            return _acesso_negado(
                request,
                'Sua conta não possui acesso ao painel de supervisão.',
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def supervisor_permission_required(*permissoes):
    def decorator(view_func):
        @wraps(view_func)
        @supervisor_required
        def wrapper(request, *args, **kwargs):
            if not request.user.has_perms(permissoes):
                return _acesso_negado(
                    request,
                    'Seu perfil de supervisor não possui esta permissão.',
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
