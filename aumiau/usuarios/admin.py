from django.contrib import admin

from .models import ContaGoogle, DocumentoBloqueado, Perfil
from .services import alterar_situacao_usuario


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'cidade', 'estado', 'situacao', 'cpf_mascarado')
    list_filter = ('situacao', 'estado')
    search_fields = ('usuario__username', 'usuario__email', 'usuario__first_name')
    readonly_fields = ('usuario', 'cpf_mascarado', 'situacao', 'criado_em', 'atualizado_em')
    exclude = ('cpf_hash', 'cpf_final')
    actions = ('suspender', 'banir', 'reativar')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # O perfil mantém vínculo de moderação e não deve ser removido isoladamente.
        return False

    def _alterar(self, request, queryset, situacao):
        for perfil in queryset.select_related('usuario'):
            if perfil.usuario_id == request.user.pk or perfil.usuario.is_staff or perfil.usuario.is_superuser:
                continue
            try:
                alterar_situacao_usuario(perfil.usuario, situacao)
            except ValueError as erro:
                self.message_user(request, str(erro), level='error')

    @admin.action(description='Suspender contas selecionadas')
    def suspender(self, request, queryset):
        self._alterar(request, queryset, Perfil.Situacao.SUSPENSA)

    @admin.action(description='Banir contas e bloquear novos cadastros com o mesmo CPF')
    def banir(self, request, queryset):
        self._alterar(request, queryset, Perfil.Situacao.BANIDA)

    @admin.action(description='Reativar contas e retirar bloqueio do CPF')
    def reativar(self, request, queryset):
        self._alterar(request, queryset, Perfil.Situacao.ATIVA)


@admin.register(DocumentoBloqueado)
class DocumentoBloqueadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'criado_em')
    readonly_fields = ('criado_em',)
    exclude = ('cpf_hash',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ContaGoogle)
class ContaGoogleAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'criado_em')
    readonly_fields = ('usuario', 'criado_em')
    exclude = ('subject',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
