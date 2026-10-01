# Creamos un procesador de contexto para añadir variables al contexto de todas las plantillas

from .models import Torneo
from django.utils import timezone

def torneo_context(request):
    """Añade información del torneo al contexto de todas las plantillas.

    Args:
        request (HttpRequest): El objeto de la solicitud.

    Returns:
        dict: Un diccionario para añadir al contexto de la plantilla.
    """
    fecha_actual = timezone.localdate()
    calendario = fecha_actual.isocalendar()
    anio_actual = calendario.year
    semana_actual = calendario.week
    participante_actual = None
    
    # Inicializamos la variable de participación del usuario en el torneo actual como None.
    if request.user.is_authenticated:
        participante_actual = Torneo.objects.filter(user=request.user, anio=anio_actual, semana=semana_actual).first()
    
    # Devolvemos el contexto con la participación actual del usuario en el torneo.
    return {"participante_actual": participante_actual}