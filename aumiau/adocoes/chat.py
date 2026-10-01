"""Conversas privadas entre os dois participantes de uma adoção aprovada."""
import uuid

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .chat_service import conversas_do_usuario, enviar_mensagem, usuario_disponivel
from .models import ConversaAdocao, MensagemAdocao


class MensagemForm(forms.Form):
    texto = forms.CharField(
        label='Sua mensagem', max_length=2000,
        widget=forms.Textarea(attrs={
            'rows': 3, 'placeholder': 'Combine o dia, horário e local da retirada…',
            'class': 'chat-compositor__texto', 'aria-describedby': 'chat-envio-status',
        }),
    )
    cliente_id = forms.UUIDField(widget=forms.HiddenInput)


def _outro(conversa, usuario):
    return conversa.anunciante if conversa.solicitacao.usuario_id == usuario.pk else conversa.solicitacao.usuario


def _nome(usuario):
    return (usuario.get_full_name() or usuario.username) if usuario else 'Participante indisponível'


def _conversa(request, pk):
    return get_object_or_404(conversas_do_usuario(request.user).select_related(
        'solicitacao__pet', 'solicitacao__usuario', 'solicitacao__usuario__perfil',
        'anunciante', 'anunciante__perfil',
    ), pk=pk)


def _serializar(mensagem, usuario):
    return {
        'id': mensagem.pk, 'texto': mensagem.texto, 'minha': mensagem.autor_id == usuario.pk,
        'autor': _nome(mensagem.autor), 'horario': timezone.localtime(mensagem.criado_em).strftime('%d/%m/%Y às %H:%M'),
        'criado_em': mensagem.criado_em.isoformat(),
    }


def _numero(valor, padrao=0):
    texto = str(valor)
    if not texto.isascii() or not texto.isdigit() or len(texto) > 18:
        return padrao
    return int(texto)


def _marcar_lidas(conversa, usuario, ultimo_id):
    if not ultimo_id or not conversa.mensagens.filter(pk=ultimo_id).exists():
        return False
    campo = 'ultimo_lido_adotante_id' if conversa.solicitacao.usuario_id == usuario.pk else 'ultimo_lido_anunciante_id'
    ConversaAdocao.objects.filter(pk=conversa.pk, **{f'{campo}__lt': ultimo_id}).update(**{campo: ultimo_id})
    return True


def _contexto(request, conversa, form=None):
    pagina = Paginator(conversa.mensagens.select_related('autor').order_by('-pk'), 50).get_page(request.GET.get('pagina'))
    historico = list(reversed(list(pagina)))
    return {
        'conversa': conversa, 'outro_nome': _nome(_outro(conversa, request.user)),
        'mensagens': historico, 'pagina': pagina, 'atualizar_chat': pagina.number == 1,
        'ultimo_id': historico[-1].pk if historico else 0,
        'pode_enviar': usuario_disponivel(_outro(conversa, request.user)),
        'form': form if form is not None else MensagemForm(initial={'cliente_id': uuid.uuid4()}),
    }


@login_required
@never_cache
@require_GET
def minhas_conversas(request):
    filtro_lidas = (
        Q(solicitacao__usuario=request.user, mensagens__pk__gt=F('ultimo_lido_adotante_id'))
        | Q(anunciante=request.user, mensagens__pk__gt=F('ultimo_lido_anunciante_id'))
    ) & ~Q(mensagens__autor=request.user)
    ultima = MensagemAdocao.objects.filter(conversa_id=OuterRef('pk')).order_by('-pk').values('texto')[:1]
    conversas = conversas_do_usuario(request.user).select_related(
        'solicitacao__pet', 'solicitacao__usuario', 'anunciante',
    ).annotate(nao_lidas=Count('mensagens', filter=filtro_lidas), ultima_mensagem=Subquery(ultima)).order_by(
        F('ultima_mensagem_em').desc(nulls_last=True), '-criado_em', '-pk',
    )
    pagina = Paginator(conversas, 20).get_page(request.GET.get('page'))
    pagina.object_list = [{
        'conversa': conversa, 'outro_nome': _nome(_outro(conversa, request.user)),
        'nao_lidas': conversa.nao_lidas, 'ultima_mensagem': conversa.ultima_mensagem or '',
    } for conversa in pagina.object_list]
    return render(request, 'adocoes/conversas.html', {'pagina': pagina})


@login_required
@never_cache
@require_GET
def conversa_adocao(request, pk):
    return render(request, 'adocoes/conversa.html', _contexto(request, _conversa(request, pk)))


@never_cache
@require_http_methods(['GET', 'POST'])
def conversa_mensagens(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'erro': 'Sua sessão expirou. Entre novamente para continuar.'}, status=401)
    conversa = _conversa(request, pk)
    if request.method == 'GET':
        apos = _numero(request.GET.get('apos', '0'))
        novas = list(conversa.mensagens.filter(pk__gt=apos).select_related('autor').order_by('pk')[:51])
        lote = novas[:50]
        return JsonResponse({
            'mensagens': [_serializar(mensagem, request.user) for mensagem in lote],
            'proxima': lote[-1].pk if lote else apos, 'tem_mais': len(novas) > 50,
            'pode_enviar': usuario_disponivel(_outro(conversa, request.user)),
        })
    form = MensagemForm(request.POST)
    status = 400
    if form.is_valid():
        try:
            mensagem, criada = enviar_mensagem(
                conversa_id=conversa.pk, usuario=request.user,
                texto=form.cleaned_data['texto'], cliente_id=form.cleaned_data['cliente_id'],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        except PermissionDenied:
            form.add_error(None, 'Esta conversa não está disponível para novas mensagens. Você pode procurar o suporte.')
            status = 403
        else:
            _marcar_lidas(conversa, request.user, _numero(request.POST.get('ultima_visivel', '0')))
            if 'application/json' in request.headers.get('Accept', ''):
                return JsonResponse({'mensagem': _serializar(mensagem, request.user), 'criada': criada}, status=201 if criada else 200)
            return redirect('conversa_adocao', pk=conversa.pk)
    if 'application/json' in request.headers.get('Accept', ''):
        erro = next(iter(form.errors.values()))[0]
        return JsonResponse({'erro': str(erro)}, status=status)
    return render(request, 'adocoes/conversa.html', _contexto(request, conversa, form), status=status)


@never_cache
@require_POST
def conversa_lidas(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'erro': 'Entre novamente para continuar.'}, status=401)
    conversa = _conversa(request, pk)
    ultimo_id = _numero(request.POST.get('ultimo_id', '0'))
    valido = _marcar_lidas(conversa, request.user, ultimo_id)
    if 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({'ok': valido or ultimo_id == 0}, status=200 if valido or ultimo_id == 0 else 400)
    if valido or ultimo_id == 0:
        messages.success(request, 'Conversa marcada como lida.')
    else:
        messages.error(request, 'Não foi possível marcar estas mensagens. Atualize a conversa e tente novamente.')
    return redirect('conversa_adocao', pk=pk)
