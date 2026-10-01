from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from adocoes.models import SolicitacaoAdocao
from adocoes.solicitacao_service import decidir_solicitacao
from adocoes.contato_adocao import mensagem_aprovacao
from .permissions import supervisor_permission_required


class DecisaoAdocaoForm(forms.Form):
    resposta = forms.CharField(
        label='Resposta ao interessado', required=False, max_length=5000,
        widget=forms.Textarea(attrs={'rows': 5, 'class': 'supervisor-form__controle'}),
        help_text='Ao aprovar, deixe em branco para usar a mensagem sugerida. Ao recusar, explique o motivo. A resposta ficará em Minhas adoções.',
    )
    acao = forms.ChoiceField(label='Decisão', choices=[('', 'Selecione uma decisão'),
                                                    ('aprovar', 'Aprovar adoção'), ('recusar', 'Recusar pedido')],
                             widget=forms.Select(attrs={'class': 'supervisor-form__controle'}))

    def __init__(self, *args, pet, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(['acao', 'resposta'])
        self.mensagem_aprovacao = mensagem_aprovacao(pet)
        self.placeholder_recusa = 'Explique ao interessado por que o pedido de adoção não pôde ser aprovado.'
        self.fields['resposta'].widget.attrs.update({
            'placeholder': self.placeholder_recusa if self.is_bound and self.data.get('acao') == 'recusar' else self.mensagem_aprovacao,
            'data-placeholder-aprovacao': self.mensagem_aprovacao,
            'data-placeholder-recusa': self.placeholder_recusa,
        })

    def clean(self):
        dados = super().clean()
        if dados.get('acao') == 'recusar' and not dados.get('resposta'):
            self.add_error('resposta', 'Explique o motivo da recusa ao interessado.')
        return dados


@supervisor_permission_required('supervisores.moderar_pet')
def lista(request):
    pedidos = SolicitacaoAdocao.objects.select_related('pet', 'usuario')
    status = request.GET.get('status', 'pendente')
    busca = request.GET.get('busca', '').strip()
    if status in SolicitacaoAdocao.Status.values:
        pedidos = pedidos.filter(status=status)
    else:
        status = ''
    if busca:
        pedidos = pedidos.filter(Q(pet__nome__icontains=busca) | Q(usuario__username__icontains=busca)
                                 | Q(usuario__email__icontains=busca))
    return render(request, 'supervisores/adocoes_lista.html', {
        'pagina_ativa': 'adocoes', 'titulo_pagina': 'Pedidos de adoção',
        'pagina': Paginator(pedidos, 20).get_page(request.GET.get('page')),
        'status_atual': status, 'status_opcoes': SolicitacaoAdocao.Status.choices, 'busca': busca,
    })


@supervisor_permission_required('supervisores.moderar_pet')
@require_http_methods(['GET', 'POST'])
def detalhe(request, pk):
    pedido = get_object_or_404(SolicitacaoAdocao.objects.select_related('pet', 'usuario'), pk=pk)
    form = DecisaoAdocaoForm(request.POST if request.method == 'POST' else None, pet=pedido.pet)
    if request.method == 'POST' and form.is_valid():
        try:
            decidir_solicitacao(
                solicitacao_id=pk, ator=request.user,
                aprovar=form.cleaned_data['acao'] == 'aprovar', resposta=form.cleaned_data['resposta'],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if form.cleaned_data['acao'] == 'aprovar':
                messages.success(request, f'Adoção de {pedido.pet.nome} aprovada! A resposta e as orientações para combinar a retirada estão em Minhas adoções do interessado.')
            else:
                messages.success(request, 'Pedido recusado. O motivo está disponível em Minhas adoções do interessado.')
            return redirect('supervisores:adocao_detalhe', pk=pk)
    return render(request, 'supervisores/adocao_detalhe.html', {
        'pagina_ativa': 'adocoes', 'titulo_pagina': f'Pedido de adoção #{pk}', 'pedido': pedido, 'form': form,
        'resposta_exibida': pedido.resposta or (form.mensagem_aprovacao if pedido.status == SolicitacaoAdocao.Status.APROVADA else ''),
    })
