from django.contrib import admin

from .models import Ong

@admin.register(Ong)
class OngAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'estado', 'status', 'moderado_em')
    list_filter = ('status', 'estado')
    search_fields = ('nome', 'cidade', 'estado')
    readonly_fields = ('aprovada', 'moderado_por', 'moderado_em', 'criado_em', 'atualizado_em')
