
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db import DatabaseError
from django.contrib.auth.decorators import login_required

from . import services

@login_required
def registro(request):
    """Gestiona el registro de un usuario en el torneo de la semana actual.

    Args:
        request (HttpRequest): El objeto de la solicitud.

    Returns:
        HttpResponse: Renderiza la plantilla de registro o redirige a la página
            principal del torneo tras un registro exitoso o si ya está registrado.
    """
    try:
        resultado = services.registrar_participante_torneo(request)
        
        if resultado["ok"]:
            return redirect('torneo:torneo')
        
        if resultado.get("ya_registrado"):
            messages.info(request, "Ya estás registrado en el torneo de esta semana.")
            return redirect('torneo:torneo')
        
        return render(request, "torneo/registro_torneo.html", {"form": resultado["form"]})
    
    except DatabaseError:
        messages.error(request, "Hubo un problema con la base de datos. Por favor, inténtalo de nuevo más tarde.")
        return redirect('torneo:torneo')
        

@login_required
def torneo(request):
    """Muestra la página principal del torneo con el ranking y filtros.

    Args:
        request (HttpRequest): El objeto de la solicitud.

    Returns:
        HttpResponse: Renderiza la plantilla 'torneo/torneo.html' con el contexto.
    """
    try:
        contexto = services.obtener_contexto_torneo(request)
        return render(request, "torneo/torneo.html", contexto)
    
    except DatabaseError:
        messages.error(request, "No se ha podido cargar la información del torneo. Por favor, inténtalo de nuevo más tarde.")
        # Devolvemos un contexto mínimo para que la plantilla no falle
        contexto_minimo = {"semana_actual": services.get_semana_actual()}
    
        return render(request, 'torneo/torneo.html', contexto_minimo)

@login_required
def estadisticas_torneo(request):
    """Muestra la página de estadísticas del torneo con gráficos.

    Args:
        request (HttpRequest): El objeto de la solicitud.

    Returns:
        HttpResponse: Renderiza la plantilla 'torneo/estadisticas_torneo.html'
            con los gráficos y datos de la semana.
    """
    try:
        contexto = services.obtener_contexto_estadisticas_torneo(request)
        return render(request, "torneo/estadisticas_torneo.html", contexto)
    
    except DatabaseError:
        messages.error(request, "No se han podido cargar las estadísticas del torneo. Por favor, inténtalo de nuevo más tarde.")
        return redirect('torneo:torneo')
    
def reglas_torneo(request):
    """Muestra la página de reglas del torneo.
    
    Args:
        request (HttpRequest): El objeto de la solicitud.
        
    Returns:
        HttpResponse: Renderiza la plantilla 'torneo/reglas_torneo.html'.
    """
    return render(request, 'torneo/reglas_torneo.html')
    