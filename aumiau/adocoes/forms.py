from django import forms
from django.core import signing

from .models import ChamadoAjuda


class ChamadoAjudaForm(forms.ModelForm):
    class Meta:
        model = ChamadoAjuda
        fields = ['categoria', 'assunto', 'mensagem']
        labels = {
            'categoria': 'Sobre o que você precisa falar?',
            'assunto': 'Assunto',
            'mensagem': 'Sua mensagem',
        }
        widgets = {
            'assunto': forms.TextInput(attrs={
                'placeholder': 'Resuma como podemos ajudar',
            }),
            'mensagem': forms.Textarea(attrs={
                'rows': 7,
                'placeholder': 'Conte o que aconteceu. Se for sobre um anúncio, inclua o link.',
                'maxlength': 5000,
            }),
        }

    def __init__(self, *args, usuario=None, pet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].choices = [('', 'Selecione uma opção')] + list(ChamadoAjuda.Categoria.choices)
        if pet is not None:
            self.fields['categoria'].disabled = True
        self.contexto_pluttu = ''
        token = self.data.get('conversa_pluttu', '') if self.is_bound else self.initial.get('conversa_pluttu', '')
        self.conversa_invalida = False
        if token:
            try:
                if len(token) > 30000:
                    raise signing.BadSignature('Conversa excedeu o limite.')
                dados = signing.loads(token, salt='pluttu-encaminhamento', max_age=3600)
                if dados['usuario'] != usuario.pk or not isinstance(dados['conversa'], str) or len(dados['conversa']) > 15000:
                    raise signing.BadSignature('Conversa de outra conta.')
                self.contexto_pluttu = dados['conversa']
            except (signing.BadSignature, KeyError, TypeError, AttributeError):
                self.conversa_invalida = True
            self.fields['conversa_pluttu'] = forms.CharField(widget=forms.HiddenInput, max_length=30000)
            self.fields['incluir_conversa'] = forms.BooleanField(
                required=False,
                label='Autorizo incluir a conversa abaixo neste chamado para a equipe de suporte.',
            )
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'ajuda-input'
            if self.is_bound and name in self.errors:
                field.widget.attrs['aria-invalid'] = 'true'
                field.widget.attrs['aria-describedby'] = f'id_{name}_errors'

    def clean(self):
        dados = super().clean()
        if self.conversa_invalida:
            raise forms.ValidationError('A conversa expirou ou não pôde ser confirmada. Volte ao Pluttu e escolha falar com a equipe novamente.')
        return dados


class PluttuForm(forms.Form):
    mensagem = forms.CharField(
        label='Sua dúvida para o Pluttu',
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'ajuda-input',
            'placeholder': 'Ex.: como anunciar um pet?',
            'autocomplete': 'off',
        }),
        error_messages={
            'required': 'Digite sua dúvida para conversar com o Pluttu.',
            'max_length': 'Escreva uma dúvida com até 500 caracteres.',
        },
    )
