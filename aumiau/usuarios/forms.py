import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db.models import Q

from .models import UF_CHOICES


User = get_user_model()
UF_FORM_CHOICES = [
    ('', 'Selecione a UF'),
    *UF_CHOICES,
]


def preparar_select_cidade(formulario):
    if formulario.is_bound:
        estado = formulario.data.get(
            formulario.add_prefix('estado'),
            '',
        ).strip().upper()

        cidade = formulario.data.get(
            formulario.add_prefix('cidade'),
            '',
        ).strip()
    else:
        estado = str(
            formulario.initial.get('estado', '') or ''
        ).strip().upper()

        cidade = str(
            formulario.initial.get('cidade', '') or ''
        ).strip()

    texto_inicial = (
        'Selecione a cidade'
        if estado
        else 'Selecione primeiro a UF'
    )

    opcoes = [('', texto_inicial)]

    if cidade:
        opcoes.append((cidade, cidade))

    formulario.fields['cidade'].widget.choices = opcoes


class LoginEmailForm(AuthenticationForm):
    username = forms.EmailField(
        label='E-mail',
        max_length=150,
        widget=forms.EmailInput(
            attrs={
                'placeholder': '✉  seuemail@exemplo.com',
                'autocomplete': 'email',
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

    estado = forms.ChoiceField(
    label='UF',
    choices=UF_FORM_CHOICES,
    widget=forms.Select(
        attrs={
            'data-uf-select': '',
            'autocomplete': 'address-level1',
        }
    ),
)

    cidade = forms.CharField(
        label='Cidade',
        max_length=100,
        widget=forms.Select(
            attrs={
                'data-cidade-select': '',
                'autocomplete': 'address-level2',
            },
            choices=[
                ('', 'Selecione primeiro a UF'),
            ],
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
            'estado',
            'cidade',
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

        preparar_select_cidade(self)

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

    def clean_cidade(self):
        cidade = self.cleaned_data['cidade'].strip()

        if not cidade:
            raise forms.ValidationError(
                'Selecione sua cidade.'
            )

        return cidade

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

class EditarContaForm(forms.Form):
    nome_completo = forms.CharField(
        label='Nome completo',
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Digite seu nome completo',
                'autocomplete': 'name',
            }
        ),
    )

    email = forms.EmailField(
        label='E-mail',
        disabled=True,
        widget=forms.EmailInput(
            attrs={
                'autocomplete': 'email',
            }
        ),
    )

    telefone = forms.CharField(
        label='Telefone',
        max_length=20,
        widget=forms.TextInput(
            attrs={
                'placeholder': '(00) 00000-0000',
                'autocomplete': 'tel',
                'inputmode': 'tel',
            }
        ),
    )

    estado = forms.ChoiceField(
        label='UF',
        choices=UF_FORM_CHOICES,
        widget=forms.Select(
            attrs={
                'data-uf-select': '',
                'autocomplete': 'address-level1',
            }
        ),
    )

    cidade = forms.CharField(
        label='Cidade',
        max_length=100,
        widget=forms.Select(
            attrs={
                'data-cidade-select': '',
                'autocomplete': 'address-level2',
            },
            choices=[
                ('', 'Selecione primeiro a UF'),
            ],
        ),
    )

    senha_atual = forms.CharField(
        label='Confirme sua senha',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Digite sua senha atual',
                'autocomplete': 'current-password',
            }
        ),
    )

    def __init__(self, *args, usuario, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

        perfil = usuario.perfil

        self.initial.update({
            'nome_completo': usuario.get_full_name(),
            'email': usuario.email,
            'telefone': perfil.telefone,
            'cidade': perfil.cidade,
            'estado': perfil.estado,
        })

        preparar_select_cidade(self)

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

    def clean_cidade(self):
        cidade = self.cleaned_data['cidade'].strip()

        if not cidade:
            raise forms.ValidationError('Informe sua cidade.')

        return cidade

    def clean_senha_atual(self):
        senha_atual = self.cleaned_data['senha_atual']

        if not self.usuario.check_password(senha_atual):
            raise forms.ValidationError('A senha atual está incorreta.')

        return senha_atual

    def save(self):
        partes_nome = (
            self.cleaned_data['nome_completo']
            .strip()
            .split(maxsplit=1)
        )

        self.usuario.first_name = partes_nome[0]
        self.usuario.last_name = (
            partes_nome[1] if len(partes_nome) > 1 else ''
        )

        self.usuario.save(
            update_fields=['first_name', 'last_name']
        )

        perfil = self.usuario.perfil
        perfil.telefone = self.cleaned_data['telefone']
        perfil.cidade = self.cleaned_data['cidade']
        perfil.estado = self.cleaned_data['estado']
        perfil.save(
            update_fields=[
                'telefone',
                'cidade',
                'estado',
                'atualizado_em',
            ]
        )

        return self.usuario