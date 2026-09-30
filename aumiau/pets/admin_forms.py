from copy import deepcopy

from django import forms

from .forms import ImagemPetField, PetForm
from .identidade import configurar_identidade, limpar_identidade
from .models import Pet
from usuarios.models import UF_CHOICES


class PetAdminForm(forms.ModelForm):
    estado = forms.ChoiceField(label='Estado', choices=[('', 'Selecione a UF'), *UF_CHOICES])
    raca = deepcopy(PetForm.base_fields['raca'])
    raca_outra = deepcopy(PetForm.base_fields['raca_outra'])
    data_nascimento = deepcopy(PetForm.base_fields['data_nascimento'])
    nascimento_desconhecido = deepcopy(PetForm.base_fields['nascimento_desconhecido'])
    idade_anos = deepcopy(PetForm.base_fields['idade_anos'])
    idade_meses = deepcopy(PetForm.base_fields['idade_meses'])
    foto_principal = ImagemPetField(
        label='Foto principal', required=False,
        widget=forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png'}),
    )

    class Meta:
        model = Pet
        fields = '__all__'
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 5}),
            'descricao_necessidades_especiais': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configurar_identidade(self)
        self.fields['nome'].label = 'Nome do pet'
        self.fields['especie'].label = 'Espécie'
        self.fields['responsavel'].label = 'Responsável individual'
        self.fields['responsavel'].empty_label = 'Sem responsável individual'
        self.fields['ong'].label = 'ONG'
        self.fields['ong'].empty_label = 'Sem ONG vinculada'
        self.fields['descricao'].label = 'História do pet'

    def clean(self):
        dados = super().clean()
        limpar_identidade(self, dados)
        if dados.get('responsavel') and dados.get('ong'):
            self.add_error('ong', 'Escolha uma ONG ou um responsável individual.')
        if dados.get('necessidades_especiais') and not dados.get('descricao_necessidades_especiais'):
            self.add_error('descricao_necessidades_especiais', 'Descreva os cuidados necessários.')
        return dados
