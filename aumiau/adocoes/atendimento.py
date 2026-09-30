from django import forms

from .models import ChamadoAjuda


class AtendimentoChamadoForm(forms.ModelForm):
    class Meta:
        model = ChamadoAjuda
        fields = ['status', 'resposta']
        labels = {'status': 'Situação do chamado', 'resposta': 'Resposta ao usuário'}
        help_texts = {
            'resposta': (
                'A resposta será exibida em Meus chamados. Ao responder um chamado '
                'recebido ou em análise, ele será marcado como respondido. '
                'Nenhum e-mail é enviado automaticamente.'
            ),
        }
        widgets = {
            'resposta': forms.Textarea(attrs={'rows': 8, 'class': 'supervisor-form__controle'}),
            'status': forms.Select(attrs={'class': 'supervisor-form__controle'}),
        }

    def clean(self):
        dados = super().clean()
        resposta = dados.get('resposta', '')
        status = dados.get('status')
        if status == ChamadoAjuda.Status.RESPONDIDO and not resposta:
            self.add_error('resposta', 'Escreva a resposta antes de marcar o chamado como respondido.')
        elif resposta and 'resposta' in self.changed_data and status in (
            ChamadoAjuda.Status.ABERTO, ChamadoAjuda.Status.EM_ANALISE,
        ):
            dados['status'] = ChamadoAjuda.Status.RESPONDIDO
        return dados
