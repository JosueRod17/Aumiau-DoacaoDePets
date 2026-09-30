import re

from django import forms

from usuarios.models import UF_CHOICES
from .cnpj import consultar_cnpj, validar_cnpj

from .models import Ong


class CadastroOngForm(forms.ModelForm):
    cnpj = forms.CharField(
        label='CNPJ', max_length=18,
        help_text='Consultaremos o cadastro público pela BrasilAPI. CNPJs alfanuméricos precisam de conferência documental pela equipe.',
        widget=forms.TextInput(attrs={'placeholder': '00.000.000/0001-00', 'autocomplete': 'off', 'autocapitalize': 'characters'}),
    )
    estado = forms.ChoiceField(label='Estado', choices=[('', 'Selecione a UF'), *UF_CHOICES])
    telefone = forms.CharField(
        label='Telefone público', max_length=20, required=False,
        widget=forms.TextInput(attrs={'placeholder': '(00) 00000-0000', 'autocomplete': 'tel', 'inputmode': 'tel'}),
    )

    class Meta:
        model = Ong
        fields = ('nome', 'cnpj', 'foto', 'estado', 'cidade', 'descricao', 'email', 'telefone')
        labels = {'nome': 'Nome da ONG', 'cidade': 'Cidade', 'descricao': 'Sobre a ONG', 'email': 'E-mail público'}
        widgets = {
            'nome': forms.TextInput(attrs={'placeholder': 'Como sua organização se chama?', 'autocomplete': 'organization'}),
            'cidade': forms.TextInput(attrs={'placeholder': 'Cidade de atuação', 'autocomplete': 'address-level2'}),
            'descricao': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Conte a história da ONG e como vocês cuidam dos animais.'}),
            'email': forms.EmailInput(attrs={'placeholder': 'contato@suaong.org', 'autocomplete': 'email'}),
        }
        help_texts = {
            'email': 'Opcional. Será exibido no perfil público da ONG.',
            'telefone': 'Opcional. Informe somente um contato da ONG que possa ser divulgado.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.codigo_demonstracao:
            self.fields['cnpj'].required = False
            self.fields['cnpj'].help_text = 'Perfil de demonstração: não informe documentos reais.'
        if 'foto' in self.fields:
            self.fields['foto'].widget.attrs['accept'] = 'image/jpeg,image/png'
            self.fields['foto'].help_text = 'Foto da organização ou dos animais. JPG ou PNG, até 5 MB.'
        self.fields['telefone'].help_text = self.Meta.help_texts['telefone']
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'ongs-form__controle'
            if field.help_text:
                field.widget.attrs['aria-describedby'] = f'id_{name}_helptext'

    def clean_telefone(self):
        entrada = self.cleaned_data.get('telefone', '').strip()
        telefone = re.sub(r'[^0-9]', '', entrada)
        if entrada and len(telefone) not in (10, 11):
            raise forms.ValidationError('Informe um telefone válido com DDD.')
        return telefone

    def clean_email(self):
        return self.cleaned_data.get('email', '').strip().casefold()

    def clean_cnpj(self):
        if self.instance.codigo_demonstracao:
            if self.cleaned_data.get('cnpj'):
                raise forms.ValidationError('Perfis fictícios não devem receber documentos reais.')
            return None
        cnpj = validar_cnpj(self.cleaned_data['cnpj'])
        if Ong.objects.filter(cnpj=cnpj).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Já existe uma ONG com este CNPJ. Fale com o suporte se precisar recuperar o acesso.')
        return cnpj

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if foto and foto.size > 5 * 1024 * 1024:
            raise forms.ValidationError('A foto deve ter no máximo 5 MB.')
        if foto and hasattr(foto, 'image') and foto.image.format not in {'JPEG', 'PNG'}:
            raise forms.ValidationError('Envie uma imagem JPG ou PNG.')
        return foto

    def clean(self):
        dados = super().clean()
        self._consulta_cnpj = None
        if not self.errors and dados.get('cnpj'):
            try:
                self._consulta_cnpj = consultar_cnpj(dados['cnpj'])
            except forms.ValidationError as erro:
                self.add_error('cnpj', erro)
        return dados

    def save(self, commit=True):
        mudou = self.instance.cnpj != self.initial.get('cnpj')
        ong = super().save(commit=False)
        if mudou:
            ong.cnpj_confirmado_manualmente = False
        consulta = self._consulta_cnpj
        ong.razao_social = consulta['razao_social'] if consulta else ''
        ong.cnpj_situacao = consulta['situacao'] if consulta else ''
        ong.cnpj_consultado_em = consulta['consultado_em'] if consulta else None
        if commit:
            ong.save()
            self.save_m2m()
        return ong
