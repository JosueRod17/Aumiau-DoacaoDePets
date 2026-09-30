from django.contrib import admin

from .atendimento import AtendimentoChamadoForm
from .models import ChamadoAjuda
from .admin_adocoes import SolicitacaoAdocaoAdmin  # noqa: F401 — registra o modelo


@admin.register(ChamadoAjuda)
class ChamadoAjudaAdmin(admin.ModelAdmin):
    form = AtendimentoChamadoForm
    list_display = ['id', 'assunto', 'pet', 'usuario', 'categoria', 'status', 'criado_em']
    list_select_related = ['usuario', 'pet']
    list_per_page = 25
    list_filter = ['status', 'categoria', 'criado_em']
    search_fields = ['assunto', 'mensagem', 'pet__nome', 'usuario__username', 'usuario__email']
    readonly_fields = ['usuario', 'pet', 'categoria', 'assunto', 'mensagem', 'contexto_pluttu', 'criado_em', 'atualizado_em']
    fieldsets = [
        ('Mensagem recebida', {
            'fields': ['usuario', 'pet', 'categoria', 'assunto', 'mensagem', 'contexto_pluttu', 'criado_em'],
        }),
        ('Atendimento', {
            'fields': ['status', 'resposta', 'atualizado_em'],
            'description': 'A resposta fica disponível na área Meus chamados do usuário. Nenhum e-mail é enviado automaticamente.',
        }),
    ]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and form.changed_data:
            from supervisores.models import RegistroAtividade
            from supervisores.services import registrar_atividade

            registrar_atividade(
                request.user, RegistroAtividade.Acao.EDITOU, 'chamado', obj,
                f'Atualizou o chamado #{obj.pk}: {obj.get_status_display()}.',
            )
