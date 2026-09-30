from django.contrib import admin

from .models import Ong
from .forms import CadastroOngForm

@admin.register(Ong)
class OngAdmin(admin.ModelAdmin):
    form = CadastroOngForm
    list_display = ('nome', 'cidade', 'estado', 'status', 'moderado_em')
    list_filter = ('status', 'estado')
    search_fields = ('nome', 'cidade', 'estado')
    readonly_fields = ('aprovada', 'moderado_por', 'moderado_em', 'criado_em', 'atualizado_em', 'razao_social', 'cnpj_situacao', 'cnpj_consultado_em')
