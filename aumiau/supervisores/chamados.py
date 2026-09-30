from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from adocoes.atendimento import AtendimentoChamadoForm
from adocoes.models import ChamadoAjuda

from .models import RegistroAtividade
from .permissions import supervisor_permission_required
from .services import registrar_atividade
from .views import _paginacao


@supervisor_permission_required('adocoes.view_chamadoajuda')
def chamados_lista(request):
    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    chamados = ChamadoAjuda.objects.select_related('usuario', 'pet')
    if status == 'pendentes':
        chamados = chamados.filter(status__in=[
            ChamadoAjuda.Status.ABERTO, ChamadoAjuda.Status.EM_ANALISE,
        ])
    elif status in ChamadoAjuda.Status.values:
        chamados = chamados.filter(status=status)
    else:
        status = ''
    if busca:
        filtro = (
            Q(assunto__icontains=busca) | Q(mensagem__icontains=busca)
            | Q(usuario__username__icontains=busca) | Q(usuario__email__icontains=busca)
            | Q(usuario__first_name__icontains=busca) | Q(pet__nome__icontains=busca)
        )
        if busca.isascii() and busca.isdigit() and len(busca) <= 18:
            filtro |= Q(pk=int(busca))
        chamados = chamados.filter(filtro)
    pagina, intervalo = _paginacao(request, chamados)
    return render(request, 'supervisores/chamados_lista.html', {
        'pagina_ativa': 'chamados',
        'titulo_pagina': 'Chamados de ajuda',
        'chamados': pagina,
        'pagina': pagina,
        'intervalo_paginas': intervalo,
        'total_resultados': pagina.paginator.count,
        'busca': busca,
        'status_atual': status,
        'status_opcoes': ChamadoAjuda.Status.choices,
    })


@require_http_methods(['GET', 'POST'])
@supervisor_permission_required('adocoes.view_chamadoajuda')
def chamado_detalhe(request, chamado_id):
    pode_responder = request.user.has_perm('adocoes.change_chamadoajuda')
    if request.method == 'POST' and not pode_responder:
        raise PermissionDenied

    with transaction.atomic():
        queryset = ChamadoAjuda.objects.select_related('usuario', 'pet')
        if request.method == 'POST':
            # Bloqueia apenas o chamado; pet é opcional e não deve integrar o lock.
            queryset = queryset.select_for_update(of=('self',))
        chamado = get_object_or_404(queryset, pk=chamado_id)
        form = AtendimentoChamadoForm(
            request.POST if request.method == 'POST' else None, instance=chamado,
        )
        for field in form.fields.values():
            field.widget.attrs['class'] = 'supervisor-form__controle'
        if request.method == 'POST' and form.is_valid():
            if form.has_changed():
                chamado = form.save()
                registrar_atividade(
                    request.user, RegistroAtividade.Acao.EDITOU, 'chamado', chamado,
                    f'Atualizou o chamado #{chamado.pk}: {chamado.get_status_display()}.',
                )
            messages.success(request, 'Atendimento salvo. O usuário pode acompanhar em Meus chamados.')
            return redirect('supervisores:chamado_detalhe', chamado_id=chamado.pk)

    return render(request, 'supervisores/chamado_detalhe.html', {
        'pagina_ativa': 'chamados',
        'titulo_pagina': f'Chamado #{chamado.pk}',
        'chamado': chamado,
        'form': form,
        'pode_responder': pode_responder,
    })
