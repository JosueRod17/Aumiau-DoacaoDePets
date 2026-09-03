from django.contrib import admin
from .models import Pet


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'especie',
        'cidade',
        'estado',
        'disponivel',
    )

    list_filter = (
        'especie',
        'disponivel',
        'estado',
    )

    search_fields = (
        'nome',
        'cidade',
        'estado',
    )