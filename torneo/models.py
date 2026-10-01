from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

MAX_PARTIDAS_TORNEO = 10

def anio_iso_actual():
    return timezone.localdate().isocalendar().year

class Torneo(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='torneo'
    )
    semana = models.PositiveSmallIntegerField(verbose_name='Semana', default=1, help_text='Número de la semana del torneo')
    anio = models.PositiveSmallIntegerField(verbose_name='Año', default=anio_iso_actual, help_text='Año del torneo')
    puntos_ahorcado = models.PositiveIntegerField(verbose_name='Puntos Ahorcado', default=0)
    puntos_piedra = models.PositiveIntegerField(verbose_name='PPTLS', default=0, help_text='Puntos en Piedra, Papel, Tijeras, Lagarto, Spock')
    juegos_ahorcado = models.PositiveSmallIntegerField(verbose_name='Juegos Ahorcado', default=0, help_text='Número de partidas jugadas en Ahorcado en la semana')
    juegos_piedra = models.PositiveSmallIntegerField(verbose_name='Juegos PPTLS', default=0, help_text='Número de partidas en PPTLS en la semana')
    intentos_adivina = models.PositiveIntegerField(verbose_name='Intentos Adivina', default=0, help_text='Número de intentos en Adivina el Número')
    tiempo_adivina = models.DecimalField(verbose_name="Tiempo Adivina", max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Tiempo utilizado en resolver el juego Adivina el Número")
    juegos_adivina = models.PositiveSmallIntegerField(verbose_name="Juegos Adivina", default=0, help_text="Número de partidas jugadas en Adivina el Número")
    fecha_inscripcion = models.DateTimeField(verbose_name="Fecha de Inscripción", auto_now_add=True)
    
    class Meta:
        # Ordenamos por año y después la semana más reciente
        ordering = ['-anio', '-semana']
        # Definimos las restricciones de la base de datos para asegurar la integridad de los datos.
        constraints = [
            models.UniqueConstraint(fields=['user', 'anio', 'semana'], name='unique_user_anio_semana'),
            models.CheckConstraint(condition=models.Q(semana__gte=1, semana__lte=53), name="semana_valida"),
            models.CheckConstraint(condition=models.Q(juegos_ahorcado__lte=MAX_PARTIDAS_TORNEO), name="limite_juegos_ahorcado"),
            models.CheckConstraint(condition=models.Q(juegos_piedra__lte=MAX_PARTIDAS_TORNEO), name="limite_juegos_piedra"),
            models.CheckConstraint(condition=models.Q(juegos_adivina__lte=MAX_PARTIDAS_TORNEO), name="limite_juegos_adivina"),
            models.CheckConstraint(condition=models.Q(puntos_ahorcado__lte=3 * models.F("juegos_ahorcado")), name="puntos_ahorcado"),
            models.CheckConstraint(condition=models.Q(puntos_piedra__lte=3 * models.F("juegos_piedra")), name="puntos_piedra"),
            models.CheckConstraint(condition=models.Q(
                juegos_adivina = 0,
                intentos_adivina = 0,
                tiempo_adivina =  0
                )
                | models.Q(
                    juegos_adivina__gt=0,
                    intentos_adivina__gt=0,
                    tiempo_adivina__gt=0
                    ),
                name="resultado_adivina"),
            ]
        
    def __str__(self):
        return (
            f'Torneo de {self.user.username} -- '
            f'Semana {self.semana}/{self.anio}')