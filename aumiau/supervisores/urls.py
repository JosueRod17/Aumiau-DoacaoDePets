from django.urls import path

from . import views


app_name = 'supervisores'


urlpatterns = [
    path(
        '',
        views.dashboard,
        name='dashboard',
    ),
    path(
        'pets/',
        views.pets_lista,
        name='pets_lista',
    ),
    path(
        'pets/<int:pet_id>/',
        views.pet_detalhe,
        name='pet_detalhe',
    ),
    path(
        'pets/<int:pet_id>/moderar/<str:acao>/',
        views.moderar_pet,
        name='moderar_pet',
    ),
    path(
        'ongs/',
        views.ongs_lista,
        name='ongs_lista',
    ),
    path(
        'ongs/<int:ong_id>/moderar/<str:acao>/',
        views.moderar_ong,
        name='moderar_ong',
    ),
    path(
        'usuarios/',
        views.usuarios_lista,
        name='usuarios_lista',
    ),
]
