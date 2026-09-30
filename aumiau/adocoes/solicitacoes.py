from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from pets.models import Pet
from usuarios.models import Perfil
from .models import SolicitacaoAdocao


class SolicitarAdocaoForm(forms.Form):
    mensagem = forms.CharField(
        label='Conte por que você quer adotar e como será o novo lar',
        max_length=5000, widget=forms.Textarea(attrs={'rows': 6, 'class': 'ajuda-input'}),
    )


@login_required
@require_http_methods(['GET', 'POST'])
def solicitar(request, pet_id):
    perfil = getattr(request.user, 'perfil', None)
    if not request.user.is_active or (perfil and perfil.situacao != Perfil.Situacao.ATIVA):
        raise PermissionDenied
    pet = get_object_or_404(Pet.objects.publicos(), pk=pet_id)
    if Pet.objects.gerenciaveis_por(request.user).filter(pk=pet_id).exists():
        raise PermissionDenied('Você não pode solicitar a adoção do próprio anúncio.')
    existente = SolicitacaoAdocao.objects.filter(
        usuario=request.user, pet=pet, status=SolicitacaoAdocao.Status.PENDENTE,
    ).first()
    if existente:
        return redirect('adocao_detalhe', pk=existente.pk)
    form = SolicitarAdocaoForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Mesmo lock usado pela aprovação; um pedido não entra após a adoção.
            pet = get_object_or_404(Pet.objects.select_for_update(), pk=pet_id)
            if not Pet.objects.publicos().filter(pk=pet_id).exists():
                form.add_error(None, 'Este pet não está mais disponível para adoção.')
            elif Pet.objects.gerenciaveis_por(request.user).filter(pk=pet_id).exists():
                raise PermissionDenied
            else:
                solicitacao, _ = SolicitacaoAdocao.objects.get_or_create(
                    usuario=request.user, pet=pet, status=SolicitacaoAdocao.Status.PENDENTE,
                    defaults={'mensagem': form.cleaned_data['mensagem']},
                )
                messages.success(request, 'Pedido enviado! Acompanhe a análise em Minhas adoções.')
                return redirect('adocao_detalhe', pk=solicitacao.pk)
    return render(request, 'adocoes/solicitar.html', {'pet': pet, 'form': form})


@login_required
def minhas_adocoes(request):
    pedidos = SolicitacaoAdocao.objects.filter(usuario=request.user).select_related('pet')
    return render(request, 'adocoes/minhas_adocoes.html', {
        'pagina': Paginator(pedidos, 12).get_page(request.GET.get('page')),
    })


@login_required
def detalhe(request, pk):
    pedido = get_object_or_404(
        SolicitacaoAdocao.objects.select_related('pet'), pk=pk, usuario=request.user,
    )
    return render(request, 'adocoes/detalhe.html', {'pedido': pedido})


@login_required
@require_POST
def cancelar(request, pk):
    pedido = get_object_or_404(SolicitacaoAdocao, pk=pk, usuario=request.user)
    with transaction.atomic():
        Pet.objects.select_for_update().get(pk=pedido.pet_id)
        pedido = SolicitacaoAdocao.objects.select_for_update().get(pk=pk, usuario=request.user)
        if pedido.status == SolicitacaoAdocao.Status.PENDENTE:
            pedido.status = SolicitacaoAdocao.Status.CANCELADA
            pedido.save(update_fields=['status', 'atualizado_em'])
            messages.success(request, 'Seu pedido de adoção foi cancelado.')
        else:
            messages.error(request, 'Somente pedidos em análise podem ser cancelados.')
    return redirect('adocao_detalhe', pk=pk)
