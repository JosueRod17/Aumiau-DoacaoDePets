"""Google OIDC: código no servidor, PKCE, state, nonce e ID token verificado."""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .documentos import assinatura_cpf
from .forms import CadastroGoogleForm
from .models import ContaGoogle, Perfil
from .backends import ContaBackend

TRANSACTION_KEY = 'google_oidc_transaction'
PENDING_KEY = 'google_registration'
REAUTH_KEY = 'google_reauthenticated'
LIFETIME = 600


def google_configurado():
    client = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    uri = urlparse(getattr(settings, 'GOOGLE_REDIRECT_URI', ''))
    uri_ok = uri.scheme == 'https' or (settings.DEBUG and uri.scheme == 'http' and uri.hostname in {'localhost', '127.0.0.1'})
    return bool(client and secret and uri_ok and uri.netloc and not uri.fragment)


def _destino_seguro(request, destino):
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return destino
    return reverse('home')


def reautenticacao_recente(request):
    prova = request.session.get(REAUTH_KEY, {})
    return (request.user.is_authenticated and prova.get('usuario') == request.user.pk
            and 0 <= time.time() - prova.get('em', 0) < 300)


@require_POST
def iniciar(request):
    if not google_configurado():
        messages.error(request, 'O acesso pelo Google ainda não está configurado. Entre com e-mail e senha.')
        return redirect('usuarios:login')
    finalidade = request.POST.get('finalidade', 'login')
    if finalidade not in {'login', 'vincular', 'reautenticar'}:
        return redirect('usuarios:login')
    if finalidade != 'login' and not request.user.is_authenticated:
        return redirect('usuarios:login')
    if finalidade == 'login' and request.user.is_authenticated:
        return redirect('home')
    estado, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    request.session[TRANSACTION_KEY] = {
        'state': estado, 'nonce': nonce, 'verifier': verifier, 'em': time.time(),
        'finalidade': finalidade, 'usuario': request.user.pk if request.user.is_authenticated else None,
        'next': _destino_seguro(request, request.POST.get('next', '')),
    }
    request.session.pop(PENDING_KEY, None)
    request.session.pop(REAUTH_KEY, None)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    parametros = {
        'client_id': settings.GOOGLE_CLIENT_ID, 'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'response_type': 'code', 'scope': 'openid email profile', 'state': estado, 'nonce': nonce,
        'code_challenge': challenge, 'code_challenge_method': 'S256', 'prompt': 'select_account',
    }
    return redirect('https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(parametros))


def _trocar_codigo(codigo, transacao):
    import requests
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import verify_oauth2_token

    class RequestComPrazo(Request):
        def __call__(self, *args, **kwargs):
            kwargs['timeout'] = 10
            return super().__call__(*args, **kwargs)

    resposta = requests.post('https://oauth2.googleapis.com/token', data={
        'code': codigo, 'client_id': settings.GOOGLE_CLIENT_ID, 'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': settings.GOOGLE_REDIRECT_URI, 'grant_type': 'authorization_code',
        'code_verifier': transacao['verifier'],
    }, timeout=10)
    resposta.raise_for_status()
    payload = resposta.json()
    token = payload.get('id_token')
    if not token:
        raise ValueError('ID token ausente.')
    # Biblioteca oficial valida assinatura Google, expiração, audiência e emissor.
    dados = verify_oauth2_token(token, RequestComPrazo(), settings.GOOGLE_CLIENT_ID)
    if not constant_time_compare(str(dados.get('nonce', '')), transacao['nonce']):
        raise ValueError('Nonce inválido.')
    if dados.get('azp') not in (None, settings.GOOGLE_CLIENT_ID):
        raise ValueError('Cliente autorizado incorreto.')
    if dados.get('email_verified') is not True or not dados.get('sub') or not dados.get('email'):
        raise ValueError('Identidade incompleta.')
    if len(str(dados['sub'])) > 255 or len(dados['email']) > 150:
        raise ValueError('Identidade incompatível.')
    return {'sub': str(dados['sub']), 'email': dados['email'].casefold(), 'name': str(dados.get('name', ''))[:150]}


def retorno(request):
    transacao = request.session.pop(TRANSACTION_KEY, None)
    if (not google_configurado() or not transacao
            or not 0 <= time.time() - transacao.get('em', 0) <= LIFETIME
            or not constant_time_compare(request.GET.get('state', ''), transacao.get('state', ''))
            or not request.GET.get('code') or request.GET.get('error')):
        messages.error(request, 'Não foi possível confirmar o acesso pelo Google. Tente novamente.')
        return redirect('usuarios:login')
    try:
        identidade = _trocar_codigo(request.GET['code'], transacao)
    except Exception:
        # Nunca retornar token, código OAuth, CPF ou detalhes de credenciais ao navegador.
        messages.error(request, 'O Google não confirmou seu acesso. Tente novamente em instantes.')
        return redirect('usuarios:login')
    conta = ContaGoogle.objects.select_related('usuario').filter(subject=identidade['sub']).first()
    finalidade = transacao['finalidade']
    if finalidade in {'vincular', 'reautenticar'}:
        if not request.user.is_authenticated or request.user.pk != transacao['usuario']:
            messages.error(request, 'Sua sessão mudou. Entre novamente e repita a confirmação.')
            return redirect('usuarios:login')
        if finalidade == 'vincular':
            try:
                with transaction.atomic():
                    if conta and conta.usuario_id != request.user.pk:
                        raise ValueError('Google já vinculado.')
                    ContaGoogle.objects.get_or_create(usuario=request.user, defaults={'subject': identidade['sub']})
                    if request.user.conta_google.subject != identidade['sub']:
                        raise ValueError('Já existe outro vínculo.')
            except (IntegrityError, ValueError):
                messages.error(request, 'Esta conta Google já tem um vínculo diferente. Procure o suporte.')
                return redirect('home')
        elif not conta or conta.usuario_id != request.user.pk:
            messages.error(request, 'Use a mesma conta Google vinculada ao seu cadastro.')
            return redirect('home')
        request.session[REAUTH_KEY] = {'usuario': request.user.pk, 'em': time.time()}
        messages.success(request, 'Identidade confirmada pelo Google.')
        return redirect(_destino_seguro(request, transacao['next']))
    if conta:
        if not ContaBackend().user_can_authenticate(conta.usuario):
            messages.error(request, 'Esta conta está indisponível. Entre em contato com o suporte.')
            return redirect('usuarios:login')
        login(request, conta.usuario, backend=settings.AUTHENTICATION_BACKENDS[0])
        return redirect(_destino_seguro(request, transacao['next']))
    if get_user_model().objects.filter(Q(email__iexact=identidade['email']) | Q(username__iexact=identidade['email'])).exists():
        messages.info(request, 'Já existe uma conta com este e-mail. Entre com sua senha e use “Vincular Google” em Minha conta.')
        return redirect('usuarios:login')
    request.session[PENDING_KEY] = identidade | {'em': time.time(), 'next': transacao['next']}
    return redirect('usuarios:google_completar')


def completar(request):
    if request.user.is_authenticated:
        return redirect('home')
    identidade = request.session.get(PENDING_KEY)
    if not identidade or not 0 <= time.time() - identidade.get('em', 0) <= LIFETIME:
        request.session.pop(PENDING_KEY, None)
        messages.info(request, 'Entre novamente com o Google para concluir seu cadastro.')
        return redirect('usuarios:login')
    form = CadastroGoogleForm(request.POST or None, identidade=identidade)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                usuario = form.save()
                Perfil.objects.create(
                    usuario=usuario, telefone=form.cleaned_data['telefone'], cidade=form.cleaned_data['cidade'],
                    estado=form.cleaned_data['estado'], cpf_hash=assinatura_cpf(form.cleaned_data['cpf']),
                    cpf_final=form.cleaned_data['cpf'][-4:], aceitou_termos_em=timezone.now(), versao_termos=settings.TERMOS_VERSAO,
                )
                ContaGoogle.objects.create(usuario=usuario, subject=identidade['sub'])
        except IntegrityError:
            form.add_error(None, 'Não foi possível criar a conta. Verifique o e-mail e o CPF ou procure o suporte.')
        else:
            request.session.pop(PENDING_KEY, None)
            login(request, usuario, backend=settings.AUTHENTICATION_BACKENDS[0])
            return redirect(_destino_seguro(request, identidade['next']))
    return render(request, 'usuarios/google_completar.html', {'form': form})


@login_required
def senha(request):
    if request.user.has_usable_password():
        return redirect(reverse('home') + '?conta=1')
    confirmado = reautenticacao_recente(request)
    form = SetPasswordForm(request.user, request.POST or None)
    if request.method == 'POST':
        form.is_valid()
        if not confirmado:
            form.add_error(None, 'Confirme sua identidade com o Google antes de criar uma senha.')
        elif form.is_valid():
            usuario = form.save()
            update_session_auth_hash(request, usuario)
            request.session.pop(REAUTH_KEY, None)
            messages.success(request, 'Senha criada. Você também pode entrar com e-mail e senha.')
            return redirect(reverse('home') + '?conta=1')
    return render(request, 'usuarios/google_senha.html', {'form': form, 'google_confirmado': confirmado})
