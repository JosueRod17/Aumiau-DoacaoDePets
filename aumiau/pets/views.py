from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url='home')
def anunciar(request):
    return render(request, 'pets/anunciar.html')