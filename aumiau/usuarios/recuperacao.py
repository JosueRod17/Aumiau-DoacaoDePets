"""Recuperação de senha sem revelar se um endereço pertence a uma conta."""

from django import forms
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.crypto import salted_hmac

from .models import Perfil


SITUACOES_BLOQUEADAS = (Perfil.Situacao.SUSPENSA, Perfil.Situacao.BANIDA, Perfil.Situacao.EXCLUIDA)


class RecuperarSenhaForm(PasswordResetForm):
    email = forms.EmailField(
        label='E-mail da conta',
        max_length=254,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'seuemail@exemplo.com', 'class': 'ajuda-input'}),
    )

    def get_users(self, email):
        for user in super().get_users(email):
            if not Perfil.objects.filter(usuario_id=user.pk, situacao__in=SITUACOES_BLOQUEADAS).exists():
                yield user


class DefinirNovaSenhaForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, label in (('new_password1', 'Nova senha'), ('new_password2', 'Confirmar nova senha')):
            field = self.fields[name]
            field.label = label
            field.widget.attrs.update({'autocomplete': 'new-password', 'placeholder': label, 'class': 'ajuda-input'})


def _contar_tentativa(chave, limite, duracao):
    cache.add(chave, 0, duracao)
    try:
        return cache.incr(chave) <= limite
    except ValueError:
        cache.set(chave, 1, duracao)
        return True


def _permitir_solicitacao(email):
    # A chave no cache não contém o endereço de e-mail em texto puro.
    email_hash = salted_hmac('aumiau.recuperacao', email.strip().casefold()).hexdigest()
    return (
        _contar_tentativa(f'aumiau:recuperacao:{email_hash}', 3, 15 * 60)
        and _contar_tentativa('aumiau:recuperacao:global', 100, 60 * 60)
    )


class SolicitarRecuperacaoView(PasswordResetView):
    template_name = 'usuarios/recuperar.html'
    form_class = RecuperarSenhaForm
    email_template_name = 'usuarios/recuperar_email.txt'
    subject_template_name = 'usuarios/recuperar_assunto.txt'
    success_url = reverse_lazy('usuarios:recuperar_enviado')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recuperacao_disponivel'] = settings.EMAIL_RECOVERY_AVAILABLE
        return context

    def form_valid(self, form):
        if not settings.EMAIL_RECOVERY_AVAILABLE:
            form.add_error(None, 'A recuperação por e-mail está temporariamente indisponível. Tente novamente mais tarde.')
            return self.form_invalid(form)
        if not _permitir_solicitacao(form.cleaned_data['email']):
            return HttpResponseRedirect(self.get_success_url())
        return super().form_valid(form)


class RecuperacaoEnviadaView(PasswordResetDoneView):
    template_name = 'usuarios/recuperar_enviado.html'


class ConfirmarRecuperacaoView(PasswordResetConfirmView):
    template_name = 'usuarios/recuperar_confirmar.html'
    form_class = DefinirNovaSenhaForm
    success_url = reverse_lazy('usuarios:recuperar_concluido')

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        if not user or not user.is_active:
            return None
        if Perfil.objects.filter(usuario_id=user.pk, situacao__in=SITUACOES_BLOQUEADAS).exists():
            return None
        return user


class RecuperacaoConcluidaView(PasswordResetCompleteView):
    template_name = 'usuarios/recuperar_concluido.html'
