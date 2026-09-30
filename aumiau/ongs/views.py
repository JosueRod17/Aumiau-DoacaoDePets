from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render

from pets.models import Pet

from .forms import CadastroOngForm
from .models import Ong


REGIOES = [('todas', 'Todas'), ('SP', 'São Paulo'), ('RJ', 'Rio de Janeiro'), ('DF', 'Brasília'), ('outras', 'Outras regiões')]


def lista(request):
    busca = request.GET.get('q', '').strip()
    regiao = request.GET.get('regiao', 'todas')
    if regiao not in dict(REGIOES):
        regiao = 'todas'
    ongs_aprovadas = Ong.objects.filter(status=Ong.Status.APROVADA)
    ongs = ongs_aprovadas.annotate(
        pets_disponiveis=Count('pets', filter=Q(pets__status=Pet.Status.PUBLICADO)),
    ).order_by('nome', 'pk')
    if busca:
        ongs = ongs.filter(Q(nome__icontains=busca) | Q(cidade__icontains=busca) | Q(estado__iexact=busca))
    if regiao == 'outras':
        ongs = ongs.exclude(estado__in=['SP', 'RJ', 'DF'])
    elif regiao != 'todas':
        ongs = ongs.filter(estado=regiao)
    pagina = Paginator(ongs, 8).get_page(request.GET.get('pagina'))
    pets_ongs = Pet.objects.filter(ong__status=Ong.Status.APROVADA)
    return render(request, 'ongs/lista.html', {
        'ongs': pagina, 'pagina': pagina, 'busca': busca, 'regiao': regiao, 'regioes': REGIOES,
        'total_ongs': ongs_aprovadas.count(),
        'total_pets': pets_ongs.filter(status__in=[Pet.Status.PUBLICADO, Pet.Status.ADOTADO]).count(),
        'total_adocoes': pets_ongs.filter(status=Pet.Status.ADOTADO).count(),
    })


def detalhe(request, pk):
    filtro = Q(status=Ong.Status.APROVADA)
    if request.user.is_authenticated:
        filtro |= Q(responsavel=request.user)
    ong = get_object_or_404(Ong.objects.filter(filtro), pk=pk)
    proprietario = request.user.is_authenticated and ong.responsavel_id == request.user.pk
    pets = ong.pets.filter(status=Pet.Status.PUBLICADO, ong__status=Ong.Status.APROVADA)
    return render(request, 'ongs/detalhe.html', {
        'ong': ong, 'proprietario': proprietario,
        'pets': pets.order_by('-publicado_em', '-pk'),
    })


def _formulario(request, ong, criando):
    form = CadastroOngForm(request.POST if request.method == 'POST' else None, request.FILES or None, instance=ong)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                ong = form.save(commit=False)
                ong.responsavel = request.user
                ong.status = Ong.Status.PENDENTE
                ong.motivo_rejeicao = ''
                ong.moderado_por = None
                ong.moderado_em = None
                ong.save()
        except IntegrityError:
            form.add_error('cnpj', 'Este CNPJ já foi cadastrado. Confira seu painel ou fale com o suporte.')
        else:
            messages.success(request, 'ONG cadastrada e enviada para análise.' if criando else 'Alterações salvas. A ONG foi enviada novamente para análise.')
            return redirect('ongs:painel')
    return render(request, 'ongs/formulario.html', {'form': form, 'ong': ong, 'criando': criando})


@login_required
def cadastrar(request):
    return _formulario(request, Ong(), criando=True)


@login_required
def editar(request, pk):
    ong = get_object_or_404(Ong, pk=pk, responsavel=request.user)
    return _formulario(request, ong, criando=False)


@login_required
def painel(request):
    ongs = Ong.objects.filter(responsavel=request.user).prefetch_related(
        Prefetch('pets', queryset=Pet.objects.order_by('-criado_em'), to_attr='pets_do_painel'),
    )
    return render(request, 'ongs/painel.html', {'ongs': ongs})
