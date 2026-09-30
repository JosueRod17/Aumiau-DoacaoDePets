from django.contrib import admin

from .models import ChamadoAjuda


@admin.register(ChamadoAjuda)
class ChamadoAjudaAdmin(admin.ModelAdmin):
    list_display = ['id', 'assunto', 'pet', 'usuario', 'categoria', 'status', 'criado_em']
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
