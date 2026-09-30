from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views
from . import google


app_name = 'usuarios'


urlpatterns = [
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
