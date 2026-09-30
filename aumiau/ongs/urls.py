from django.urls import path

from . import views

app_name = 'ongs'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('cadastrar/', views.cadastrar, name='cadastrar'),
    path('painel/', views.painel, name='painel'),
    path('<int:pk>/', views.detalhe, name='detalhe'),
    path('<int:pk>/editar/', views.editar, name='editar'),
]
