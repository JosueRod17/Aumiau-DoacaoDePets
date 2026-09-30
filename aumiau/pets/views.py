import re
from calendar import monthrange
from urllib.parse import quote, urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from usuarios.models import UF_CHOICES
from .forms import PetForm
from .models import FotoPet, Pet


def lista(request):
    pets = Pet.objects.publicos().select_related('ong')
    filtros = {campo: request.GET.get(campo, '').strip() for campo in (
        'q', 'cidade', 'estado', 'localizacao', 'especie', 'genero', 'porte', 'idade', 'ordem',
        'vacinado', 'castrado', 'vermifugado', 'microchipado', 'necessidades_especiais',
    )}
    if filtros['q']:
        pets = pets.filter(Q(nome__icontains=filtros['q']) | Q(raca__icontains=filtros['q']))
    if filtros['cidade']:
        pets = pets.filter(cidade__icontains=filtros['cidade'])
    if filtros['localizacao']:
        pets = pets.filter(Q(cidade__icontains=filtros['localizacao']) | Q(estado__iexact=filtros['localizacao']))
    for campo, escolhas in (
        ('especie', Pet.Especie.values), ('genero', Pet.Genero.values),
        ('porte', Pet.Porte.values), ('estado', dict(UF_CHOICES)),
    ):
        if filtros[campo] in escolhas:
            pets = pets.filter(**{campo: filtros[campo]})
    for campo in ('vacinado', 'castrado', 'vermifugado', 'microchipado', 'necessidades_especiais'):
        if filtros[campo] == '1':
            pets = pets.filter(**{campo: True})
    faixas = {'filhote': (0, 1), 'jovem': (1, 3), 'adulto': (3, 8), 'idoso': (8, None)}
    if filtros['especie'] == 'outros':
        pets = pets.exclude(especie__in=[Pet.Especie.CACHORRO, Pet.Especie.GATO])
    if filtros['idade'] in faixas:
        minimo, maximo = faixas[filtros['idade']]
        hoje = timezone.localdate()

        def aniversario(anos):
            ano = hoje.year - anos
            return hoje.replace(year=ano, day=min(hoje.day, monthrange(ano, hoje.month)[1]))

        exata = Q(data_nascimento__lte=aniversario(minimo))
        estimada = Q(data_nascimento__isnull=True, idade_anos__gte=minimo)
        estimada &= Q(idade_estimada_informada=True) | Q(idade_anos__gt=0) | Q(idade_meses__gt=0)
        if maximo is not None:
            exata &= Q(data_nascimento__gt=aniversario(maximo))
            estimada &= Q(idade_anos__lt=maximo)
        pets = pets.filter(exata | estimada)
    pets = pets.order_by({'nome': 'nome', 'antigos': 'criado_em'}.get(filtros['ordem'], '-criado_em'), 'pk')
    pagina = Paginator(pets, 9).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'pets/lista.html', {
        'page_obj': pagina, 'pets': pagina, 'filtros': filtros,
        'filtros_ativos': any(v for k, v in filtros.items() if k != 'ordem'),
        'querystring': params.urlencode(), 'estados': UF_CHOICES,
        'especies': [*Pet.Especie.choices, ('outros', 'Outros animais (todos)')], 'generos': Pet.Genero.choices,
        'portes': [(valor, rotulo) for valor, rotulo in Pet.Porte.choices if valor != Pet.Porte.NAO_INFORMADO],
    })


def detalhe(request, pk):
    visiveis = Pet.objects.publicos()
    if request.user.is_authenticated:
        visiveis = Pet.objects.filter(
            Q(pk__in=visiveis) | Q(pk__in=Pet.objects.gerenciaveis_por(request.user))
        )
    pet = get_object_or_404(visiveis.select_related('ong', 'responsavel').prefetch_related('fotos'), pk=pk)
    gerenciavel = Pet.objects.gerenciaveis_por(request.user).filter(pk=pk).exists()
    email = pet.ong.email if pet.ong_id else pet.email_contato
    telefone = pet.ong.telefone if pet.ong_id else pet.telefone_contato
    digitos = re.sub(r'\D', '', telefone or '')
    if len(digitos) in (10, 11):
        digitos = '55' + digitos
    whatsapp = ''
    if len(digitos) in (12, 13) and digitos.startswith('55'):
        whatsapp = f'https://wa.me/{digitos}?' + urlencode({'text': f'Olá! Vi o anúncio de {pet.nome} no AuMiau e gostaria de saber mais sobre a adoção.'})
    assunto = f'Interesse em adotar {pet.nome} — AuMiau'
    email_url = 'mailto:' + quote(email, safe='@') + '?' + urlencode({'subject': assunto}, quote_via=quote) if email else ''
    gmail_url = 'https://mail.google.com/mail/?' + urlencode({'view': 'cm', 'fs': '1', 'to': email, 'su': assunto}) if email else ''
    outlook_url = 'https://outlook.live.com/mail/0/deeplink/compose?' + urlencode({'to': email, 'subject': assunto}) if email else ''
    return render(request, 'pets/detalhe.html', {
        'pet': pet, 'gerenciavel': gerenciavel, 'email_contato': email,
        'telefone_contato': telefone, 'whatsapp_url': whatsapp, 'email_url': email_url,
        'gmail_url': gmail_url, 'outlook_url': outlook_url,
        'publico': Pet.objects.publicos().filter(pk=pk).exists(),
        'outros_pets': Pet.objects.publicos().exclude(pk=pk).select_related('ong')[:3],
    })


@login_required
def meus_pets(request):
    pets = Pet.objects.gerenciaveis_por(request.user).select_related('ong')
    status = request.GET.get('status', '')
    if status in Pet.Status.values:
        pets = pets.filter(status=status)
    return render(request, 'pets/meus_pets.html', {
        'page_obj': Paginator(pets, 12).get_page(request.GET.get('page')),
        'status_atual': status, 'status_opcoes': Pet.Status.choices,
        'querystring': urlencode({'status': status}) if status else '',
    })


def _formulario(request, pet=None):
    resposta_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    rascunho = request.method == 'POST' and request.POST.get('acao') == 'rascunho'
    initial = {}
    if pet is None and request.method == 'GET':
        perfil = getattr(request.user, 'perfil', None)
        if perfil:
            initial.update(cidade=perfil.cidade, estado=perfil.estado)
        if request.GET.get('ong', '').isdigit():
            initial['ong'] = request.GET['ong']
    form = PetForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        instance=pet, usuario=request.user, rascunho=rascunho, initial=initial,
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            anuncio = form.save(commit=False)
            if not anuncio.pk:
                anuncio.criado_por = request.user
            if anuncio.ong_id:
                anuncio.responsavel = None
                anuncio.email_contato = ''
                anuncio.telefone_contato = ''
            elif not anuncio.responsavel_id:
                anuncio.responsavel = request.user
            anuncio.status = Pet.Status.RASCUNHO if rascunho else Pet.Status.PENDENTE
            anuncio.destaque = False
            anuncio.moderado_por = None
            anuncio.moderado_em = None
            anuncio.publicado_em = None
            anuncio.adotado_em = None
            anuncio.motivo_rejeicao = ''
            anuncio.save()
            form.cleaned_data['remover_fotos'].delete()
            for indice, arquivo in enumerate(form.cleaned_data['galeria'], start=anuncio.fotos.count()):
                FotoPet.objects.create(pet=anuncio, imagem=arquivo, ordem=indice)
        messages.success(request, 'Rascunho salvo. Você pode continuar quando quiser.' if rascunho else 'Anúncio enviado! Ele aparecerá para adoção depois da aprovação da nossa equipe.')
        if resposta_json:
            return JsonResponse({'redirect_url': reverse('pets:meus_pets')})
        return redirect('pets:meus_pets')
    if request.method == 'POST' and resposta_json:
        return JsonResponse({'errors': form.errors.get_json_data()}, status=422)
    return render(request, 'pets/anunciar.html', {'form': form, 'pet': pet, 'editando': pet is not None})


@login_required
def anunciar(request):
    return _formulario(request)


@login_required
def editar(request, pk):
    pet = get_object_or_404(Pet.objects.gerenciaveis_por(request.user), pk=pk)
    if pet.status == Pet.Status.ADOTADO:
        messages.info(request, 'Este pet já foi adotado. Entre em contato com a equipe para reabrir o anúncio.')
        return redirect('pets:detalhe', pk=pk)
    return _formulario(request, pet)
