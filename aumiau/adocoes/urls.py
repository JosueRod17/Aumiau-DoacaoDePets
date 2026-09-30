from django.urls import path
from . import views
from . import ajuda

urlpatterns = [
    path('', views.home, name='home'),
    path('ajuda/', ajuda.ajuda, name='ajuda'),
    path('ajuda/pluttu/', ajuda.pluttu, name='pluttu'),
    path('ajuda/contato/', ajuda.chamado_novo, name='chamado_novo'),
    path('ajuda/chamados/', ajuda.meus_chamados, name='meus_chamados'),
    path('ajuda/chamados/<int:pk>/', ajuda.chamado_detalhe, name='chamado_detalhe'),
    path('termos/', ajuda.termos, name='termos'),
    path('privacidade/', ajuda.privacidade, name='privacidade'),
]
