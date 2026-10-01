from django.contrib import admin
from .models import Torneo


@admin.register(Torneo)
class TorneoAdmin(admin.ModelAdmin):
    list_display = [
        'user', 
        'anio', 
        'semana', 
        'puntos_ahorcado', 
        'juegos_ahorcado', 
        'puntos_piedra', 
        'juegos_piedra',
        'intentos_adivina',
        'tiempo_adivina',
        'juegos_adivina',
        ]
    
    search_fields = ['user__username']
    
    list_filter = ['anio', 'semana']