from django.urls import path
from . import views
from . import ajuda
from . import solicitacoes
from . import chat

urlpatterns = [
    path('conversas/', chat.minhas_conversas, name='minhas_conversas'),
    path('conversas/<int:pk>/', chat.conversa_adocao, name='conversa_adocao'),
    path('conversas/<int:pk>/mensagens/', chat.conversa_mensagens, name='conversa_mensagens'),
    path('conversas/<int:pk>/lidas/', chat.conversa_lidas, name='conversa_lidas'),
    path('adocoes/pet/<int:pet_id>/solicitar/', solicitacoes.solicitar, name='solicitar_adocao'),
    path('adocoes/minhas/', solicitacoes.minhas_adocoes, name='minhas_adocoes'),
    path('adocoes/<int:pk>/', solicitacoes.detalhe, name='adocao_detalhe'),
    path('adocoes/<int:pk>/cancelar/', solicitacoes.cancelar, name='cancelar_adocao'),
    path('', views.home, name='home'),
    path('ajuda/', ajuda.ajuda, name='ajuda'),
    path('ajuda/pluttu/', ajuda.pluttu, name='pluttu'),
    path('ajuda/contato/', ajuda.chamado_novo, name='chamado_novo'),
    path('ajuda/chamados/', ajuda.meus_chamados, name='meus_chamados'),
    path('ajuda/chamados/<int:pk>/', ajuda.chamado_detalhe, name='chamado_detalhe'),
    path('termos/', ajuda.termos, name='termos'),
    path('privacidade/', ajuda.privacidade, name='privacidade'),
]
