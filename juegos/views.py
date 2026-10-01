
from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from . import services
    
@login_required
def ahorcado(request, modo_juego=None):
    """Vista principal para el juego del Ahorcado.

    Args:
        request (HttpRequest): El objeto de la solicitud.
        modo_juego (str, optional): "torneo" si la partida cuenta para el
            torneo. Defaults to None.

    Returns:
        HttpResponse: Renderiza la plantilla 'juegos/ahorcado.html' con el
                      contexto del estado actual del juego.
    """
    # Verifica que el modo de juego sea válido para que no se pueda acceder a modos inexistentes introduciendo manualmente la URL
    if modo_juego not in (None, "torneo"):
        raise Http404("Modo de juego no válido")
    
    # Variables del estado del juego
    partida_torneo = (modo_juego == "torneo")
    participacion_torneo = None
    
    # --- Lógica del Torneo ---
    if partida_torneo:
        if services.es_fin_semana():
            messages.warning(request, "El juego del Ahorcado sólo está disponible en el modo torneo de lunes a viernes")
            return redirect("torneo:torneo")
        
        participacion_torneo = services.validar_participacion_torneo(request, "ahorcado")
        if not participacion_torneo:
            return redirect("torneo:torneo")
        
    contexto = services.procesar_ahorcado_request(request, partida_torneo, participacion_torneo)
    
    # Verificamos si el contexto indica que se debe redirigir a otra URL.
    if "redirigir" in contexto:                    
        return redirect(contexto["redirigir"])
        
    return render(request, "juegos/ahorcado.html", contexto)

@login_required
def pptls(request, modo_juego=None):
    """Vista principal para el juego Piedra-Papel-Tijera-Lagarto-Spock.

    Args:
        request (HttpRequest): El objeto de la solicitud.
        modo_juego (str, optional): "torneo" si la partida cuenta para el
            torneo. Defaults to None.

    Returns:
        HttpResponse: Renderiza la plantilla 'juegos/pptls.html' con el contexto.
    """
    # Verifica que el modo de juego sea válido para que no se pueda acceder a modos inexistentes introduciendo manualmente la URL
    if modo_juego not in (None, "torneo"):
        raise Http404("Modo de juego no válido")
    
    # Variables del estado del juego
    partida_torneo = (modo_juego == "torneo")
    participacion_torneo = None
    
    if partida_torneo:
        if services.es_fin_semana():
            messages.warning(request, "El juego Piedra-Papel-Tijera-Lagarto-Spock sólo está disponible en el modo torneo de lunes a viernes")
            return redirect("torneo:torneo")
                
        participacion_torneo = services.validar_participacion_torneo(request, "piedra")
        if not participacion_torneo:
            return redirect("torneo:torneo")
        
    contexto = services.procesar_pptls_request(request, partida_torneo, participacion_torneo)
        
    return render(request, "juegos/pptls.html", contexto)

@login_required
def adivina_numero(request, modo_juego=None):
    """Vista principal para el juego 'Adivina el Número'.

    Args:
        request (HttpRequest): El objeto de la solicitud.
        modo_juego (str, optional): "torneo" si la partida es de torneo.
            Defaults to None.

    Returns:
        HttpResponse: Renderiza la plantilla 'juegos/adivina_numero.html' con el contexto.
    """
    # Verifica que el modo de juego sea válido para que no se pueda acceder a modos inexistentes introduciendo manualmente la URL
    if modo_juego not in (None, "torneo"):
        raise Http404("Modo de juego no válido")
    
    partida_torneo = (modo_juego == "torneo")
    participacion_torneo = None
    teclado = [["7", "8", "9"], ["4", "5", "6"], ["1", "2", "3"]]
 
    if partida_torneo:  
        participacion_torneo, url_torneo = services.validar_participacion_adivina(request)
        if url_torneo:
            return redirect(url_torneo)
            
    contexto = services.procesar_adivina_request(request, partida_torneo, participacion_torneo, teclado)  
    return render(request, "juegos/adivina_numero.html", contexto)
    
                  