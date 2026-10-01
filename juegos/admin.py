from django.contrib import admin
from .models import Partida

@admin.register(Partida)
class PartidaAdmin(admin.ModelAdmin):
    list_display = ("juego", "user", "fecha")
    list_filter = ("juego", "fecha")
    search_fields = ("user__username", "juego")
