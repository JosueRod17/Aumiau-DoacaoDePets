from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from .forms import LoginEmailForm

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
        LoginView.as_view(
            template_name='usuarios/login.html',
            authentication_form=LoginEmailForm,
            redirect_authenticated_user=True,
        ),
        name='login',
    ),

    path(
        'sair/',
        LogoutView.as_view(),
        name='logout',
    ),
]