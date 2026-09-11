from django.urls import path
from . import views


app_name = 'pets'

urlpatterns = [
    path('anunciar/', views.anunciar, name='anunciar'),
]