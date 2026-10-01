from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods

from supervisores.adocoes import DecisaoAdocaoForm
from .models import SolicitacaoAdocao
from .solicitacao_service import decidir_solicitacao


@admin.register(SolicitacaoAdocao)
class SolicitacaoAdocaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'pet', 'usuario', 'status', 'criado_em', 'analisar']
    list_filter = ['status', 'criado_em']
    list_select_related = ['pet', 'usuario']
    search_fields = ['pet__nome', 'usuario__username', 'usuario__email']
    readonly_fields = ['pet', 'usuario', 'mensagem', 'status', 'resposta', 'analisado_por',
                       'analisado_em', 'criado_em', 'atualizado_em', 'analisar']
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Análise')
    def analisar(self, obj):
        return format_html('<a href="{}">Analisar pedido</a>', reverse(
            'admin:adocoes_solicitacaoadocao_analisar', args=[obj.pk],
        ))

    def get_urls(self):
        return [path('<int:pk>/analisar/', self.admin_site.admin_view(self.analisar_view),
                     name='adocoes_solicitacaoadocao_analisar')] + super().get_urls()

    @method_decorator(require_http_methods(['GET', 'POST']))
    def analisar_view(self, request, pk):
        if not request.user.has_perm('supervisores.moderar_pet'):
            raise PermissionDenied
        pedido = get_object_or_404(SolicitacaoAdocao.objects.select_related('pet', 'usuario'), pk=pk)
        form = DecisaoAdocaoForm(request.POST if request.method == 'POST' else None, pet=pedido.pet)
        if request.method == 'POST' and form.is_valid():
            try:
                decidir_solicitacao(solicitacao_id=pk, ator=request.user,
                                   aprovar=form.cleaned_data['acao'] == 'aprovar',
                                   resposta=form.cleaned_data['resposta'])
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                self.log_change(request, pedido, 'Registrou decisão sobre o pedido de adoção.')
                feedback = (
                    f'Adoção de {pedido.pet.nome} aprovada! A resposta e as orientações para combinar a retirada estão em Minhas adoções do interessado.'
                    if form.cleaned_data['acao'] == 'aprovar' else
                    'Pedido recusado. O motivo está disponível em Minhas adoções do interessado.'
                )
                self.message_user(request, feedback, messages.SUCCESS)
                return redirect('admin:adocoes_solicitacaoadocao_analisar', pk=pk)
        return TemplateResponse(request, 'admin/adocoes/analisar.html', {
            **self.admin_site.each_context(request), 'title': f'Pedido de adoção #{pk}',
            'aumiau_admin_title': 'Pedidos de adoção', 'pedido': pedido, 'form': form,
            'resposta_exibida': pedido.resposta or (form.mensagem_aprovacao if pedido.status == SolicitacaoAdocao.Status.APROVADA else ''),
            'opts': self.model._meta,
        })
