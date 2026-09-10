from django.conf import settings
from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import CadastroUsuarioForm
from .models import Perfil


def cadastro(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = CadastroUsuarioForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                usuario = form.save()
                cidade, estado = form.obter_localizacao()

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
            return redirect('home')

    return render(
        request,
        'usuarios/cadastro.html',
        {'form': form},
    )