import re

from django import forms
from django.utils import timezone

from ongs.models import Ong
from usuarios.models import UF_CHOICES
from .models import FotoPet, Pet
from .identidade import configurar_identidade, limpar_identidade


LIMITE_IMAGEM = 5 * 1024 * 1024
LIMITE_GALERIA = 6


class ImagemPetField(forms.ImageField):
    def clean(self, data, initial=None):
        if data and getattr(data, 'size', 0) > LIMITE_IMAGEM:
            raise forms.ValidationError('Cada imagem deve ter no máximo 5 MB.')
        imagem = super().clean(data, initial)
        if imagem and hasattr(imagem, 'image') and imagem.image.format not in {'JPEG', 'PNG'}:
            raise forms.ValidationError('Envie uma imagem JPG ou PNG.')
        return imagem


class ImagensInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class GaleriaField(ImagemPetField):
    widget = ImagensInput

    def clean(self, data, initial=None):
        if not data:
            return []
        arquivos = data if isinstance(data, (list, tuple)) else [data]
        if len(arquivos) > LIMITE_GALERIA:
            raise forms.ValidationError('A galeria pode ter até 6 imagens.')
        return [super(GaleriaField, self).clean(arquivo) for arquivo in arquivos]


class PetForm(forms.ModelForm):
    estado = forms.ChoiceField(label='Estado', choices=[('', 'Selecione'), *UF_CHOICES])
    raca = forms.ChoiceField(label='Raça ou tipo')
    raca_outra = forms.CharField(label='Qual raça ou tipo?', max_length=80, required=False)
    nascimento_desconhecido = forms.BooleanField(label='Não sei a data de nascimento', required=False)
    data_nascimento = forms.DateField(
        label='Data de nascimento', required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )
    idade_anos = forms.IntegerField(label='Anos (aproximadamente)', min_value=0, max_value=150, required=False)
    idade_meses = forms.IntegerField(label='Meses (aproximadamente)', min_value=0, max_value=11, required=False)
    foto_principal = ImagemPetField(
        label='Foto principal', required=False,
        widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png', 'data-preview-main': ''}),
    )
    galeria = GaleriaField(
        label='Outras fotos', required=False,
        widget=ImagensInput(attrs={'accept': 'image/jpeg,image/png', 'data-preview-gallery': ''}),
    )
    remover_fotos = forms.ModelMultipleChoiceField(
        label='Remover fotos da galeria', queryset=FotoPet.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    confirmar = forms.BooleanField(
        required=False,
        label='Confirmo que as informações são verdadeiras e que este pet será doado, sem cobrança.',
    )

    class Meta:
        model = Pet
        fields = (
            'nome', 'especie', 'raca', 'genero', 'porte', 'data_nascimento', 'idade_anos', 'idade_meses',
            'estado', 'cidade', 'descricao', 'ong', 'email_contato', 'telefone_contato',
            'foto_principal', 'vacinado', 'castrado', 'vermifugado', 'microchipado',
            'necessidades_especiais', 'descricao_necessidades_especiais',
        )
        labels = {
            'nome': 'Nome do pet', 'especie': 'Espécie', 'raca': 'Raça', 'genero': 'Sexo',
            'idade_anos': 'Anos', 'idade_meses': 'Meses', 'descricao': 'Conte a história do pet',
            'ong': 'Quem é responsável pelo pet?',
            'descricao_necessidades_especiais': 'Quais cuidados especiais ele precisa?',
        }
        widgets = {
            'genero': forms.RadioSelect, 'porte': forms.RadioSelect,
            'descricao': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Como ele é? Do que gosta? Conte um pouco da sua história…'}),
            'descricao_necessidades_especiais': forms.Textarea(attrs={'rows': 3}),
            'telefone_contato': forms.TextInput(attrs={'type': 'tel', 'placeholder': '(11) 99999-9999'}),
        }

    def __init__(self, *args, usuario, rascunho=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.rascunho = rascunho
        configurar_identidade(self)
        self.fields['ong'].queryset = Ong.objects.filter(
            responsavel=usuario, status=Ong.Status.APROVADA,
        ).order_by('nome')
        self.fields['ong'].empty_label = 'Eu sou responsável (pessoa física)'
        self.fields['descricao'].required = not rascunho
        self.fields['confirmar'].required = not rascunho
        if self.instance.pk:
            self.fields['remover_fotos'].queryset = self.instance.fotos.all()
        for nome, campo in self.fields.items():
            campo.widget.attrs.setdefault('class', 'pet-control')
        self.fields['nome'].widget.attrs.update({'placeholder': 'Como seu pet se chama?', 'data-pet-name': ''})
        self.fields['cidade'].widget.attrs.update({'placeholder': 'Cidade onde o pet está', 'data-pet-city': ''})
        self.fields['estado'].widget.attrs['data-pet-state'] = ''
        self.fields['idade_anos'].widget.attrs.update({'min': 0, 'max': 150})
        self.fields['idade_meses'].widget.attrs.update({'min': 0, 'max': 11})

    def clean_telefone_contato(self):
        telefone = re.sub(r'\D', '', self.cleaned_data.get('telefone_contato', ''))
        if telefone.startswith('55') and len(telefone) in (12, 13):
            telefone = telefone[2:]
        if telefone and len(telefone) not in (10, 11):
            raise forms.ValidationError('Informe o DDD e o telefone com 10 ou 11 dígitos.')
        return telefone

    def clean(self):
        dados = super().clean()
        limpar_identidade(self, dados)
        if not self.rascunho:
            if not dados.get('foto_principal') and 'foto_principal' not in self.errors:
                self.add_error('foto_principal', 'Adicione uma foto principal para enviar o anúncio.')
            if not dados.get('ong') and not (dados.get('email_contato') or dados.get('telefone_contato')):
                self.add_error('email_contato', 'Informe um e-mail ou telefone público para os interessados entrarem em contato.')
            ong = dados.get('ong')
            if ong and not (ong.email or ong.telefone):
                self.add_error('ong', 'Adicione um e-mail ou telefone público no cadastro da ONG antes de enviar o anúncio.')
            if dados.get('necessidades_especiais') and not dados.get('descricao_necessidades_especiais'):
                self.add_error('descricao_necessidades_especiais', 'Descreva os cuidados necessários.')
        if not dados.get('necessidades_especiais'):
            dados['descricao_necessidades_especiais'] = ''
        restantes = self.instance.fotos.count() if self.instance.pk else 0
        restantes -= len(dados.get('remover_fotos', []))
        if restantes + len(dados.get('galeria', [])) > LIMITE_GALERIA:
            self.add_error('galeria', 'A galeria pode ter até 6 fotos. Remova uma foto antes de adicionar outra.')
        return dados
