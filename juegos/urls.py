from django.urls import path
from . import views

app_name = 'juegos' # Nombre para usar rutas como juegos:ahorcado

urlpatterns = [
    path('ahorcado/', views.ahorcado, name='ahorcado'), # Ruta para el juego normal de Ahorcado
    path('ahorcado/<str:modo_juego>/', views.ahorcado, name="ahorcado_modo"), # Ruta para el juego Ahorcado en modo torneo
    path('pptls/', views.pptls, name='pptls'), # Ruta para el juego Piedra-Papel-Tijera-Lagarto-Spock
    path('pptls/<str:modo_juego>/', views.pptls, name='pptls_modo'), # Ruta para el juego Piedra-Papel-Tijera-Lagarto-Spock en modo torneo
    path('adivina_numero/', views.adivina_numero, name='adivina_numero'), # Ruta para el juego Adivina el Número
    path('adivina_numero/<str:modo_juego>/', views.adivina_numero, name='adivina_numero_modo'), # Ruta para el juego Adivina el Número en modo torneo
]