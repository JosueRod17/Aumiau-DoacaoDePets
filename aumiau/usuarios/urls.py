from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views
from . import google
from . import recuperacao


app_name = 'usuarios'


urlpatterns = [
    path('senha/recuperar/', recuperacao.SolicitarRecuperacaoView.as_view(), name='recuperar'),
    path('senha/recuperar/enviado/', recuperacao.RecuperacaoEnviadaView.as_view(), name='recuperar_enviado'),
    path('senha/recuperar/<uidb64>/<token>/', recuperacao.ConfirmarRecuperacaoView.as_view(), name='recuperar_confirmar'),
    path('senha/recuperar/concluido/', recuperacao.RecuperacaoConcluidaView.as_view(), name='recuperar_concluido'),
    path('conta/excluir/', views.excluir, name='excluir'),
    path('google/iniciar/', google.iniciar, name='google_iniciar'),
    path('google/retorno/', google.retorno, name='google_retorno'),
    path('google/completar/', google.completar, name='google_completar'),
    path('google/senha/', google.senha, name='google_senha'),
    path(
        'cadastro/',
        views.cadastro,
        name='cadastro',
    ),

    path(
        'entrar/',
        views.LoginUsuarioView.as_view(),
        name='login',
    ),

    path(
        'sair/',
        LogoutView.as_view(),
        name='logout',
    ),
]
