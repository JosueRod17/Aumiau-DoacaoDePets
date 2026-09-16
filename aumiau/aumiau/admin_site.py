from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class AuMiauAdminSite(AdminSite):
    site_header = 'Administração AuMiau'
    site_title = 'AuMiau Admin'
    index_title = 'Visão geral'
    site_url = '/'

    index_template = 'admin/aumiau_index.html'

    def login(self, request, extra_context=None):
        if self.has_permission(request):
            return redirect('admin:index')

        if request.user.is_authenticated:
            return redirect('home')

        destino = (
            request.GET.get('next')
            or request.get_full_path()
        )

        parametros = urlencode({
            'next': destino,
        })

        return redirect(
            f"{reverse('home')}?{parametros}"
        )

    def index(self, request, extra_context=None):
        from ongs.models import Ong
        from pets.models import Pet

        Usuario = get_user_model()

        pet_admin = self._registry.get(Pet)
        ong_admin = self._registry.get(Ong)
        usuario_admin = self._registry.get(Usuario)

        pode_ver_pets = bool(
            pet_admin
            and pet_admin.has_view_or_change_permission(request)
        )

        pode_adicionar_pets = bool(
            pet_admin
            and pet_admin.has_add_permission(request)
        )

        pode_ver_ongs = bool(
            ong_admin
            and ong_admin.has_view_or_change_permission(request)
        )

        pode_ver_usuarios = bool(
            usuario_admin
            and usuario_admin.has_view_or_change_permission(request)
        )

        agora = timezone.now()
        ultimos_30_dias = agora - timedelta(days=30)

        contexto_dashboard = {
            'pode_ver_pets': pode_ver_pets,
            'pode_adicionar_pets': pode_adicionar_pets,
            'pode_ver_ongs': pode_ver_ongs,
            'pode_ver_usuarios': pode_ver_usuarios,

            'total_usuarios': 0,
            'novos_usuarios': 0,

            'total_pets': 0,
            'pets_publicados': 0,
            'pets_pendentes': 0,
            'pets_adotados': 0,

            'ongs_aprovadas': 0,
            'ongs_pendentes': 0,

            'grafico_status': [],
            'pets_pendentes_lista': [],
            'ultimos_pets': [],
        }

        if pode_ver_usuarios:
            usuarios_comuns = Usuario.objects.filter(
                is_staff=False,
            )

            contexto_dashboard.update({
                'total_usuarios': usuarios_comuns.count(),

                'novos_usuarios': usuarios_comuns.filter(
                    date_joined__gte=ultimos_30_dias,
                ).count(),
            })

        if pode_ver_pets:
            contagens_status = {
                item['status']: item['total']
                for item in (
                    Pet.objects
                    .values('status')
                    .annotate(total=Count('id'))
                )
            }

            total_pets = sum(contagens_status.values())

            grafico_status = []

            for valor, rotulo in Pet.Status.choices:
                quantidade = contagens_status.get(valor, 0)

                percentual = (
                    round((quantidade / total_pets) * 100)
                    if total_pets
                    else 0
                )

                grafico_status.append({
                    'valor': valor,
                    'rotulo': rotulo,
                    'quantidade': quantidade,
                    'percentual': percentual,
                })

            contexto_dashboard.update({
                'total_pets': total_pets,

                'pets_publicados': contagens_status.get(
                    Pet.Status.PUBLICADO,
                    0,
                ),

                'pets_pendentes': contagens_status.get(
                    Pet.Status.PENDENTE,
                    0,
                ),

                'pets_adotados': contagens_status.get(
                    Pet.Status.ADOTADO,
                    0,
                ),

                'grafico_status': grafico_status,

                'pets_pendentes_lista': (
                    Pet.objects
                    .filter(status=Pet.Status.PENDENTE)
                    .select_related('responsavel', 'ong')
                    .order_by('criado_em')[:5]
                ),

                'ultimos_pets': (
                    Pet.objects
                    .select_related('responsavel', 'ong')
                    .order_by('-criado_em')[:6]
                ),
            })

        if pode_ver_ongs:
            contexto_dashboard.update({
                'ongs_aprovadas': Ong.objects.filter(
                    aprovada=True,
                ).count(),

                'ongs_pendentes': Ong.objects.filter(
                    aprovada=False,
                ).count(),
            })

        contexto = dict(extra_context or {})
        contexto.update(contexto_dashboard)

        return super().index(
            request,
            extra_context=contexto,
        )