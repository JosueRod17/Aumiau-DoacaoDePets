from django.db.models import Q
from django.shortcuts import render
from ongs.models import Ong
from pets.models import Pet

def home(request):
    localizacao = request.GET.get('localizacao', '').strip()

    pets = Pet.objects.filter(disponivel=True)

    if localizacao:
        pets = pets.filter(
            Q(cidade__icontains=localizacao)
            | Q(estado__iexact=localizacao)
        )

    ongs_aprovadas = Ong.objects.filter(aprovada=True)

    contexto = {
        'pets': pets[:4],
        'localizacao': localizacao,
        'total_pets': Pet.objects.count(),
        'ongs': ongs_aprovadas[:4],
        'total_ongs': ongs_aprovadas.count(),
    }

    return render(request, 'home.html', contexto)