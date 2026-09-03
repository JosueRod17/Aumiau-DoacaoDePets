from django.contrib import admin

from .models import Ong

@admin.register(Ong)
class OngAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'estado', 'aprovada')
    list_filter = ('aprovada', 'estado')
    search_fields = ('nome', 'cidade', 'estado')