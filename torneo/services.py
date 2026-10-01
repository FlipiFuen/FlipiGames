
from datetime import timedelta

from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F

from .forms import TorneoRegistroForm
from .models import Torneo

from flipigames.charts import preparar_datos_graficos

def get_periodo_actual():
    """Obtiene el año y la semana actual según el calendario ISO 8601.

    Returns:
        tuple[int, int]: Una tupla con el año y el número de la semana actual.
    """
    fecha_actual = timezone.localdate()
    calendario = fecha_actual.isocalendar()
    return calendario.year, calendario.week

def get_anio_actual():
    """Devuelve el año ISO actual"""
    return get_periodo_actual()[0]

def get_semana_actual():
    """Devuelve la semana ISO actual"""
    return get_periodo_actual()[1]

def get_ranking_config(juego):
    """
    Obtiene la configuración del ranking para un juego específico.

    Args:
        juego (str): El nombre del juego para el cual obtener la configuración.

    Returns:
        dict: Un diccionario con los parámetros de filtrado y ordenación.
    """
    
    config = {
        "ahorcado": {
            "filters": {"juegos_ahorcado__gt": 0},
            "order": ["-puntos_ahorcado", "user__username"],
            "valor": lambda p: p.puntos_ahorcado, # Obtiene el valor de los puntos de ahorcado del participante
        },
        "piedra": {
            "filters": {"juegos_piedra__gt": 0},
            "order": ["-puntos_piedra", "user__username"],
            "valor": lambda p: p.puntos_piedra,
        },
        "adivina": {
            "filters": {"juegos_adivina__gt": 0},
            "order": ["intentos_adivina", "tiempo_adivina", "user__username"],
            "valor": lambda p: (p.intentos_adivina, p.tiempo_adivina),
        },
        "general": {
            "filters": {},
            "order": ["-total_puntos", "user__username"],
            "valor": lambda p: p.total_puntos,
        },
    }
    return config.get(juego, config["general"])
    
def calcular_puesto(participante, indice, ranking_lista, juego):
    """
    Calcula el puesto de un participante en el ranking.

    Args:
        participante (Torneo): El participante para el cual calcular el puesto.
        indice (int): El índice del participante en la lista del ranking.
        ranking_lista (list[Torneo]): La lista del ranking.
        juego (str): El nombre del juego para el cual calcular el puesto.

    Returns:
        int: El puesto del participante en el ranking.
    """
    # Si es el primer participante de la lista, su puesto es 1.
    if indice == 0:
        return 1
    
    config = get_ranking_config(juego)
    valor_actual = config["valor"](participante)
    valor_previo = config["valor"](ranking_lista[indice - 1])
    
    # Comparamos el valor actual con el valor del participante previo para determinar si el puesto cambia.
    if valor_actual != valor_previo:
        return ranking_lista[indice - 1].puesto + 1
    
    return ranking_lista[indice - 1].puesto

def get_ranking_filtrado(parametros):
    """Filtra y ordena el ranking del torneo según los parámetros GET.

    Args:
        parametros (dict): Un diccionario (como request.GET) con los parámetros
            de filtrado: 'q', 'jugador', 'juego'.

    Returns:
        tuple[list[Torneo], int]: Una tupla con una lista del ranking
            filtrado y el número de la semana que se está mostrando.
    """
   
    # Obtenemos los parámetros de filtrado
    q = parametros.get("q", "").strip()
    anio = parametros.get("anio", "").strip()
    jugador = parametros.get("jugador", "").strip()
    juego = parametros.get("juego", "general").strip()
    
    anio_mostrar = get_anio_actual()
    semana_mostrar = get_semana_actual()
    
    if anio and anio.isdigit():
        anio_solicitado = int(anio)
        
        if 2025 <= anio_solicitado <= 2100:
            anio_mostrar = anio_solicitado
    
    if q and q.isdigit():
        semana_solicitada = int(q)
        if 1 <= semana_solicitada <= 53:
            semana_mostrar = semana_solicitada
        
    ranking = Torneo.objects.filter(anio=anio_mostrar, semana=semana_mostrar).select_related(
        "user").annotate(
        total_puntos = F("puntos_ahorcado") + F("puntos_piedra")
        )
    
    # Aplicamos los filtros y ordenación según el juego seleccionado
    config = get_ranking_config(juego)
    ranking = ranking.filter(**config["filters"]).order_by(*config["order"])
    
    # Convertimos a lista para calcular los puestos antes de filtrar por usuario
    ranking_lista = list(ranking)
    
    for indice, participante in enumerate(ranking_lista):
        participante.puesto = calcular_puesto(participante, indice, ranking_lista, juego)
        
    # Aplicamos los filtros de usuario sobre la lista
    if jugador:
        ranking_lista = [p for p in ranking_lista if p.user.username == jugador] 
    
    return ranking_lista, semana_mostrar, anio_mostrar

def get_mejores_puntuaciones_historicas():
    """Obtiene las mejores puntuaciones históricas de cada juego.

    Returns:
        tuple[Torneo | None, Torneo | None, Torneo | None]: Una tupla con los
            objetos Torneo correspondientes a la mejor puntuación en Ahorcado,
            PPTLS y Adivina el Número, respectivamente.
    """
    mejor_ahorcado = Torneo.objects.filter(puntos_ahorcado__gt=0).select_related("user").order_by("-puntos_ahorcado", "-anio", "semana").first()
    mejor_piedra = Torneo.objects.filter(puntos_piedra__gt=0).select_related("user").order_by("-puntos_piedra", "-anio", "semana").first()
    mejor_adivina = Torneo.objects.filter(juegos_adivina__gt=0, intentos_adivina__gt=0).select_related("user").order_by("intentos_adivina", "tiempo_adivina", "user__username", "-anio", "semana").first()
    
    return mejor_ahorcado, mejor_piedra, mejor_adivina

def get_campeon_semana(anio, semana):
    """Obtiene el campeón del torneo para una semana específica.

    Args:
        anio (int): El año para la que se busca el campeón.
        semana (int): El número de la semana para la que se busca el campeón.
        
    Returns:
        Torneo|None: El objeto de participación del campeón o None si no hubo
    """
    if anio < 1 or semana < 1:
        return None
    
    return Torneo.objects.filter(
        anio=anio, 
        semana=semana, 
        juegos_adivina__gt=0
        ).select_related(
            "user"
        ).order_by(
            "intentos_adivina", 
            "tiempo_adivina", 
            "user__username"
        ).first()

def paginar_ranking(ranking, page_number, per_page=10):
    """Devuelve una página válida del ranking.

    Args:
        ranking (list): Lista de participantes del ranking.
        page_number (int | str | None): Número de página solicitado.
        per_page (int): Número de elementos por página.

    Returns:
        Page: Página paginada del ranking.

    Raises:
        ValueError: Si per_page es cero o negativo.
    """
    if per_page <= 0:
        raise ValueError("per_page debe ser mayor que cero")
    
    paginator = Paginator(ranking, per_page)
    return paginator.get_page(page_number)

def registrar_participante_torneo(request):
    """Registra a un usuario en el torneo de la semana actual.
    
    Args:
        request: El objeto HttpRequest que contiene los datos del POST.
        
    Returns:
        dict: Un diccionario con el resultado de la operación.
    """
    anio_actual, semana_actual = get_periodo_actual()
    
    if Torneo.objects.filter(user=request.user, anio=anio_actual, semana=semana_actual).exists():
        messages.warning(request, '¡Ya estás apuntado al torneo!')
        return {"ok": False, "ya_registrado": True}
    
    if request.method != 'POST':
        return {"ok": False, "ya_registrado": False, "form": TorneoRegistroForm()}
            
    form = TorneoRegistroForm(request.POST)
    if not form.is_valid():
        return {"ok": False, "ya_registrado": False, "form": form}
            
    nuevo_participante = form.save(commit=False)
    nuevo_participante.user = request.user
    nuevo_participante.anio = anio_actual
    nuevo_participante.semana = semana_actual
    nuevo_participante.save()
            
    messages.success(request, '¡Te has apuntado al torneo!')
    return {"ok": True, "ya_registrado": False}

def obtener_contexto_torneo(request):
    """Obtiene el contexto necesario para renderizar la página principal del torneo.

    Args:
        request: El objeto HttpRequest que contiene los datos de la solicitud.

    Returns:
        dict: Un diccionario con el contexto necesario para renderizar la página del torneo.
    """
    ranking, semana_mostrar, anio_mostrar = get_ranking_filtrado(request.GET)
    mejor_ahorcado, mejor_piedra, mejor_adivina = get_mejores_puntuaciones_historicas()
            
    # Obtenemos el campeón de la semana anterior
    fecha_anterior = timezone.localdate() - timedelta(days=7)
    calendario_anterior = fecha_anterior.isocalendar()
    
    anio_campeon = calendario_anterior.year
    semana_anterior = calendario_anterior.week
        
    campeon_semana = get_campeon_semana(anio_campeon, semana_anterior)
                
    # Paginamos con 10 resultados por página
    page_obj = paginar_ranking(ranking, request.GET.get("page"), 10)
            
    # Obtenemos todos los participantes para el selector de jugador
    todos_participantes = Torneo.objects.filter(
        anio=anio_mostrar, 
        semana=semana_mostrar
        ).select_related(
            "user"
        ).order_by("user__username")
            
    return  {
        'todos_participantes': todos_participantes,
        'anio_actual': get_anio_actual(),
        'anio_mostrar': anio_mostrar,
        'semana': get_semana_actual(),
        'semana_actual': semana_mostrar,
        'semana_anterior': semana_anterior,
        'page_obj': page_obj,
        'q': request.GET.get('q', ''),
        'jugador': request.GET.get('jugador', ''),
        'juego_seleccionado': request.GET.get('juego', 'general'),
        'mejor_ahorcado': mejor_ahorcado,
        'mejor_piedra': mejor_piedra,
        'mejor_adivina': mejor_adivina,
        'campeon_semana': campeon_semana,
    }
    
def obtener_contexto_estadisticas_torneo(request):
    """Obtiene el contexto necesario para renderizar las estadísticas del torneo.

    Args:
        request (HttpRequest): El objeto de la solicitud.

    Returns:
        dict: Un diccionario con el contexto necesario para renderizar la página de estadísticas del torneo.
    """
    anio_actual, semana_actual = get_periodo_actual()
            
    # Obtenemos el año y la semana a mostrar desde los parámetros GET, si no usamos la actual
    try:
        anio_mostrar = int(request.GET.get("anio", anio_actual))
    except(ValueError, TypeError):
        anio_mostrar = anio_actual
    try:
        semana_mostrar = int(request.GET.get("semana", semana_actual))
    except (ValueError, TypeError):
        semana_mostrar = semana_actual
        
    max_semana = semana_actual if anio_mostrar == anio_actual else 53
        
    if semana_mostrar < 1 or semana_mostrar > max_semana:
        semana_mostrar = semana_actual if anio_mostrar == anio_actual else 1
            
    # Obtenemos el ranking de la semana y anotamos los puntos totales
    ranking = Torneo.objects.filter(
        anio=anio_mostrar, 
        semana=semana_mostrar
        ).select_related(
            "user"
        ).annotate(
        total_puntos= F("puntos_ahorcado") + F("puntos_piedra")
        ).order_by("-total_puntos", "user__username")
            
    # Generamos los gráficos
    grafico_barras, grafico_torta, grafico_adivina = preparar_datos_graficos(ranking, semana_mostrar)
            
    return {
        "anio_actual": anio_actual,
        "anio_mostrar": anio_mostrar,
        "semana_actual": semana_actual,
        "semana_mostrar": semana_mostrar,
        "semana_anterior": semana_mostrar - 1 if semana_mostrar > 1 else None,
        "semana_siguiente": semana_mostrar + 1 if semana_mostrar < max_semana else None,
        "grafica_barras": grafico_barras,
        "grafica_torta": grafico_torta,
        "grafica_adivina": grafico_adivina,
    }
    
    