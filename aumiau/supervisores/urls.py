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
        'pets/novo/',
        views.pet_criar,
        name='pet_criar',
    ),
    path(
        'pets/<int:pet_id>/',
        views.pet_detalhe,
        name='pet_detalhe',
    ),
    path(
        'pets/<int:pet_id>/editar/',
        views.pet_editar,
        name='pet_editar',
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
        'ongs/nova/',
        views.ong_criar,
        name='ong_criar',
    ),
    path(
        'ongs/<int:ong_id>/',
        views.ong_detalhe,
        name='ong_detalhe',
    ),
    path(
        'ongs/<int:ong_id>/editar/',
        views.ong_editar,
        name='ong_editar',
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
    path(
        'usuarios/<int:usuario_id>/',
        views.usuario_detalhe,
        name='usuario_detalhe',
    ),
    path(
        'usuarios/<int:usuario_id>/status/<str:acao>/',
        views.alterar_status_usuario,
        name='alterar_status_usuario',
    ),
    path(
        'atividades/',
        views.atividades_lista,
        name='atividades_lista',
    ),
    path(
        'equipe/',
        views.equipe_lista,
        name='equipe_lista',
    ),
    path(
        'equipe/<int:usuario_id>/<str:acao>/',
        views.alterar_supervisor,
        name='alterar_supervisor',
    ),
]
