from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth import update_session_auth_hash

from ongs.models import Ong
from pets.models import Pet
from usuarios.forms import (AlterarSenhaForm, CadastroUsuarioForm, EditarContaForm, LoginEmailForm,)


def home(request):
    localizacao = request.GET.get('localizacao', '').strip()
    login_next = request.GET.get('next', '')

    pets = Pet.objects.publicos().select_related('ong')
    ongs_aprovadas = Ong.objects.filter(
        status=Ong.Status.APROVADA,
    ).annotate(
        pets_disponiveis=Count('pets', filter=Q(pets__status=Pet.Status.PUBLICADO)),
    )

    if localizacao:
        pets = pets.filter(
            Q(cidade__icontains=localizacao)
            | Q(estado__iexact=localizacao)
        )

    destino_anuncio = reverse('pets:anunciar')
    destino_admin = reverse('admin:index')
    destino_supervisor = reverse('supervisores:dashboard')

    next_seguro = url_has_allowed_host_and_scheme(
        url=login_next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )

    destino_permitido = (
        login_next == destino_anuncio
        or login_next.startswith(destino_admin)
        or login_next.startswith(destino_supervisor)
    )

    if (
        request.user.is_authenticated
        or not next_seguro
        or not destino_permitido
    ):
        login_next = ''

    conta_form = None
    senha_form = None
    abrir_conta = False
    painel_conta = 'menu'

    if (request.user.is_authenticated and hasattr(request.user, 'perfil')):
        conta_form = EditarContaForm(
            usuario=request.user,
        )

        senha_form = AlterarSenhaForm(
            user=request.user,
        )

        abrir_conta = request.GET.get('conta') == '1'

        if request.method == 'POST':
            acao = request.POST.get('acao')

            if acao == 'editar_conta':
                conta_form = EditarContaForm(
                    request.POST,
                    usuario=request.user,
                )

                abrir_conta = True
                painel_conta = 'cadastro'

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

            elif acao == 'alterar_senha':
                senha_form = AlterarSenhaForm(
                    user=request.user,
                    data=request.POST,
                )

                abrir_conta = True
                painel_conta = 'senha'

                if senha_form.is_valid():
                    usuario = senha_form.save()

                    update_session_auth_hash(
                        request,
                        usuario,
                    )

                    messages.success(
                        request,
                        'Sua senha foi alterada com sucesso!',
                    )

                    return redirect(
                        f"{reverse('home')}?conta=1"
                    )

    contexto = {
        'pets': pets[:12],
        'localizacao': localizacao,
        'total_pets': Pet.objects.publicos().count(),
        'total_adotados': Pet.objects.filter(status=Pet.Status.ADOTADO).count(),
        'ongs': ongs_aprovadas[:4],
        'total_ongs': ongs_aprovadas.count(),

        'login_form': LoginEmailForm(request=request),
        'cadastro_form': CadastroUsuarioForm(),
        'abrir_login': bool(login_next),
        'login_next': login_next,
        'login_aviso': (
            'Entre com uma conta de supervisor para acessar o painel.'
            if login_next.startswith(destino_supervisor)
            else 'Para anunciar um pet, entre na sua conta ou crie um cadastro.'
        ),

        'conta_form': conta_form,
        'senha_form': senha_form,
        'abrir_conta': abrir_conta,
        'painel_conta': painel_conta,
    }

    return render(
        request,
        'home.html',
        contexto,
    )
