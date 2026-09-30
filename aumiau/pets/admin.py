from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from supervisores.models import RegistroAtividade
from supervisores.services import registrar_atividade

from .models import FotoPet, Pet
from .admin_forms import PetAdminForm


class FotoPetInline(admin.TabularInline):
    model = FotoPet
    extra = 1

    fields = (
        'imagem',
        'legenda',
        'ordem',
    )

    ordering = (
        'ordem',
        'id',
    )


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    form = PetAdminForm

    class Media:
        js = ('js/pet-admin.js', 'js/pets.js')

    inlines = (
        FotoPetInline,
    )

    list_display = (
        'miniatura',
        'nome',
        'especie',
        'raca',
        'responsavel_ou_ong',
        'localizacao',
        'status_colorido',
        'destaque',
        'criado_em',
    )

    list_display_links = (
        'miniatura',
        'nome',
    )

    list_filter = (
        'status',
        'especie',
        'genero',
        'porte',
        'estado',
        'destaque',
        'vacinado',
        'castrado',
        'criado_em',
    )

    search_fields = (
        'nome',
        'raca',
        'cidade',
        'estado',
        'responsavel__first_name',
        'responsavel__last_name',
        'responsavel__email',
        'ong__nome',
    )

    autocomplete_fields = (
        'responsavel',
        'ong',
    )

    readonly_fields = (
        'preview_foto',
        'criado_por',
        'moderado_por',
        'moderado_em',
        'publicado_em',
        'adotado_em',
        'criado_em',
        'atualizado_em',
    )

    fieldsets = (
        (
            'Identificação do pet',
            {
                'fields': (
                    'nome',
                    'especie',
                    'raca',
                    'raca_outra',
                    'genero',
                    'porte',
                    'data_nascimento',
                    'nascimento_desconhecido',
                    'idade_anos',
                    'idade_meses',
                ),
            },
        ),
        (
            'Responsável pelo anúncio',
            {
                'fields': (
                    'responsavel',
                    'ong',
                    'email_contato',
                    'telefone_contato',
                ),
            },
        ),
        (
            'Localização',
            {
                'fields': (
                    'estado',
                    'cidade',
                ),
            },
        ),
        (
            'Descrição e imagem principal',
            {
                'fields': (
                    'descricao',
                    'foto_principal',
                    'preview_foto',
                ),
            },
        ),
        (
            'Saúde e características',
            {
                'fields': (
                    'vacinado',
                    'castrado',
                    'vermifugado',
                    'microchipado',
                    'necessidades_especiais',
                    'descricao_necessidades_especiais',
                ),
            },
        ),
        (
            'Publicação',
            {
                'fields': (
                    'status',
                    'destaque',
                    'motivo_rejeicao',
                ),
            },
        ),
        (
            'Auditoria',
            {
                'classes': ('collapse',),
                'fields': (
                    'criado_por',
                    'moderado_por',
                    'moderado_em',
                    'publicado_em',
                    'adotado_em',
                    'criado_em',
                    'atualizado_em',
                ),
            },
        ),
    )

    actions = (
        'publicar_selecionados',
        'marcar_como_adotados',
        'arquivar_selecionados',
    )

    date_hierarchy = 'criado_em'
    list_per_page = 25
    list_select_related = ('responsavel', 'ong')
    empty_value_display = '—'

    def get_urls(self):
        return [
            path(
                '<int:object_id>/publicar/',
                self.admin_site.admin_view(require_POST(self.publicar_view)),
                name='pets_pet_publicar',
            ),
            path(
                '<int:object_id>/arquivar/',
                self.admin_site.admin_view(require_POST(self.arquivar_view)),
                name='pets_pet_arquivar',
            ),
        ] + super().get_urls()

    def publicar_view(self, request, object_id):
        pet = self.get_object(request, object_id)
        if pet is None:
            raise Http404
        if not self.has_change_permission(request, pet):
            raise PermissionDenied
        self.publicar_selecionados(request, self.get_queryset(request).filter(pk=pet.pk))
        return redirect('admin:pets_pet_change', object_id=pet.pk)

    def arquivar_view(self, request, object_id):
        pet = self.get_object(request, object_id)
        if pet is None:
            raise Http404
        if not self.has_change_permission(request, pet):
            raise PermissionDenied
        quantidade = self._arquivar_pets(request, self.get_queryset(request).filter(pk=pet.pk))
        self.message_user(
            request,
            'Anúncio arquivado.' if quantidade else 'Este anúncio já está arquivado.',
            messages.SUCCESS if quantidade else messages.INFO,
        )
        return redirect('admin:pets_pet_change', object_id=pet.pk)

    def _arquivar_pets(self, request, queryset):
        agora = timezone.now()
        with transaction.atomic():
            # A lista usa joins com responsáveis opcionais; somente o pet deve
            # ser bloqueado para que o arquivamento também funcione no PostgreSQL.
            pets = list(queryset.select_related(None).select_for_update().exclude(
                status=Pet.Status.ARQUIVADO,
            ).order_by('pk'))
            for pet in pets:
                if not self.has_change_permission(request, pet):
                    raise PermissionDenied
                pet.status = Pet.Status.ARQUIVADO
                pet.moderado_por = request.user
                pet.moderado_em = agora
                pet.save(update_fields=['status', 'moderado_por', 'moderado_em', 'atualizado_em'])
                self.log_change(request, pet, 'Anúncio arquivado.')
                registrar_atividade(
                    request.user, RegistroAtividade.Acao.ARQUIVOU,
                    'pet', pet, f'Anúncio arquivado: {pet.nome}.',
                )
        return len(pets)

    @admin.display(description='Foto')
    def miniatura(self, obj):
        if not obj.foto_principal:
            return 'Sem foto'

        return format_html(
            '<img src="{}" alt="" '
            'style="width:58px;height:44px;'
            'object-fit:cover;border-radius:10px;">',
            obj.foto_principal.url,
        )

    @admin.display(description='Imagem atual')
    def preview_foto(self, obj):
        if not obj.foto_principal:
            return 'Nenhuma imagem enviada.'

        return format_html(
            '<img src="{}" alt="Foto de {}" '
            'style="width:260px;height:185px;'
            'object-fit:cover;border-radius:16px;">',
            obj.foto_principal.url,
            obj.nome,
        )

    @admin.display(description='Responsável / ONG')
    def responsavel_ou_ong(self, obj):
        if obj.ong:
            return f'ONG: {obj.ong.nome}'

        if obj.responsavel:
            return (
                obj.responsavel.get_full_name()
                or obj.responsavel.email
                or obj.responsavel.username
            )

        return 'Não informado'

    @admin.display(description='Localização', ordering='cidade')
    def localizacao(self, obj):
        return f'{obj.cidade}/{obj.estado}'

    @admin.display(description='Status', ordering='status')
    def status_colorido(self, obj):
        cores = {
            Pet.Status.RASCUNHO: ('#eeeeee', '#555555'),
            Pet.Status.PENDENTE: ('#fff2de', '#7a4b00'),
            Pet.Status.PUBLICADO: ('#e8f7ee', '#1f6b3a'),
            Pet.Status.ADOTADO: ('#f1e8ff', '#6d36b3'),
            Pet.Status.REJEITADO: ('#fdecec', '#9b1c1c'),
            Pet.Status.ARQUIVADO: ('#eeeeee', '#555555'),
        }

        fundo, texto = cores[obj.status]

        return format_html(
            '<span style="background:{};color:{};'
            'padding:5px 10px;border-radius:999px;'
            'font-weight:700;display:inline-flex;align-items:center;white-space:nowrap;line-height:1.4;">{}</span>',
            fundo,
            texto,
            obj.get_status_display(),
        )

    def save_model(self, request, obj, form, change):
        agora = timezone.now()

        if not obj.criado_por_id:
            obj.criado_por = request.user

        if not obj.responsavel_id and not obj.ong_id:
            obj.responsavel = request.user

        if obj.status != Pet.Status.PENDENTE:
            obj.moderado_por = request.user
            obj.moderado_em = agora

        if (
            obj.status == Pet.Status.PUBLICADO
            and not obj.publicado_em
        ):
            obj.publicado_em = agora

        if (
            obj.status == Pet.Status.ADOTADO
            and not obj.adotado_em
        ):
            obj.adotado_em = agora

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    @admin.action(description='Aprovar e publicar pets em análise', permissions=['change'])
    def publicar_selecionados(self, request, queryset):
        agora = timezone.now()
        quantidade = 0
        with transaction.atomic():
            for pet in queryset.select_related(None).select_for_update().filter(status=Pet.Status.PENDENTE).order_by('pk'):
                if not self.has_change_permission(request, pet):
                    raise PermissionDenied
                if pet.ong_id and pet.ong.status != 'aprovada':
                    continue
                pet.status = Pet.Status.PUBLICADO
                pet.moderado_por = request.user
                pet.moderado_em = agora
                pet.publicado_em = agora
                pet.motivo_rejeicao = ''
                pet.save(update_fields=['status', 'moderado_por', 'moderado_em', 'publicado_em',
                                        'motivo_rejeicao', 'atualizado_em'])
                self.log_change(request, pet, 'Anúncio aprovado e publicado.')
                registrar_atividade(request.user, RegistroAtividade.Acao.APROVOU,
                                   'pet', pet, f'Anúncio aprovado: {pet.nome}.')
                quantidade += 1
        self.message_user(
            request,
            f'{quantidade} pet(s) aprovado(s) e publicado(s).' if quantidade else
            'Nenhum anúncio foi publicado. O pet deve estar em análise e sua ONG, se houver, aprovada.',
            messages.SUCCESS if quantidade else messages.WARNING,
        )

    @admin.action(description='Marcar como adotados')
    def marcar_como_adotados(self, request, queryset):
        agora = timezone.now()

        quantidade = queryset.exclude(
            status=Pet.Status.ADOTADO,
        ).update(
            status=Pet.Status.ADOTADO,
            moderado_por=request.user,
            moderado_em=agora,
            adotado_em=agora,
        )

        self.message_user(
            request,
            f'{quantidade} pet(s) marcado(s) como adotado(s).',
            messages.SUCCESS,
        )

    @admin.action(description='Arquivar pets selecionados', permissions=['change'])
    def arquivar_selecionados(self, request, queryset):
        quantidade = self._arquivar_pets(request, queryset)

        self.message_user(
            request,
            f'{quantidade} pet(s) arquivado(s).',
            messages.SUCCESS,
        )
