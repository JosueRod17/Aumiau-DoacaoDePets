from django.urls import path
from . import views


app_name = 'pets'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('anunciar/', views.anunciar, name='anunciar'),
    path('meus-anuncios/', views.meus_pets, name='meus_pets'),
    path('<int:pk>/', views.detalhe, name='detalhe'),
    path('<int:pk>/editar/', views.editar, name='editar'),
]
