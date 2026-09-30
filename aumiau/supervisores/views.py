from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ongs.models import Ong
from pets.models import Pet
from adocoes.models import ChamadoAjuda

from .forms import (
    FotoPetSupervisorFormSet,
    OngSupervisorForm,
    PetSupervisorForm,
)
from .models import RegistroAtividade
from .permissions import (
    GRUPO_SUPERVISORES,
    supervisor_permission_required,
    supervisor_required,
    superuser_required,
)
from .services import registrar_atividade


ITENS_POR_PAGINA = 12

TRANSICOES_PET = {
    Pet.Status.PENDENTE: {'publicar', 'rejeitar', 'arquivar'},
    Pet.Status.PUBLICADO: {'adotar', 'arquivar'},
    Pet.Status.ADOTADO: {'arquivar', 'reabrir'},
    Pet.Status.REJEITADO: {'reabrir', 'arquivar'},
    Pet.Status.ARQUIVADO: {'reabrir'},
}

TRANSICOES_ONG = {
    Ong.Status.PENDENTE: {'aprovar', 'rejeitar'},
    Ong.Status.APROVADA: {'suspender'},
    Ong.Status.REJEITADA: {'reabrir'},
    Ong.Status.SUSPENSA: {'reabrir'},
}


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
    pode_ver_chamados = request.user.has_perm('adocoes.view_chamadoajuda')
    pode_ver_ongs = request.user.has_perm('ongs.view_ong')
    pode_ver_usuarios = request.user.has_perms((
        'auth.view_user',
        'usuarios.view_perfil',
    ))
    pode_ver_atividades = request.user.has_perm(
        'supervisores.view_registroatividade'
    )

    contexto = {
        'pagina_ativa': 'dashboard',
        'titulo_pagina': 'Visão geral',
        'pode_ver_pets': pode_ver_pets,
        'pode_ver_chamados': pode_ver_chamados,
        'chamados_pendentes': 0,
        'pode_ver_ongs': pode_ver_ongs,
        'pode_ver_usuarios': pode_ver_usuarios,
        'pode_ver_atividades': pode_ver_atividades,
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

    if pode_ver_chamados:
        contexto['chamados_pendentes'] = ChamadoAjuda.objects.filter(
            status__in=[ChamadoAjuda.Status.ABERTO, ChamadoAjuda.Status.EM_ANALISE],
        ).count()

    if pode_ver_ongs:
        totais_ongs = Ong.objects.aggregate(
            total=Count('pk'),
            pendentes=Count(
                'pk',
                filter=Q(status=Ong.Status.PENDENTE),
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

    contexto['atividades_recentes'] = (
        RegistroAtividade.objects.select_related('supervisor')[:6]
        if pode_ver_atividades
        else []
    )

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

    titulos_por_status = {
        Pet.Status.PENDENTE: 'Fila de moderação',
        Pet.Status.PUBLICADO: 'Pets publicados',
        Pet.Status.ADOTADO: 'Pets adotados',
        Pet.Status.REJEITADO: 'Anúncios rejeitados',
        Pet.Status.ARQUIVADO: 'Anúncios arquivados',
    }
    titulo_lista = titulos_por_status.get(status, 'Todos os pets')

    contexto = {
        'pagina_ativa': 'pets',
        'titulo_pagina': titulo_lista,
        'pets': pagina,
        'pagina': pagina,
        'intervalo_paginas': intervalo_paginas,
        'busca': busca,
        'status_atual': status,
        'status_opcoes': Pet.Status.choices,
        'total_resultados': pagina.paginator.count,
    }

    return render(
        request,
        'supervisores/pets_lista.html',
        contexto,
    )


def _salvar_formulario_pet(request, pet, criando=False):
    form = PetSupervisorForm(
        request.POST or None,
        request.FILES or None,
        instance=pet,
    )
    fotos_formset = FotoPetSupervisorFormSet(
        request.POST or None,
        request.FILES or None,
        instance=pet,
        prefix='fotos',
    )

    if (
        request.method == 'POST'
        and form.is_valid()
        and fotos_formset.is_valid()
    ):
        with transaction.atomic():
            pet = form.save(commit=False)

            if criando:
                pet.criado_por = request.user
                pet.status = Pet.Status.PENDENTE

            pet.save()
            fotos_formset.instance = pet
            fotos_formset.save()

            registrar_atividade(
                request.user,
                (
                    RegistroAtividade.Acao.CADASTROU
                    if criando
                    else RegistroAtividade.Acao.EDITOU
                ),
                'pet',
                pet,
                (
                    f'Cadastrou o pet {pet.nome}.'
                    if criando
                    else f'Atualizou os dados de {pet.nome}.'
                ),
            )

        messages.success(
            request,
            (
                'Pet cadastrado e enviado para moderação.'
                if criando
                else 'Dados do pet atualizados com sucesso.'
            ),
        )

        return redirect(
            'supervisores:pet_detalhe',
            pet_id=pet.pk,
        )

    return render(
        request,
        'supervisores/pet_form.html',
        {
            'pagina_ativa': 'pets',
            'titulo_pagina': (
                'Cadastrar pet'
                if criando
                else f'Editar {pet.nome}'
            ),
            'form': form,
            'fotos_formset': fotos_formset,
            'pet': None if criando else pet,
            'criando': criando,
        },
    )


@supervisor_permission_required('pets.add_pet')
def pet_criar(request):
    return _salvar_formulario_pet(
        request,
        Pet(),
        criando=True,
    )


@supervisor_permission_required('pets.change_pet')
def pet_editar(request, pet_id):
    pet = get_object_or_404(Pet, pk=pet_id)
    return _salvar_formulario_pet(request, pet)


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
            'pagina_ativa': 'pets',
            'titulo_pagina': f'Análise de {pet.nome}',
            'pet': pet,
            'pode_moderar': request.user.has_perm(
                'supervisores.moderar_pet'
            ),
            'pode_editar': request.user.has_perm(
                'pets.change_pet'
            ),
            'acoes_disponiveis': TRANSICOES_PET.get(
                pet.status,
                set(),
            ),
        },
    )


@require_POST
@supervisor_permission_required('supervisores.moderar_pet')
def moderar_pet(request, pet_id, acao):
    acoes_permitidas = {
        'publicar': Pet.Status.PUBLICADO,
        'rejeitar': Pet.Status.REJEITADO,
        'adotar': Pet.Status.ADOTADO,
        'arquivar': Pet.Status.ARQUIVADO,
        'reabrir': Pet.Status.PENDENTE,
    }

    novo_status = acoes_permitidas.get(acao)

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

    mensagens = {
        'publicar': 'Anúncio publicado com sucesso.',
        'rejeitar': 'Anúncio rejeitado.',
        'adotar': 'Pet marcado como adotado.',
        'arquivar': 'Anúncio arquivado.',
        'reabrir': 'Anúncio enviado novamente para análise.',
    }

    with transaction.atomic():
        pet = get_object_or_404(
            # PostgreSQL não permite FOR UPDATE sobre o lado opcional do JOIN.
            # A moderação bloqueia somente o pet; a ONG é consultada se houver.
            Pet.objects.select_for_update(),
            pk=pet_id,
        )

        if (
            not novo_status
            or acao not in TRANSICOES_PET.get(pet.status, set())
        ):
            messages.error(
                request,
                'Essa mudança de status não é permitida.',
            )
            return redirect(
                'supervisores:pet_detalhe',
                pet_id=pet_id,
            )

        if (
            novo_status == Pet.Status.PUBLICADO
            and pet.ong_id
            and pet.ong.status != Ong.Status.APROVADA
        ):
            messages.error(
                request,
                'A ONG responsável precisa estar aprovada antes da publicação.',
            )
            return redirect(
                'supervisores:pet_detalhe',
                pet_id=pet_id,
            )

        pet.status = novo_status
        pet.moderado_por = request.user
        pet.moderado_em = agora

        campos_atualizados = {
            'status',
            'moderado_por',
            'moderado_em',
            'atualizado_em',
        }

        if novo_status == Pet.Status.PUBLICADO:
            pet.publicado_em = agora
            pet.adotado_em = None
            pet.motivo_rejeicao = ''
            campos_atualizados.update({
                'publicado_em',
                'adotado_em',
                'motivo_rejeicao',
            })

        if novo_status == Pet.Status.ADOTADO:
            pet.adotado_em = agora
            pet.motivo_rejeicao = ''
            campos_atualizados.update({
                'adotado_em',
                'motivo_rejeicao',
            })

        if novo_status == Pet.Status.REJEITADO:
            pet.motivo_rejeicao = motivo_rejeicao
            pet.publicado_em = None
            pet.adotado_em = None
            campos_atualizados.update({
                'motivo_rejeicao',
                'publicado_em',
                'adotado_em',
            })

        if novo_status == Pet.Status.PENDENTE:
            pet.motivo_rejeicao = ''
            pet.publicado_em = None
            pet.adotado_em = None
            campos_atualizados.update({
                'motivo_rejeicao',
                'publicado_em',
                'adotado_em',
            })

        pet.save(update_fields=list(campos_atualizados))

        acoes_registro = {
            'publicar': RegistroAtividade.Acao.PUBLICOU,
            'rejeitar': RegistroAtividade.Acao.REJEITOU,
            'adotar': RegistroAtividade.Acao.ADOTOU,
            'arquivar': RegistroAtividade.Acao.ARQUIVOU,
            'reabrir': RegistroAtividade.Acao.REABRIU,
        }

        registrar_atividade(
            request.user,
            acoes_registro[acao],
            'pet',
            pet,
            f'{mensagens[acao][:-1]}: {pet.nome}.',
        )

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

    filtros_status = {
        'aprovadas': Ong.Status.APROVADA,
        'pendentes': Ong.Status.PENDENTE,
        'rejeitadas': Ong.Status.REJEITADA,
        'suspensas': Ong.Status.SUSPENSA,
    }

    if situacao in filtros_status:
        ongs = ongs.filter(status=filtros_status[situacao])
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
                'supervisores.moderar_ong'
            ),
            'pode_adicionar_ong': request.user.has_perm(
                'ongs.add_ong'
            ),
        },
    )


def _salvar_formulario_ong(request, ong, criando=False):
    form = OngSupervisorForm(
        request.POST or None,
        request.FILES or None,
        instance=ong,
    )

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            ong = form.save()

            registrar_atividade(
                request.user,
                (
                    RegistroAtividade.Acao.CADASTROU
                    if criando
                    else RegistroAtividade.Acao.EDITOU
                ),
                'ong',
                ong,
                (
                    f'Cadastrou a ONG {ong.nome}.'
                    if criando
                    else f'Atualizou os dados da ONG {ong.nome}.'
                ),
            )

        messages.success(
            request,
            (
                'ONG cadastrada e enviada para análise.'
                if criando
                else 'Dados da ONG atualizados com sucesso.'
            ),
        )

        return redirect(
            'supervisores:ong_detalhe',
            ong_id=ong.pk,
        )

    return render(
        request,
        'supervisores/ong_form.html',
        {
            'pagina_ativa': 'ongs',
            'titulo_pagina': (
                'Cadastrar ONG'
                if criando
                else f'Editar {ong.nome}'
            ),
            'form': form,
            'ong': None if criando else ong,
            'criando': criando,
        },
    )


@supervisor_permission_required('ongs.add_ong')
def ong_criar(request):
    return _salvar_formulario_ong(
        request,
        Ong(),
        criando=True,
    )


@supervisor_permission_required('ongs.change_ong')
def ong_editar(request, ong_id):
    ong = get_object_or_404(Ong, pk=ong_id)
    return _salvar_formulario_ong(request, ong)


@supervisor_permission_required('ongs.view_ong')
def ong_detalhe(request, ong_id):
    ong = get_object_or_404(
        Ong.objects
        .select_related('moderado_por')
        .annotate(total_pets=Count('pets')),
        pk=ong_id,
    )

    pets = (
        ong.pets
        .select_related('responsavel')
        .order_by('-criado_em')[:8]
    )

    return render(
        request,
        'supervisores/ong_detalhe.html',
        {
            'pagina_ativa': 'ongs',
            'titulo_pagina': ong.nome,
            'ong': ong,
            'pets': pets,
            'pode_editar': request.user.has_perm('ongs.change_ong'),
            'pode_moderar': request.user.has_perm(
                'supervisores.moderar_ong'
            ),
            'acoes_disponiveis': TRANSICOES_ONG.get(
                ong.status,
                set(),
            ),
        },
    )


@require_POST
@supervisor_permission_required('supervisores.moderar_ong')
def moderar_ong(request, ong_id, acao):
    novos_status = {
        'aprovar': Ong.Status.APROVADA,
        'rejeitar': Ong.Status.REJEITADA,
        'suspender': Ong.Status.SUSPENSA,
        'reabrir': Ong.Status.PENDENTE,
    }
    motivo = request.POST.get('motivo', '').strip()

    with transaction.atomic():
        ong = get_object_or_404(
            Ong.objects.select_for_update(),
            pk=ong_id,
        )

        if (
            acao not in novos_status
            or acao not in TRANSICOES_ONG.get(ong.status, set())
        ):
            messages.error(
                request,
                'Essa mudança de situação não é permitida.',
            )
            return redirect(
                'supervisores:ong_detalhe',
                ong_id=ong.pk,
            )

        if acao in {'rejeitar', 'suspender'} and not motivo:
            messages.error(
                request,
                'Informe o motivo antes de continuar.',
            )
            return redirect(
                'supervisores:ong_detalhe',
                ong_id=ong.pk,
            )

        if acao == 'aprovar' and ong.cnpj_requer_conferencia:
            if request.POST.get('confirmar_cnpj') != '1':
                messages.error(request, 'Confira o comprovante do CNPJ e confirme a conferência antes de aprovar.')
                return redirect('supervisores:ong_detalhe', ong_id=ong.pk)
            ong.cnpj_confirmado_manualmente = True

        ong.status = novos_status[acao]
        ong.motivo_rejeicao = (
            motivo if acao in {'rejeitar', 'suspender'} else ''
        )
        ong.moderado_por = request.user
        ong.moderado_em = timezone.now()
        ong.save(update_fields=[
            'status',
            'aprovada',
            'cnpj_confirmado_manualmente',
            'motivo_rejeicao',
            'moderado_por',
            'moderado_em',
            'atualizado_em',
        ])

        pets_arquivados = 0

        if acao == 'suspender':
            pets_arquivados = ong.pets.filter(
                status=Pet.Status.PUBLICADO,
            ).update(
                status=Pet.Status.ARQUIVADO,
                moderado_por=request.user,
                moderado_em=ong.moderado_em,
                atualizado_em=ong.moderado_em,
            )

        acoes_registro = {
            'aprovar': RegistroAtividade.Acao.APROVOU,
            'rejeitar': RegistroAtividade.Acao.REJEITOU,
            'suspender': RegistroAtividade.Acao.ARQUIVOU,
            'reabrir': RegistroAtividade.Acao.REABRIU,
        }

        registrar_atividade(
            request.user,
            acoes_registro[acao],
            'ong',
            ong,
            f'{ong.get_status_display()}: ONG {ong.nome}.',
        )

    mensagens_ong = {
        'aprovar': f'A ONG {ong.nome} foi aprovada.',
        'rejeitar': f'O cadastro de {ong.nome} foi rejeitado.',
        'suspender': (
            f'A ONG {ong.nome} foi suspensa. '
            f'{pets_arquivados} anúncio(s) publicado(s) foram arquivados.'
        ),
        'reabrir': f'A ONG {ong.nome} voltou para análise.',
    }

    messages.success(request, mensagens_ong[acao])

    return redirect(
        'supervisores:ong_detalhe',
        ong_id=ong.pk,
    )


@supervisor_permission_required(
    'auth.view_user',
    'usuarios.view_perfil',
)
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


@supervisor_permission_required(
    'auth.view_user',
    'usuarios.view_perfil',
)
def usuario_detalhe(request, usuario_id):
    usuario = get_object_or_404(
        _usuarios_comuns().select_related('perfil'),
        pk=usuario_id,
    )

    pets = (
        usuario.pets_sob_responsabilidade
        .select_related('ong')
        .order_by('-criado_em')[:8]
    )

    return render(
        request,
        'supervisores/usuario_detalhe.html',
        {
            'pagina_ativa': 'usuarios',
            'titulo_pagina': 'Detalhes do usuário',
            'usuario_detalhe': usuario,
            'pets': pets,
            'total_pets_usuario': (
                usuario.pets_sob_responsabilidade.count()
            ),
            'pode_gerenciar': request.user.has_perm(
                'supervisores.gerenciar_usuarios'
            ),
        },
    )


@require_POST
@supervisor_permission_required('supervisores.gerenciar_usuarios')
def alterar_status_usuario(request, usuario_id, acao):
    from usuarios.models import Perfil
    from usuarios.services import alterar_situacao_usuario
    situacoes = {'ativar': Perfil.Situacao.ATIVA, 'inativar': Perfil.Situacao.SUSPENSA,
                 'suspender': Perfil.Situacao.SUSPENSA, 'banir': Perfil.Situacao.BANIDA}
    destino = 'supervisores:usuario_detalhe'
    if acao not in situacoes:
        messages.error(request, 'Ação de usuário inválida.')
        return redirect(destino, usuario_id=usuario_id)
    motivo = request.POST.get('motivo', '').strip()
    if not motivo:
        messages.error(request, 'Informe o motivo da alteração da conta.')
        return redirect(destino, usuario_id=usuario_id)
    with transaction.atomic():
        usuario = get_object_or_404(_usuarios_comuns().select_for_update(), pk=usuario_id)
        if usuario.pk == request.user.pk:
            messages.error(request, 'Você não pode alterar o estado da própria conta.')
            return redirect(destino, usuario_id=usuario_id)
        perfil = getattr(usuario, 'perfil', None)
        atual = perfil.situacao if perfil else (Perfil.Situacao.ATIVA if usuario.is_active else Perfil.Situacao.SUSPENSA)
        if atual == situacoes[acao]:
            messages.info(request, 'A conta já está com a situação solicitada.')
            return redirect(destino, usuario_id=usuario_id)
        try:
            usuario = alterar_situacao_usuario(usuario, situacoes[acao])
        except ValueError as erro:
            messages.error(request, str(erro))
            return redirect(destino, usuario_id=usuario_id)
        verbo = {'ativar': 'Reativou', 'inativar': 'Suspendeu', 'suspender': 'Suspendeu', 'banir': 'Baniu'}[acao]
        registrar_atividade(
            request.user,
            RegistroAtividade.Acao.ATIVOU if usuario.is_active else RegistroAtividade.Acao.DESATIVOU,
            'usuario', usuario, f'{verbo} a conta {usuario.get_username()}. Motivo: {motivo}',
        )
    messages.success(request, {'ativar': 'Conta reativada com sucesso.', 'inativar': 'Conta suspensa com sucesso.',
                              'suspender': 'Conta suspensa com sucesso.', 'banir': 'Conta banida. Novos cadastros com o mesmo CPF serão bloqueados.'}[acao])
    return redirect(destino, usuario_id=usuario_id)


@supervisor_permission_required('supervisores.view_registroatividade')
def atividades_lista(request):
    busca = request.GET.get('busca', '').strip()
    acao = request.GET.get('acao', '').strip()

    atividades = (
        RegistroAtividade.objects
        .select_related('supervisor')
    )

    acoes_validas = {
        valor for valor, _ in RegistroAtividade.Acao.choices
    }

    if acao in acoes_validas:
        atividades = atividades.filter(acao=acao)
    else:
        acao = ''

    if busca:
        atividades = atividades.filter(
            Q(descricao__icontains=busca)
            | Q(supervisor__first_name__icontains=busca)
            | Q(supervisor__last_name__icontains=busca)
            | Q(supervisor__username__icontains=busca)
        )

    pagina, intervalo_paginas = _paginacao(
        request,
        atividades,
    )

    return render(
        request,
        'supervisores/atividades_lista.html',
        {
            'pagina_ativa': 'atividades',
            'titulo_pagina': 'Histórico de atividades',
            'atividades': pagina,
            'pagina': pagina,
            'intervalo_paginas': intervalo_paginas,
            'busca': busca,
            'acao_atual': acao,
            'acoes_opcoes': RegistroAtividade.Acao.choices,
            'total_resultados': pagina.paginator.count,
        },
    )


@superuser_required
def equipe_lista(request):
    busca = request.GET.get('busca', '').strip()
    usuarios = (
        get_user_model().objects
        .filter(is_superuser=False)
        .annotate(
            total_grupos_supervisor=Count(
                'groups',
                filter=Q(groups__name=GRUPO_SUPERVISORES),
            )
        )
        .order_by('first_name', 'last_name', 'username')
    )

    if busca:
        usuarios = usuarios.filter(
            Q(first_name__icontains=busca)
            | Q(last_name__icontains=busca)
            | Q(username__icontains=busca)
            | Q(email__icontains=busca)
        )

    pagina, intervalo_paginas = _paginacao(request, usuarios)

    return render(
        request,
        'supervisores/equipe_lista.html',
        {
            'pagina_ativa': 'equipe',
            'titulo_pagina': 'Equipe de supervisão',
            'usuarios_equipe': pagina,
            'pagina': pagina,
            'intervalo_paginas': intervalo_paginas,
            'busca': busca,
            'total_resultados': pagina.paginator.count,
        },
    )


@require_POST
@superuser_required
def alterar_supervisor(request, usuario_id, acao):
    if acao not in {'promover', 'remover'}:
        messages.error(request, 'Ação de equipe inválida.')
        return redirect('supervisores:equipe_lista')

    with transaction.atomic():
        usuario = get_object_or_404(
            get_user_model().objects
            .select_for_update()
            .filter(is_superuser=False),
            pk=usuario_id,
        )
        grupo, _ = Group.objects.get_or_create(
            name=GRUPO_SUPERVISORES,
        )
        possui_acesso = usuario.groups.filter(pk=grupo.pk).exists()

        if (
            (acao == 'promover' and possui_acesso)
            or (acao == 'remover' and not possui_acesso)
        ):
            messages.info(
                request,
                'O acesso dessa conta já está atualizado.',
            )
            return redirect('supervisores:equipe_lista')

        if acao == 'promover':
            usuario.groups.add(grupo)

            if usuario.is_staff:
                usuario.is_staff = False
                usuario.save(update_fields=['is_staff'])

            atividade = RegistroAtividade.Acao.PROMOVEU
            mensagem = f'{usuario.get_username()} agora é supervisor.'
        else:
            usuario.groups.remove(grupo)
            atividade = RegistroAtividade.Acao.REMOVEU_ACESSO
            mensagem = f'O acesso de {usuario.get_username()} foi removido.'

        registrar_atividade(
            request.user,
            atividade,
            'usuario',
            usuario,
            mensagem,
        )
    messages.success(request, mensagem)

    return redirect('supervisores:equipe_lista')
