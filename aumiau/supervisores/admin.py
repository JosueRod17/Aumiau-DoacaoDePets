from django.contrib import admin

from .models import RegistroAtividade


@admin.register(RegistroAtividade)
class RegistroAtividadeAdmin(admin.ModelAdmin):
    list_display = (
        'criado_em',
        'supervisor',
        'acao',
        'entidade',
        'descricao',
    )
    list_filter = ('acao', 'entidade', 'criado_em')
    search_fields = (
        'descricao',
        'supervisor__username',
        'supervisor__email',
    )
    readonly_fields = (
        'supervisor',
        'acao',
        'entidade',
        'objeto_id',
        'descricao',
        'criado_em',
    )
    date_hierarchy = 'criado_em'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
