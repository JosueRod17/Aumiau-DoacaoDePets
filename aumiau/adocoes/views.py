from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from ongs.models import Ong
from pets.models import Pet
from usuarios.forms import (CadastroUsuarioForm, EditarContaForm, LoginEmailForm,)


def home(request):
    localizacao = request.GET.get('localizacao', '').strip()
    login_next = request.GET.get('next', '')

    pets = Pet.objects.filter(disponivel=True)
    ongs_aprovadas = Ong.objects.filter(aprovada=True)

    if localizacao:
        pets = pets.filter(
            Q(cidade__icontains=localizacao)
            | Q(estado__iexact=localizacao)
        )

    destino_anuncio = reverse('pets:anunciar')

    next_seguro = url_has_allowed_host_and_scheme(
        url=login_next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )

    if (
        request.user.is_authenticated
        or not next_seguro
        or login_next != destino_anuncio
    ):
        login_next = ''

    conta_form = None
    abrir_conta = False

    if request.user.is_authenticated:
        conta_form = EditarContaForm(usuario=request.user)
        abrir_conta = request.GET.get('conta') == '1'

        if (
            request.method == 'POST'
            and request.POST.get('acao') == 'editar_conta'
        ):
            conta_form = EditarContaForm(
                request.POST,
                usuario=request.user,
            )
            abrir_conta = True

            if conta_form.is_valid():
                with transaction.atomic():
                    conta_form.save()

                messages.success(
                    request,
                    'Seus dados foram atualizados com sucesso!',
                )

                return redirect(
                    f"{reverse('home')}?conta=1"
                )

    contexto = {
        'pets': pets[:4],
        'localizacao': localizacao,
        'total_pets': Pet.objects.count(),
        'ongs': ongs_aprovadas[:4],
        'total_ongs': ongs_aprovadas.count(),

        'login_form': LoginEmailForm(request=request),
        'cadastro_form': CadastroUsuarioForm(),
        'abrir_login': bool(login_next),
        'login_next': login_next,

        'conta_form': conta_form,
        'abrir_conta': abrir_conta,
    }

    return render(request, 'home.html', contexto)