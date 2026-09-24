from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ongs.models import Ong
from pets.models import Pet

from .permissions import (
    GRUPO_SUPERVISORES,
    supervisor_permission_required,
    supervisor_required,
)


ITENS_POR_PAGINA = 12


def _usuarios_comuns():
    Usuario = get_user_model()

    return (
        Usuario.objects
        .filter(is_superuser=False)
        .exclude(groups__name=GRUPO_SUPERVISORES)
        .distinct()
    )


def _paginacao(request, queryset):
    paginador = Paginator(queryset, ITENS_POR_PAGINA)
    pagina = paginador.get_page(request.GET.get('pagina'))

    return pagina, paginador.get_elided_page_range(
        pagina.number,
        on_each_side=1,
        on_ends=1,
    )


@supervisor_required
def dashboard(request):
    agora = timezone.now()
    ultimos_30_dias = agora - timedelta(days=30)

    pode_ver_pets = request.user.has_perm('pets.view_pet')
    pode_ver_ongs = request.user.has_perm('ongs.view_ong')
    pode_ver_usuarios = request.user.has_perm('auth.view_user')

    contexto = {
        'pagina_ativa': 'dashboard',
        'titulo_pagina': 'Visão geral',
        'pode_ver_pets': pode_ver_pets,
        'pode_ver_ongs': pode_ver_ongs,
        'pode_ver_usuarios': pode_ver_usuarios,
        'total_pets': 0,
        'pets_pendentes': 0,
        'pets_publicados': 0,
        'pets_adotados': 0,
        'adotados_30_dias': 0,
        'total_ongs': 0,
        'ongs_pendentes': 0,
        'total_usuarios': 0,
        'novos_usuarios': 0,
        'grafico_status': [],
        'fila_moderacao': [],
        'ultimos_pets': [],
    }

    if pode_ver_pets:
        totais_pets = Pet.objects.aggregate(
            total=Count('pk'),
            pendentes=Count(
                'pk',
                filter=Q(status=Pet.Status.PENDENTE),
            ),
            publicados=Count(
                'pk',
                filter=Q(status=Pet.Status.PUBLICADO),
            ),
            adotados=Count(
                'pk',
                filter=Q(status=Pet.Status.ADOTADO),
            ),
            adotados_30_dias=Count(
                'pk',
                filter=Q(
                    status=Pet.Status.ADOTADO,
                    adotado_em__gte=ultimos_30_dias,
                ),
            ),
        )

        contagens_status = {
            item['status']: item['total']
            for item in (
                Pet.objects
                .values('status')
                .annotate(total=Count('pk'))
            )
        }

        total_pets = totais_pets['total'] or 0
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

        contexto.update({
            'total_pets': total_pets,
            'pets_pendentes': totais_pets['pendentes'] or 0,
            'pets_publicados': totais_pets['publicados'] or 0,
            'pets_adotados': totais_pets['adotados'] or 0,
            'adotados_30_dias': (
                totais_pets['adotados_30_dias'] or 0
            ),
            'grafico_status': grafico_status,
            'fila_moderacao': (
                Pet.objects
                .filter(status=Pet.Status.PENDENTE)
                .select_related('responsavel', 'ong')
                .order_by('criado_em', 'pk')[:6]
            ),
            'ultimos_pets': (
                Pet.objects
                .select_related('responsavel', 'ong')
                .order_by('-criado_em')[:6]
            ),
        })

    if pode_ver_ongs:
        totais_ongs = Ong.objects.aggregate(
            total=Count('pk'),
            pendentes=Count(
                'pk',
                filter=Q(aprovada=False),
            ),
        )

        contexto.update({
            'total_ongs': totais_ongs['total'] or 0,
            'ongs_pendentes': totais_ongs['pendentes'] or 0,
        })

    if pode_ver_usuarios:
        usuarios = _usuarios_comuns()

        contexto.update({
            'total_usuarios': usuarios.count(),
            'novos_usuarios': usuarios.filter(
                date_joined__gte=ultimos_30_dias,
            ).count(),
        })

    return render(
        request,
        'supervisores/dashboard.html',
        contexto,
    )


@supervisor_permission_required('pets.view_pet')
def pets_lista(request):
    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()

    pets = (
        Pet.objects
        .select_related('responsavel', 'ong', 'moderado_por')
        .order_by('-criado_em')
    )

    status_validos = {valor for valor, _ in Pet.Status.choices}

    if status in status_validos:
        pets = pets.filter(status=status)
    else:
        status = ''

    if busca:
        pets = pets.filter(
            Q(nome__icontains=busca)
            | Q(raca__icontains=busca)
            | Q(cidade__icontains=busca)
            | Q(estado__iexact=busca)
            | Q(responsavel__first_name__icontains=busca)
            | Q(responsavel__last_name__icontains=busca)
            | Q(responsavel__email__icontains=busca)
            | Q(ong__nome__icontains=busca)
        ).distinct()

    pagina, intervalo_paginas = _paginacao(
        request,
        pets,
    )

    contexto = {
        'pagina_ativa': (
            'moderacao'
            if status == Pet.Status.PENDENTE
            else 'pets'
        ),
        'titulo_pagina': 'Moderação de pets',
        'pets': pagina,
        'pagina': pagina,
        'intervalo_paginas': intervalo_paginas,
        'busca': busca,
        'status_atual': status,
        'status_opcoes': Pet.Status.choices,
        'total_resultados': pagina.paginator.count,
    }

    contexto['titulo_pagina'] = (
        'Fila de moderação'
        if status == Pet.Status.PENDENTE
        else 'Pets cadastrados'
    )

    return render(
        request,
        'supervisores/pets_lista.html',
        contexto,
    )


@supervisor_permission_required('pets.view_pet')
def pet_detalhe(request, pet_id):
    pet = get_object_or_404(
        Pet.objects
        .select_related(
            'responsavel',
            'ong',
            'criado_por',
            'moderado_por',
        )
        .prefetch_related('fotos'),
        pk=pet_id,
    )

    return render(
        request,
        'supervisores/pet_detalhe.html',
        {
            'pagina_ativa': (
                'moderacao'
                if pet.status == Pet.Status.PENDENTE
                else 'pets'
            ),
            'titulo_pagina': f'Análise de {pet.nome}',
            'pet': pet,
            'pode_moderar': request.user.has_perm(
                'pets.change_pet'
            ),
        },
    )


@require_POST
@supervisor_permission_required('pets.change_pet')
def moderar_pet(request, pet_id, acao):
    acoes_permitidas = {
        'publicar': Pet.Status.PUBLICADO,
        'rejeitar': Pet.Status.REJEITADO,
        'adotar': Pet.Status.ADOTADO,
        'arquivar': Pet.Status.ARQUIVADO,
        'reabrir': Pet.Status.PENDENTE,
    }

    novo_status = acoes_permitidas.get(acao)

    if not novo_status:
        messages.error(request, 'Ação de moderação inválida.')
        return redirect(
            'supervisores:pet_detalhe',
            pet_id=pet_id,
        )

    motivo_rejeicao = request.POST.get(
        'motivo_rejeicao',
        '',
    ).strip()

    if (
        novo_status == Pet.Status.REJEITADO
        and not motivo_rejeicao
    ):
        messages.error(
            request,
            'Informe o motivo antes de rejeitar o anúncio.',
        )

        return redirect(
            'supervisores:pet_detalhe',
            pet_id=pet_id,
        )

    agora = timezone.now()

    with transaction.atomic():
        pet = get_object_or_404(
            Pet.objects.select_for_update(),
            pk=pet_id,
        )

        pet.status = novo_status
        pet.moderado_por = request.user
        pet.moderado_em = agora

        campos_atualizados = [
            'status',
            'moderado_por',
            'moderado_em',
            'atualizado_em',
        ]

        if novo_status == Pet.Status.PUBLICADO:
            pet.publicado_em = agora
            pet.motivo_rejeicao = ''
            campos_atualizados.extend([
                'publicado_em',
                'motivo_rejeicao',
            ])

        if novo_status == Pet.Status.ADOTADO:
            pet.adotado_em = agora
            campos_atualizados.append('adotado_em')

        if novo_status == Pet.Status.REJEITADO:
            pet.motivo_rejeicao = motivo_rejeicao
            campos_atualizados.append('motivo_rejeicao')

        if novo_status == Pet.Status.PENDENTE:
            pet.motivo_rejeicao = ''
            campos_atualizados.append('motivo_rejeicao')

        pet.save(update_fields=campos_atualizados)

    mensagens = {
        'publicar': 'Anúncio publicado com sucesso.',
        'rejeitar': 'Anúncio rejeitado.',
        'adotar': 'Pet marcado como adotado.',
        'arquivar': 'Anúncio arquivado.',
        'reabrir': 'Anúncio enviado novamente para análise.',
    }

    messages.success(request, mensagens[acao])

    return redirect(
        'supervisores:pet_detalhe',
        pet_id=pet_id,
    )


@supervisor_permission_required('ongs.view_ong')
def ongs_lista(request):
    busca = request.GET.get('busca', '').strip()
    situacao = request.GET.get('situacao', '').strip()

    ongs = (
        Ong.objects
        .annotate(total_pets=Count('pets'))
        .order_by('-criado_em')
    )

    if situacao == 'aprovadas':
        ongs = ongs.filter(aprovada=True)
    elif situacao == 'pendentes':
        ongs = ongs.filter(aprovada=False)
    else:
        situacao = ''

    if busca:
        ongs = ongs.filter(
            Q(nome__icontains=busca)
            | Q(cidade__icontains=busca)
            | Q(estado__iexact=busca)
        )

    pagina, intervalo_paginas = _paginacao(
        request,
        ongs,
    )

    return render(
        request,
        'supervisores/ongs_lista.html',
        {
            'pagina_ativa': 'ongs',
            'titulo_pagina': 'ONGs parceiras',
            'ongs': pagina,
            'pagina': pagina,
            'intervalo_paginas': intervalo_paginas,
            'busca': busca,
            'situacao_atual': situacao,
            'total_resultados': pagina.paginator.count,
            'pode_moderar_ongs': request.user.has_perm(
                'ongs.change_ong'
            ),
        },
    )


@require_POST
@supervisor_permission_required('ongs.change_ong')
def moderar_ong(request, ong_id, acao):
    if acao not in {'aprovar', 'reabrir'}:
        messages.error(request, 'Ação de moderação inválida.')
        return redirect('supervisores:ongs_lista')

    ong = get_object_or_404(Ong, pk=ong_id)
    ong.aprovada = acao == 'aprovar'
    ong.save(update_fields=['aprovada'])

    if ong.aprovada:
        messages.success(
            request,
            f'A ONG {ong.nome} foi aprovada.',
        )
    else:
        messages.success(
            request,
            f'A ONG {ong.nome} voltou para análise.',
        )

    return redirect('supervisores:ongs_lista')


@supervisor_permission_required('auth.view_user')
def usuarios_lista(request):
    busca = request.GET.get('busca', '').strip()
    situacao = request.GET.get('situacao', '').strip()

    usuarios = _usuarios_comuns().select_related('perfil')

    if situacao == 'ativos':
        usuarios = usuarios.filter(is_active=True)
    elif situacao == 'inativos':
        usuarios = usuarios.filter(is_active=False)
    else:
        situacao = ''

    if busca:
        usuarios = usuarios.filter(
            Q(first_name__icontains=busca)
            | Q(last_name__icontains=busca)
            | Q(username__icontains=busca)
            | Q(email__icontains=busca)
            | Q(perfil__cidade__icontains=busca)
            | Q(perfil__estado__iexact=busca)
        ).distinct()

    usuarios = usuarios.order_by('-date_joined')

    pagina, intervalo_paginas = _paginacao(
        request,
        usuarios,
    )

    return render(
        request,
        'supervisores/usuarios_lista.html',
        {
            'pagina_ativa': 'usuarios',
            'titulo_pagina': 'Usuários cadastrados',
            'usuarios': pagina,
            'pagina': pagina,
            'intervalo_paginas': intervalo_paginas,
            'busca': busca,
            'situacao_atual': situacao,
            'total_resultados': pagina.paginator.count,
        },
    )
