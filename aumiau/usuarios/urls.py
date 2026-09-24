from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views


app_name = 'usuarios'


urlpatterns = [
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
