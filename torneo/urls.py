from django.urls import path
from . import views

app_name = 'torneo' 

urlpatterns = [
    path('torneo/', views.torneo, name="torneo"),
    path('torneo/registro/', views.registro, name='registro_torneo'),
    path('torneo/estadisticas/', views.estadisticas_torneo, name='estadisticas_torneo'),
    path('torneo/reglas/', views.reglas_torneo, name='reglas_torneo'),
]