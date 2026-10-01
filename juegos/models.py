from django.db import models
from django.conf import settings

class Partida(models.Model):
    """Modelo para partidas en modo libre"""
    # Usamos Choices para mostrar nombres legibles en el admin
    JUEGO_CHOICES = [
        ("ahorcado", "Ahorcado"),
        ("pptls", "Piedra-Papel-Tijera-Lagarto-Spock"),
        ("adivina", "Adivina el Número")
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="partidas_libres"
    )
    juego = models.CharField(max_length=20, choices=JUEGO_CHOICES, verbose_name="Juego")
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de juego")
    
    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Partida Libre"
        
    def __str__(self):
        return f"{self.get_juego_display()} - {self.user.username} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"