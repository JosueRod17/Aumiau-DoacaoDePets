from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from supervisores.permissions import usuario_e_supervisor

from .forms import CadastroUsuarioForm, LoginEmailForm
from .models import Perfil


class LoginUsuarioView(LoginView):
    template_name = 'usuarios/login.html'
    authentication_form = LoginEmailForm
    redirect_authenticated_user = True

    def get_success_url(self):
        destino = self.get_redirect_url()

        if destino:
            return destino

        if usuario_e_supervisor(self.request.user):
            return reverse('supervisores:dashboard')

        return resolve_url(settings.LOGIN_REDIRECT_URL)


def cadastro(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = CadastroUsuarioForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                usuario = form.save()
                cidade = form.cleaned_data['cidade']
                estado = form.cleaned_data['estado']

                Perfil.objects.create(
                    usuario=usuario,
                    telefone=form.cleaned_data['telefone'],
                    cidade=cidade,
                    estado=estado,
                    aceitou_termos_em=timezone.now(),
                    versao_termos=settings.TERMOS_VERSAO,
                )

        except IntegrityError:
            form.add_error(
                'email',
                'Não foi possível criar a conta. Verifique o e-mail.',
            )

        else:
            login(request, usuario)
            destino = request.POST.get('next', '')

            if destino and url_has_allowed_host_and_scheme(
                url=destino,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(destino)

            return redirect('home')

    return render(
        request,
        'usuarios/cadastro.html',
        {'form': form},
    )
