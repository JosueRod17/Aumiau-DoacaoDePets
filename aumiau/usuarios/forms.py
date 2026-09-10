import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db.models import Q

from .models import UF_CHOICES


User = get_user_model()
UFS_VALIDAS = {sigla for sigla, nome in UF_CHOICES}


class LoginEmailForm(AuthenticationForm):
    username = forms.EmailField(
        label='E-mail',
        max_length=150,
        widget=forms.EmailInput(
            attrs={
                'placeholder': '✉  seuemail@exemplo.com',
                'autocomplete': 'email',
                'autofocus': True,
            }
        ),
    )

    password = forms.CharField(
        label='Senha',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': '🔒  Digite sua senha',
                'autocomplete': 'current-password',
            }
        ),
    )

    error_messages = {
        'invalid_login': 'E-mail ou senha inválidos.',
        'inactive': 'Esta conta está inativa.',
    }

    def clean_username(self):
        return self.cleaned_data['username'].strip().casefold()


class CadastroUsuarioForm(UserCreationForm):
    nome_completo = forms.CharField(
        label='Nome completo',
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'placeholder': '👤  Como podemos chamar você?',
                'autocomplete': 'name',
            }
        ),
    )

    email = forms.EmailField(
        label='E-mail',
        max_length=150,
        widget=forms.EmailInput(
            attrs={
                'placeholder': '✉  seuemail@exemplo.com',
                'autocomplete': 'email',
            }
        ),
    )

    telefone = forms.CharField(
        label='Telefone',
        max_length=20,
        widget=forms.TextInput(
            attrs={
                'placeholder': '☎  (00) 00000-0000',
                'autocomplete': 'tel',
                'inputmode': 'tel',
            }
        ),
    )

    localizacao = forms.CharField(
        label='Cidade / UF',
        max_length=105,
        widget=forms.TextInput(
            attrs={
                'placeholder': '📍  Brasília, DF',
                'autocomplete': 'address-level2',
            }
        ),
    )

    aceite_termos = forms.BooleanField(
        label='Li e aceito os Termos de Uso e a Política de Privacidade.',
        required=True,
        error_messages={
            'required': 'Você precisa aceitar os termos para continuar.',
        },
    )

    class Meta:
        model = User

        fields = (
            'nome_completo',
            'email',
            'telefone',
            'localizacao',
            'password1',
            'password2',
            'aceite_termos',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['password1'].label = 'Senha'
        self.fields['password1'].widget.attrs.update({
            'placeholder': '🔒  Crie uma senha segura',
            'autocomplete': 'new-password',
        })

        self.fields['password2'].label = 'Confirmar senha'
        self.fields['password2'].widget.attrs.update({
            'placeholder': '🔒  Digite a senha novamente',
            'autocomplete': 'new-password',
        })

    def clean_email(self):
        email = self.cleaned_data['email'].strip().casefold()

        email_existente = User.objects.filter(
            Q(username__iexact=email) |
            Q(email__iexact=email)
        ).exists()

        if email_existente:
            raise forms.ValidationError(
                'Já existe uma conta com este e-mail.'
            )

        return email

    def clean_telefone(self):
        telefone = re.sub(
            r'\D',
            '',
            self.cleaned_data['telefone'],
        )

        if len(telefone) not in (10, 11):
            raise forms.ValidationError(
                'Informe um telefone válido com DDD.'
            )

        return telefone

    def clean_localizacao(self):
        localizacao = self.cleaned_data['localizacao'].strip()

        if ',' not in localizacao:
            raise forms.ValidationError(
                'Informe a cidade e o estado no formato Cidade, UF.'
            )

        cidade, estado = localizacao.rsplit(',', 1)
        cidade = cidade.strip()
        estado = estado.strip().upper()

        if not cidade:
            raise forms.ValidationError('Informe sua cidade.')

        if estado not in UFS_VALIDAS:
            raise forms.ValidationError(
                'Informe uma UF brasileira válida.'
            )

        return f'{cidade}, {estado}'

    def obter_localizacao(self):
        cidade, estado = self.cleaned_data['localizacao'].rsplit(',', 1)

        return cidade.strip(), estado.strip().upper()

    def save(self, commit=True):
        usuario = super().save(commit=False)

        email = self.cleaned_data['email']
        partes_nome = self.cleaned_data['nome_completo'].strip().split(
            maxsplit=1
        )

        usuario.username = email
        usuario.email = email
        usuario.first_name = partes_nome[0]
        usuario.last_name = (
            partes_nome[1] if len(partes_nome) > 1 else ''
        )

        if commit:
            usuario.save()

        return usuario