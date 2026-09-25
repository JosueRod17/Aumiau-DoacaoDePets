from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from django.db.models import Q

from ongs.models import Ong
from pets.models import FotoPet, Pet
from usuarios.models import UF_CHOICES

from .permissions import GRUPO_SUPERVISORES


LIMITE_IMAGEM = 5 * 1024 * 1024


def validar_tamanho_imagem(imagem):
    if imagem and imagem.size > LIMITE_IMAGEM:
        raise forms.ValidationError(
            'A imagem deve possuir no máximo 5 MB.'
        )

    return imagem


class PetSupervisorForm(forms.ModelForm):
    estado = forms.ChoiceField(
        label='UF',
        choices=[('', 'Selecione a UF'), *UF_CHOICES],
    )

    class Meta:
        model = Pet
        fields = (
            'nome',
            'especie',
            'raca',
            'genero',
            'porte',
            'idade_anos',
            'idade_meses',
            'responsavel',
            'ong',
            'estado',
            'cidade',
            'descricao',
            'foto_principal',
            'vacinado',
            'castrado',
            'vermifugado',
            'microchipado',
            'necessidades_especiais',
            'descricao_necessidades_especiais',
            'destaque',
        )
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 5}),
            'descricao_necessidades_especiais': forms.Textarea(
                attrs={'rows': 3}
            ),
            'foto_principal': forms.ClearableFileInput(
                attrs={'accept': 'image/*'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        Usuario = get_user_model()

        responsaveis = (
            Usuario.objects
            .filter(is_active=True, is_superuser=False)
            .exclude(groups__name=GRUPO_SUPERVISORES)
            .distinct()
        )

        if self.instance and self.instance.responsavel_id:
            responsaveis = Usuario.objects.filter(
                Q(pk__in=responsaveis)
                | Q(pk=self.instance.responsavel_id)
            )

        self.fields['responsavel'].queryset = (
            responsaveis
            .distinct()
            .order_by('first_name', 'last_name', 'username')
        )

        filtro_ongs = Q(status=Ong.Status.APROVADA)

        if self.instance and self.instance.ong_id:
            filtro_ongs |= Q(pk=self.instance.ong_id)

        self.fields['ong'].queryset = (
            Ong.objects
            .filter(filtro_ongs)
            .order_by('nome')
        )

        self.fields['responsavel'].required = False
        self.fields['ong'].required = False

        self.fields['responsavel'].empty_label = 'Sem responsável individual'
        self.fields['ong'].empty_label = 'Sem ONG vinculada'

        self.fields['idade_anos'].label = 'Anos'
        self.fields['idade_meses'].label = 'Meses'

        for campo in self.fields.values():
            classe_atual = campo.widget.attrs.get('class', '')
            campo.widget.attrs['class'] = (
                f'{classe_atual} supervisor-form__controle'.strip()
            )

    def clean(self):
        dados = super().clean()
        responsavel = dados.get('responsavel')
        ong = dados.get('ong')

        if responsavel and ong:
            mensagem = (
                'Escolha somente um responsável: usuário ou ONG.'
            )
            self.add_error('responsavel', mensagem)
            self.add_error('ong', mensagem)

        if not responsavel and not ong:
            mensagem = 'Informe um usuário responsável ou uma ONG.'
            self.add_error('responsavel', mensagem)
            self.add_error('ong', mensagem)

        if (
            not dados.get('necessidades_especiais')
            and dados.get('descricao_necessidades_especiais')
        ):
            dados['descricao_necessidades_especiais'] = ''

        return dados

    def clean_foto_principal(self):
        return validar_tamanho_imagem(
            self.cleaned_data.get('foto_principal')
        )


class FotoPetSupervisorForm(forms.ModelForm):
    class Meta:
        model = FotoPet
        fields = ('imagem', 'legenda', 'ordem')
        widgets = {
            'imagem': forms.ClearableFileInput(
                attrs={'accept': 'image/*'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for campo in self.fields.values():
            classe_atual = campo.widget.attrs.get('class', '')
            campo.widget.attrs['class'] = (
                f'{classe_atual} supervisor-form__controle'.strip()
            )

    def clean_imagem(self):
        return validar_tamanho_imagem(
            self.cleaned_data.get('imagem')
        )


FotoPetSupervisorFormSet = inlineformset_factory(
    Pet,
    FotoPet,
    form=FotoPetSupervisorForm,
    extra=6,
    max_num=6,
    validate_max=True,
    can_delete=True,
)


class OngSupervisorForm(forms.ModelForm):
    estado = forms.ChoiceField(
        label='UF',
        choices=[('', 'Selecione a UF'), *UF_CHOICES],
    )

    class Meta:
        model = Ong
        fields = (
            'nome',
            'estado',
            'cidade',
            'descricao',
        )
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for campo in self.fields.values():
            classe_atual = campo.widget.attrs.get('class', '')
            campo.widget.attrs['class'] = (
                f'{classe_atual} supervisor-form__controle'.strip()
            )
