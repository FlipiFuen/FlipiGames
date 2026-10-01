import os
import random
import time

from django.utils import timezone
from django.conf import settings
from django.contrib import messages

# Importamos transaction para manejar transacciones atómicas en la base de datos, en desarrollo con SQLite puede no ser completamente efectivo.
# Con SQLite esta solución es válida para el flujo normal, pero la concurrencia real deberá probarse con PostgreSQL.
from django.db import DatabaseError, transaction 
from django.db.models import F

from .models import Partida
from torneo.models import Torneo

# --- Constantes ---
MAX_FALLOS_AHORCADO = 7
MAX_PARTIDAS_TORNEO = 10
PUNTOS_VICTORIA_AHORCADO = 3
PUNTOS_VICTORIA_PPTLS = 3
PUNTOS_EMPATE_PPTLS = 1

OPCIONES_PPTLS = ["piedra", "papel", "tijera", "lagarto", "spock"]

REGLAS_PPTLS = {
    "piedra": ["tijera", "lagarto"],
    "papel": ["piedra", "spock"],
    "tijera": ["papel", "lagarto"],
    "lagarto": ["spock", "papel"],
    "spock": ["tijera", "piedra"],
}

MENSAJES_PPTLS = {
    ("piedra", "tijera"): "Piedra aplasta a Tijeras",
    ("piedra", "lagarto"): "Piedra aplasta a Lagarto",
    ("papel", "piedra"): "Papel tapa a Piedra",
    ("papel", "spock"): "Papel desautoriza a Spock",
    ("tijera", "papel"): "Tijeras cortan a Papel",
    ("tijera", "lagarto"): "Tijeras decapitan a Lagarto",
    ("lagarto", "spock"): "Lagarto envenena a Spock",
    ("lagarto", "papel"): "Lagarto se come a Papel",
    ("spock", "tijera"): "Spock destroza a Tijeras",
    ("spock", "piedra"): "Spock vaporiza a Piedra",
}

CLAVES_AHORCADO = [
    "palabra_secreta",
    "letras_usadas",
    "letras_acertadas",
    "fallos",
]

CLAVES_ADIVINA = [
    "numero_secreto",
    "intentos",
    "historial_jugadas",
    "juego_ganado",
    "jugada_actual",
    "start_time_adivina",
    "tiempo_partida",
]

CAMPOS_PARTIDAS_TORNEO = {
    "ahorcado": "juegos_ahorcado",
    "piedra": "juegos_piedra",
}

DIGITOS_VALIDOS = "1234567890"
LETRAS_VALIDAS_AHORCADO = "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"

# --- Funciones auxiliares ---

def opcion_pptls_valida(eleccion):
    """Verifica si la elección es una opción válida de PPTLS."""
    return isinstance(eleccion, str) and eleccion in OPCIONES_PPTLS

def letra_ahorcado_valida(letra):
    """Verifica si la letra es válida para el juego del ahorcado."""
    return (isinstance(letra, str) and len(letra) == 1 and letra in LETRAS_VALIDAS_AHORCADO)

def jugada_adivina_valida(jugada):
    """Verifica si la jugada es válida para el juego de adivina el número."""
    return isinstance(jugada, str) and len(set(jugada)) == 4 and all(digito in DIGITOS_VALIDOS for digito in jugada)

def es_fin_semana():
    """Comprueba si hoy es sábado o domingo.
    
    Returns:
        bool: True si hoy es sábado o domingo, False en caso contrario.
    """
    
    return timezone.localtime().weekday() >= 5  # 5 = sábado, 6 = domingo

def obtener_periodo_actual():
    """Devuelve el año ISO y la semana ISO actuales
    
    Returtns:
        tuple[int, int]: Año y semana actuales
    """
    fecha_actual = timezone.localdate()
    calendario = fecha_actual.isocalendar()
    return calendario.year, calendario.week

def obtener_anio_actual():
    """Devuelve el año ISO actual"""
    return obtener_periodo_actual()[0]

def obtener_semana_actual():
    """Devuelve la semana actual"""   
    return obtener_periodo_actual()[1]

def limpiar_sesion(request, claves):
    """Elimina un conjunto de claves de la sesión del usuario.

    Args:
        request (HttpRequest): El objeto de la solicitud.
        claves (list[str]): Una lista de claves a eliminar de la sesión.
    """
    for clave in claves:
        request.session.pop(clave, None)
        
def registrar_partida_libre(request, user, juego):
    """Registra una partida en el modo libre para un usuario y juego específicos.

    Args:
        request (HttpRequest): El objeto de la solicitud.
        user (User): El usuario que juega la partida.
        juego (str): Nombre del juego.
    """
    try:
        Partida.objects.create(user=user, juego=juego)
    except DatabaseError:
        messages.warning(request, "Hubo un error al registrar la partida")
        
# --- Funciones de torneo ---
        
def validar_participacion_torneo(request, juego):
    """Valida si un usuario puede jugar una partida de torneo para un juego.

    Args:
        request (HttpRequest): El objeto de la solicitud.
        juego (str): Nombre del juego a validar ('ahorcado', 'piedra').

    Returns:
        Torneo | None: El objeto de participación si la validación es exitosa,
                        de lo contrario, None.
    """
    anio_actual, semana_actual = obtener_periodo_actual()
    # Obtener la participación del usuario en el torneo de la semana actual.
    try:
        participacion = Torneo.objects.get(user=request.user,anio=anio_actual, semana=semana_actual)
    except Torneo.DoesNotExist:
        messages.error(request, "Debes estar apuntado en el torneo de esta semana para jugar en este modo")
        return None
        
    # Mapeo de juegos a sus campos en el modelo Torneo     
    campo_partida = CAMPOS_PARTIDAS_TORNEO.get(juego)
    
    # Verificar si se ha alcanzado el límite de partidas para el juego en el torneo.
    if campo_partida and getattr(participacion, campo_partida) >= MAX_PARTIDAS_TORNEO:
         messages.warning(request, f"Ya has jugado tus {MAX_PARTIDAS_TORNEO} partidas para el torneo de esta semana. Puedes jugar en el modo libre desde el menú de juegos")
         return None
        
    return participacion

def calcular_incrementos_torneo(juego, resultado):
    """Calcula los incrementos de puntos y partidas para una partida de torneo.

    Args:
        juego (str): Nombre del juego.
        resultado (str): Resultado de la partida.

    Returns:
        dict: Un diccionario con los incrementos de puntos y partidas.
    """
    incrementos = {
        ("ahorcado", "victoria"): {
            "puntos_ahorcado": PUNTOS_VICTORIA_AHORCADO,
            "juegos_ahorcado": 1
        },
        ("ahorcado", "derrota"): {
            "juegos_ahorcado": 1
        },
        ("piedra", "victoria"): {
            "puntos_piedra": PUNTOS_VICTORIA_PPTLS,
            "juegos_piedra": 1
        },
        ("piedra", "empate"): {
            "puntos_piedra": PUNTOS_EMPATE_PPTLS,
            "juegos_piedra": 1
        },
        ("piedra", "derrota"): {
            "juegos_piedra": 1
        },
        ("adivina", "victoria"): {
            "juegos_adivina": 1
        },
    }
    
    # Devolver una copia de los incrementos correspondientes al juego y resultado, si existen.
    if (juego, resultado) in incrementos:
        return incrementos[(juego, resultado)].copy()
    
    # Si no hay incrementos definidos para el juego y resultado, devolver un diccionario vacío.
    return incrementos.get((juego, resultado), {}).copy()

    

def aplicar_incrementos_torneo(participacion, juego, resultado):
    """Aplica los incrementos de puntos y partidas a la participación en el torneo.

    Args:
        participacion (Torneo): Instancia del modelo Torneo del usuario.
        juego (str): Nombre del juego.
        resultado (str): Resultado de la partida.

    Returns:
        bool: True si se aplicaron los incrementos correctamente, False si no se aplicaron debido a que se alcanzó el máximo de partidas.
    """
    incrementos = calcular_incrementos_torneo(juego, resultado)
    if not incrementos:
        return False
    
    campo_partida = CAMPOS_PARTIDAS_TORNEO.get(juego)
    
    # Bloque atómico para asegurar que las actualizaciones de la participación sean consistentes.
    with transaction.atomic():
        participacion_bloqueada = Torneo.objects.select_for_update().get(pk=participacion.pk)
    
        if campo_partida and getattr(participacion_bloqueada, campo_partida) >= MAX_PARTIDAS_TORNEO:
            return False

        # Aplicar los incrementos a los campos correspondientes de la participación bloqueada.
        for campo, valor in incrementos.items():
            valor_actual = getattr(participacion_bloqueada, campo) 
            setattr(participacion_bloqueada, campo, valor_actual + valor)
        
        participacion_bloqueada.save(update_fields=list(incrementos))

        # Actualizar los campos de la participación original con los valores de la participación bloqueada.
        for campo in incrementos:
            setattr(participacion, campo, getattr(participacion_bloqueada, campo))
        
    return True
        
def registrar_resultado_torneo(request, participacion_torneo, juego, resultado):
    """Registra el resultado de una partida en el torneo.
    
    Args:
        request (HttpRequest): El objeto de la solicitud.
        participacion_torneo (Torneo): Instancia del modelo Torneo del usuario.
        juego (str): Nombre del juego.
        resultado (str): Resultado de la partida.
    """
    try:
        resultado_registro = aplicar_incrementos_torneo(participacion_torneo, juego, resultado)
        
        if resultado_registro is False:
            messages.warning(request, "Has alcanzado el límite de partidas para esta juego")
    except (AttributeError, DatabaseError):
        messages.warning(request, "Hubo un error al registrar tu resultado en el torneo. La partida no ha contado para el torneo.")
        
def registrar_resultado_partida(request, partida_torneo, participacion_torneo, juego, resultado):
    """Registra el resultado de una partida específica.
    
    Args:
        request (HttpRequest): El objeto de la solicitud.
        partida_toreno (Partida): Instancia del modelo Partida del torneo.
        participacion_torneo (Torneo): Instancia del modelo Torneo del usuario.
        juego (str): Nombre del juego.
        resultado (str): Resultado de la partida.
    """
    if resultado is None:
        return
    
    if partida_torneo:
        registrar_resultado_torneo(request, participacion_torneo, juego, resultado)
    else:
        registrar_partida_libre(request, request.user, juego)
    
# ------------ JUEGO AHORCADO ----------

def get_palabra():
    """Selecciona y devuelve una palabra aleatoria de un archivo de diccionario.

    Returns:
        str | None: Una palabra en mayúsculas si se encuentra, o None si
                    ocurre un error (ej. archivo no encontrado).
    """
    try:
        # Creamos el nombre de un archivo aleatorio,
        num_letras = random.randint(4, 8)
        ruta_diccionario = os.path.join(settings.BASE_DIR, 'static', 'Diccionarios', f"dicc{num_letras}.dic")
                
        # Abrimos y leemos el archivo
        with open(ruta_diccionario, 'r', encoding='utf-8') as f:
            palabras = f.read().splitlines()
                    
        # Elegimos una palabra al azar del archivo
        return random.choice(palabras).upper()
    except (FileNotFoundError, IndexError):
        return None
    
def inicializar_ahorcado(session):
    """Inicializa o resetea el estado del juego del Ahorcado en la sesión.

    Args:
        session (SessionBase): El objeto de sesión de Django.

    Returns:
        dict | None: Un diccionario con el estado del juego inicializado, o
                     None si no se pudo obtener una palabra.
    """
    palabra_secreta = get_palabra()
    
    if not palabra_secreta:
        return None
    
    estado_juego = {
        "palabra_secreta": palabra_secreta,
        "letras_usadas": [],
        "letras_acertadas": [],
        "fallos": 0,
    }
    
    session.update(estado_juego)
    return estado_juego

def obtener_estado_ahorcado(request):
    """
    Obtiene el estado actual del juego del Ahorcado desde la sesión.
    
    Args:
        request (HttpRequest): El objeto de la solicitud.
        
    Returns:
        dict | None: Un diccionario con el estado del juego si existe, o None si no se pudo inicializar
    """
    
    if "palabra_secreta" not in request.session:
        if not inicializar_ahorcado(request.session):
            messages.error(request, "No se pudo iniciar el juego. Inténtalo de nuevo ")
            return None
        
    return{
        "palabra_secreta": request.session["palabra_secreta"],
        "letras_usadas": request.session.setdefault("letras_usadas", []),
        "letras_acertadas": request.session.setdefault("letras_acertadas", []),
        "fallos": request.session.setdefault("fallos", 0),
    }
    
def obtener_resultado_ahorcado(juego_ganado, juego_perdido):
    """Obtiene el resultado del juego del Ahorcado.
    
    Args:
        juego_ganado (bool): Indica si el juego fue ganado.
        juego_perdido (bool): Indica si el juego fue perdido.
        
    Returns:
        str | None: "victoria" si el juego fue ganado, "derrota" si fue perdido, o None si el juego no ha terminado.
    """
    if juego_ganado:
        return "victoria"
    
    elif juego_perdido:
        return "derrota"
    
    return None

def procesar_jugada_ahorcado(request, partida_torneo, participacion_torneo):
    """Procesa la jugada del usuario en el juego del Ahorcado.
    
    Args:
        request (HttpRequest): El objeto de la solicitud.
        partida_torneo (bool): Indica si la partida es en modo torneo.
        participacion_torneo (Torneo | None): La participación en el torneo, si aplica.
        
    Returns:
        dict: Un diccionario con el estado actualizado del juego, incluyendo
              la palabra secreta, letras usadas, letras acertadas, fallos,
              intentos restantes y flags de victoria/derrota.
    """
    
    estado = obtener_estado_ahorcado(request)
    if estado is None:
        return {"redirigir": "juegos:ahorcado"}
    
    palabra = estado["palabra_secreta"]
    letras_usadas = estado["letras_usadas"]
    letras_acertadas = estado["letras_acertadas"]
    fallos = estado["fallos"]
    
    juego_ganado_actual = set(palabra) <= set(letras_acertadas)
    juego_perdido_actual = fallos >= MAX_FALLOS_AHORCADO
    
    # Si el juego ya ha sido ganado o perdido, devolvemos el estado actual sin procesar nuevas jugadas.
    if juego_ganado_actual or juego_perdido_actual:
        return {
            "primera_vez": False,
            "palabra": palabra,
            "letras_usadas": letras_usadas,
            "letras_acertadas": letras_acertadas,
            "fallos": fallos,
            "intentos_restantes": MAX_FALLOS_AHORCADO - fallos,
            "juego_ganado": juego_ganado_actual,
            "juego_perdido": juego_perdido_actual,
            "partida_torneo": partida_torneo,
            "participacion_torneo": participacion_torneo,
        }
    
    letra = request.POST.get("letra", "").upper()
    # Una petición manipulada no debe modificar la sesión ni el marcador
    if letra and not letra_ahorcado_valida(letra):
        messages.error(request, "La letra seleccionada no es válida")
        letra = ""
    
    juego_ganado = False
    juego_perdido = False
        
    if letra and (len(letra) != 1 and not letra_ahorcado_valida(letra)):
        messages.error(request, "La letra seleccionada no es válida")
        letra = ""
    
    # Si se envía una letra válida, procesamos la jugada
    if letra and letra not in letras_usadas:
        letras_usadas.append(letra)
        if letra in palabra:
            letras_acertadas.append(letra)
        else:
            fallos += 1
        
        request.session["letras_usadas"] = letras_usadas
        request.session["letras_acertadas"] = letras_acertadas
        request.session["fallos"] = fallos
        
        # Comprobamos si el juego ha terminado
        juego_ganado = set(palabra) <= set(letras_acertadas)
        juego_perdido = fallos >= MAX_FALLOS_AHORCADO
    
    resultado = obtener_resultado_ahorcado(juego_ganado, juego_perdido)
        
    registrar_resultado_partida(request, partida_torneo, participacion_torneo, "ahorcado", resultado)
        
    return {
        "primera_vez": False,
        "palabra": palabra,
        "letras_usadas": letras_usadas,
        "letras_acertadas": letras_acertadas,
        "fallos": fallos,
        "intentos_restantes": MAX_FALLOS_AHORCADO - fallos,
        "juego_ganado": juego_ganado,
        "juego_perdido": juego_perdido,
        "partida_torneo": partida_torneo,
        "participacion_torneo": participacion_torneo,
    }
    
def registrar_resultado_ahorcado(request, partida_torneo, participacion_torneo, juego_ganado, juego_perdido):
    """Registra el resultado de una partida de Ahorcado, ya sea en modo torneo o libre.

    Args:
        request (HttpRequest): El objeto de la solicitud.
        partida_torneo (bool): Indica si la partida es en modo torneo.
        participacion_torneo (ParticipacionTorneo): La participación en el torneo.
        juego_ganado (bool): Indica si el jugador ganó la partida.
        juego_perdido (bool): Indica si el jugador perdió la partida.
        
    Returns:
        None
    """
    
    resultado = obtener_resultado_ahorcado(juego_ganado, juego_perdido)
    registrar_resultado_partida(request, partida_torneo, participacion_torneo, "ahorcado", resultado)
        
def procesar_ahorcado_request(request, partida_torneo, participacion_torneo):
    """Procesa la solicitud del juego de Ahorcado, manejando tanto GET como POST.

    Args:
        request (HttpRequest): El objeto de la solicitud.
        partida_torneo (bool): Indica si la partida es en modo torneo.
        participacion_torneo (ParticipacionTorneo): La participación en el torneo.

    Returns:
        dict: Un diccionario con el estado del juego y la información relevante.
    """
    # Si es la primera vez que se entra se reinicia el juego
    if request.method == "GET":
        # Limpiamos los datos de la partida anterior
        limpiar_sesion(request, ["palabra_secreta", "letras_usadas", "letras_acertadas", "fallos"])
        return {"primera_vez": True, "partida_torneo": partida_torneo, "participacion_torneo": participacion_torneo}
                
    if request.method == "POST":
        if "volver_jugar" in request.POST:
            # Si se pulsa "volver a jugar" se reinicia el juego
            limpiar_sesion(request, ["palabra_secreta", "letras_usadas", "letras_acertadas", "fallos"]) 

        return procesar_jugada_ahorcado(request, partida_torneo, participacion_torneo)
    
    return {"primera_vez": True, "partida_torneo": partida_torneo, "participacion_torneo": participacion_torneo}

# ------------ JUEGO Piedra-Papel-Tijera-Lagarto-Spock ----------

def determinar_resultado_pptls(jugador, cpu):
    """Determina el resultado de una partida de PPTLS.

    Args:
        jugador (str): La elección del jugador ('piedra', 'papel', ...).
        cpu (str): La elección aleatoria de la CPU.

    Returns:
        str: 'victoria', 'derrota' o 'empate'.
    """

    if jugador == cpu:
        return "empate"
    
    if cpu in REGLAS_PPTLS.get(jugador, []):
        return "victoria"

    return "derrota"
    
def personalizar_mensaje(jugador, cpu):
    """Devuelve el mensaje explicativo de una jugada de PPTLS.

    Args:
        jugador (str): La elección del jugador.
        cpu (str): La elección de la CPU.

    Returns:
        str: El mensaje descriptivo de la jugada.
    """
    return MENSAJES_PPTLS.get((jugador, cpu)) or MENSAJES_PPTLS.get((cpu, jugador))

def actualizar_marcador_pptls(session, resultado):
    """Actualiza y devuelve el marcador del juego PPTLS en la sesión.

    Args:
        session (SessionBase): El objeto de sesión de Django.
        resultado (str): 'victoria', 'derrota' o 'empate'.

    Returns:
        dict: Un diccionario con el número de 'victorias', 'derrotas' y 'empates'.
    """
    marcador = {
        "victorias": session.get("victorias", 0),
        "derrotas": session.get("derrotas", 0),
        "empates": session.get("empates", 0),
    }
    if resultado == "victoria":
        marcador["victorias"] += 1
    elif resultado == "derrota":
        marcador["derrotas"] += 1
    elif resultado == "empate":
        marcador["empates"] += 1
        
    session.update(marcador)
    return marcador

def registrar_resultado_pptls(request, partida_torneo, participacion_torneo, resultado):
    """
    Registra el resultado de una partida de PPTLS.
    
    Args:
        request (HttpRequest): El objeto de la solicitud.
        partida_torneo (bool): True si la partida es de torneo, False si es libre.
        participacion_torneo (Torneo | None): La instancia de participación en el torneo, si aplica.
        resultado (str): El resultado de la partida ('victoria', 'derrota', 'empate').
    """
    if resultado is None:
        return
    if partida_torneo:
        registrar_resultado_partida(request, partida_torneo, participacion_torneo, "piedra", resultado)
    else:
        registrar_resultado_partida(request, partida_torneo, participacion_torneo, "pptls", resultado) 
        
def procesar_pptls_request(request, partida_torneo, participacion_torneo):
    """Procesa la solicitud para el juego PPTLS, manejando tanto GET como POST.

    Args:
        request (HttpRequest): El objeto de la solicitud.
        partida_torneo (bool): True si la partida es de torneo, False si es libre.
        participacion_torneo (Torneo | None): La instancia de participación en el torneo, si aplica.
        
    Returns:
        dict: Un diccionario con el contexto necesario para renderizar la plantilla,
              incluyendo el estado del juego y la información de la partida.
    """
    if request.method == "GET":
        if not partida_torneo:
            limpiar_sesion(request, ["victorias", "derrotas", "empates", "partidas_jugadas"])
            
        return {"primera_vez": True, "partida_torneo": partida_torneo, "participacion_torneo": participacion_torneo}
    
    if request.method == "POST":
        # Procesar la jugada del jugador y determinar el resultado.
        eleccion_jugador = request.POST.get("eleccion")
        if not opcion_pptls_valida(eleccion_jugador):
            messages.error(request, "La jugada seleccionada no es válida")
            return {"primera_vez": False, "partida_torneo": partida_torneo, "participacion_torneo": participacion_torneo}
              
        eleccion_cpu = random.choice(OPCIONES_PPTLS)
        resultado = determinar_resultado_pptls(eleccion_jugador, eleccion_cpu)
        mensaje = personalizar_mensaje(eleccion_jugador, eleccion_cpu)
            
        registrar_resultado_pptls(request, partida_torneo, participacion_torneo, resultado)
            
        marcador = actualizar_marcador_pptls(request.session, resultado)
            
        return {
            "primera_vez": False,
            "victorias": request.session.get("victorias", marcador["victorias"]),
            "derrotas": request.session.get("derrotas", marcador["derrotas"]),
            "empates": request.session.get("empates", marcador["empates"]),
            "partidas_jugadas": sum(marcador.values()),
            "resultado": resultado,
            "eleccion_jugador": eleccion_jugador,
            "eleccion_cpu": eleccion_cpu,
            "mensaje": mensaje,
            "partida_torneo": partida_torneo,
            "participacion_torneo": participacion_torneo,
        }
        
    return {"primera_vez": True, "partida_torneo": partida_torneo, "participacion_torneo": participacion_torneo}
        
        
# ------------ JUEGO ADIVINA EL NUMERO -----------

def generar_numero_secreto():
    """Genera un número secreto de 4 dígitos únicos.

    Returns:
        list[str]: Una lista de 4 strings, cada uno un dígito único.
    """
    return [str(d) for d in random.sample(range(10), 4)]

def validar_participacion_adivina(request):
    """Valida si un usuario puede participar en el evento de 'Adivina el Número'.

    Args:
        request (HttpRequest): El objeto de la solicitud.

    Returns:
        tuple[Torneo | None, str | None]: Una tupla con el objeto de
            participación y una URL de redirección. Si la validación es exitosa,
            la URL es None. Si falla, el objeto de participación es None.
    """
    hoy = timezone.localdate()
    anio_actual, semana_actual = obtener_periodo_actual()
    
    # Comprobamos si es sábado
    if hoy.weekday() != 5:
        messages.error(request, "El juego 'Adivina el Número' sólo está disponible los sábados en el modo torneo")
        return None, "torneo:torneo"
    
    # Comprobamos si el usuario está en el top10 (considerando empates)
    ranking_semanal = Torneo.objects.filter(anio= anio_actual, semana=semana_actual).annotate(
        total_puntos = F("puntos_ahorcado") + F("puntos_piedra")
        ).order_by("-total_puntos")
    
    usuarios_top10 = []
    puesto = 1
    for i, participante in enumerate(ranking_semanal):
        # Actualizamos el puesto considerando empates.
        if i > 0 and participante.total_puntos < ranking_semanal[i-1].total_puntos:
            puesto += 1
        if puesto <= 10:
            usuarios_top10.append(participante.user.id)
        else:
            break
            
    if request.user.id not in usuarios_top10:
        messages.error(request, "Debes estar en el top10 del torneo semanal para participar en este modo del juego")
        return None, "torneo:torneo"
    
    try:
        participacion_torneo = Torneo.objects.get(user=request.user, anio=anio_actual, semana=semana_actual)
    except Torneo.DoesNotExist:
        messages.error(request, "Debes estar clasificado para jugar en este modo del juego")
        return None, "torneo:torneo"
    
    if participacion_torneo.juegos_adivina >= 10: # Sólo 1 participación por semana
                messages.warning(request, "Ya has jugado las 10 partidas, tu mejor puntuación a quedado registrada ¡Mucha suerte!")
                return None, "torneo:torneo"
    
    return participacion_torneo, None
    
def inicializar_partida_adivina(session):
    """Inicializa el estado para una nueva partida de 'Adivina el Número' en la sesión.

    Args:
        session (SessionBase): El objeto de sesión de Django.
    """
    session.update({
        "numero_secreto": generar_numero_secreto(),
        "intentos": 0,
        "historial_jugadas": [],
        "juego_ganado": False,
        "jugada_actual": "",
        "start_time_adivina": None,
        "tiempo_partida": None
    })
    
def manejar_teclado_adivina(session, post_data):
    """Gestiona la entrada del teclado virtual y actualiza la jugada actual en la sesión.

    Args:
        session (SessionBase): El objeto de sesión de Django.
        post_data (QueryDict): El diccionario request.POST.

    Returns:
        str: La cadena de la jugada actual actualizada.
    """
    jugada_actual = session.get("jugada_actual", "")
    
    if "digito" in post_data and len(jugada_actual) < 4:
        # Añadimos el dígito a la jugada actual si es válido.
        digito = post_data.get("digito", "")
        
        # Nos aseguramos de que el dígito sea válido antes de añadirlo a la jugada actual.
        if (len(digito) == 1 and digito in DIGITOS_VALIDOS and digito not in jugada_actual):
            jugada_actual += digito
            
            # Si es la primera jugada, registramos el tiempo de inicio de la partida.
            if len(jugada_actual) == 1 and not session.get("start_time_adivina"):
                session["start_time_adivina"] = time.time()
                
    elif "accion" in post_data:
        accion = post_data.get("accion")
        
        if accion == "borrar":
            jugada_actual = jugada_actual[:-1]
        elif accion == "limpiar":
            jugada_actual = ""
    
    session["jugada_actual"] = jugada_actual
    return jugada_actual

def procesar_jugada_adivina(numero_secreto, jugada_actual):
    """Compara la jugada del usuario con el número secreto y calcula aciertos y coincidencias.

    Args:
        numero_secreto (list[str]): Lista de strings con el número a adivinar.
        jugada_actual (str): Cadena de 4 dígitos enviada por el usuario.

    Returns:
        dict: Un diccionario con el resultado detallado de la jugada,
            incluyendo aciertos, coincidencias y el estado de cada dígito.
    """
    aciertos, coincidencias = 0, 0
    resultado_digitos = []
    
    for i, digito in enumerate(jugada_actual):
        estado = "incorrecto"
        if digito in numero_secreto:
            # Verificamos si el dígito está en la posición correcta.
            if digito == numero_secreto[i]:
                estado = "acierto"
                aciertos += 1
            else:
                estado = "coincidencia"
                coincidencias += 1
        resultado_digitos.append({"digito": digito, "estado": estado})
    
    return {
        "jugada": jugada_actual,
        "aciertos": aciertos,
        "coincidencias": coincidencias,
        "resultado_digitos": resultado_digitos,
    }
    
def actualizar_puntuacion_torneo_adivina(participacion, intentos, tiempo_partida):
    """
    Actualiza la puntuación del usuario en el torneo para el juego 'Adivina el Número'.

    Args:
        participacion (Torneo): Instancia del modelo Torneo del usuario.
        intentos (int): Número de intentos de la partida actual.
        tiempo_partida (int): Tiempo en segundos de la partida actual.

    Returns:
        bool: True si se aplicaron los cambios correctamente, False si no se aplicaron debido a que se alcanzó el máximo de partidas o los valores son inválidos.
    """
    if not isinstance(intentos, int) or intentos <= 0:
        return False
    
    if not isinstance(tiempo_partida, (int, float)):
        return False
    
    if tiempo_partida <= 0:
        return False
    
    # Bloqueamos la participación para evitar que otros procesos la modifiquen simultáneamente.
    with transaction.atomic():
        participacion_bloqueada = (
            Torneo.objects.select_for_update().get(pk=participacion.pk)
        )
        
        # Verificamos si el usuario ya alcanzó el máximo de partidas permitidas en el torneo.
        if participacion_bloqueada.juegos_adivina >= MAX_PARTIDAS_TORNEO:
            return False
        
        participacion_bloqueada.juegos_adivina += 1
        
        mejor_puntuacion = (
            participacion_bloqueada.intentos_adivina == 0
            or intentos < participacion_bloqueada.intentos_adivina
            or (
                intentos == participacion_bloqueada.intentos_adivina
                and (
                    participacion_bloqueada.tiempo_adivina == 0
                    or tiempo_partida < participacion_bloqueada.tiempo_adivina
                )
            )
        )
        
        if mejor_puntuacion:
            participacion_bloqueada.intentos_adivina = intentos
            participacion_bloqueada.tiempo_adivina = tiempo_partida
            
        participacion_bloqueada.save(
            update_fields=["juegos_adivina", "intentos_adivina", "tiempo_adivina"]
        )
        
        # Actualizamos la instancia original con los valores bloqueados para mantener la coherencia en la sesión.
        participacion.juegos_adivina = participacion_bloqueada.juegos_adivina
        participacion.intentos_adivina = participacion_bloqueada.intentos_adivina
        participacion.tiempo_adivina = participacion_bloqueada.tiempo_adivina
        
    return True
   
def reiniciar_partida_adivina(request):
    """Reinicia la partida del juego 'Adivina el Número' en la sesión del usuario.
    
    Args:
        request (HttpRequest): El objeto de la solicitud.
    """
    limpiar_sesion(request, CLAVES_ADIVINA)
    inicializar_partida_adivina(request.session)
    
def procesar_adivina_request(request, partida_torneo, participacion_torneo, teclado):
    """Procesa la solicitud para el juego 'Adivina el Número', manejando tanto GET como POST.
    
    Args:
        request (HttpRequest): El objeto de la solicitud.
        partida_torneo (bool): Indica si la partida es en modo torneo.
        participacion_torneo (Torneo | None): La participación en el torneo, si aplica.
        teclado (list[list[str]]): Representación del teclado virtual para el juego.
        
    Returns:
        dict: Un diccionario con el contexto necesario para renderizar la plantilla, incluyendo el estado del juego y la información de la partida.
    """
    if request.method == "GET":
        limpiar_sesion(request, CLAVES_ADIVINA)
        
        return {
            "primera_vez": True,
            "partida_torneo": partida_torneo,
            "participacion_torneo": participacion_torneo,
            "teclado": teclado,
        }
    
    if request.method == "POST":
        if "volver_jugar" in request.POST:
            reiniciar_partida_adivina(request)
            
        if "numero_secreto" not in request.session:
            inicializar_partida_adivina(request.session)
            
        if request.session.get("juego_ganado", False):
            # Si el juego ya ha sido ganado, devolvemos inmediatamente el estado actual del juego.
            return {
            "primera_vez": False,
            "intentos": request.session.get("intentos", 0),
            "historial_jugadas": request.session.get("historial_jugadas", []),
            "juego_ganado": True,
            "partida_torneo": partida_torneo,
            "participacion_torneo": participacion_torneo,
            "jugada_actual": "",
            "teclado": teclado,
            "tiempo_partida": request.session.get("tiempo_partida"),
            "start_time_adivina": request.session.get("start_time_adivina")
        }
            
        jugada_actual = manejar_teclado_adivina(request.session, request.POST)
        
        # Guardamos la jugada actual en la sesión para mantener el estado del juego.
        if request.POST.get("accion") == "enviar" and len(jugada_actual) == 4:
            if not jugada_adivina_valida(jugada_actual):
                messages.error(request, "La jugada debe contener cuatro dígitos distintos")
                                    
                request.session["jugada_actual"] = ""
                                    
                return {
                    "primera_vez": False,
                    "intentos": request.session.get("intentos", 0),
                    "historial_jugadas": request.session.get("historial_jugadas", []),
                    "juego_ganado": request.session.get("juego_ganado", False),
                    "partida_torneo": partida_torneo,
                    "participacion_torneo": participacion_torneo,
                    "tiempo_partida": request.session.get("tiempo_partida"),
                    "start_time_adivina": request.session.get("start_time_adivina")
                    }
            request.session["intentos"] += 1

            numero_secreto = request.session["numero_secreto"]
            resultado_jugada = procesar_jugada_adivina(numero_secreto, jugada_actual)
            request.session["historial_jugadas"].append(resultado_jugada)

            # Verificamos si la jugada actual ha resultado en un juego ganado.
            if resultado_jugada["aciertos"] == 4:
                request.session["juego_ganado"] = True
                
                # Si el juego ha sido ganado, calculamos el tiempo de la partida si aún no se ha hecho.
                if request.session.get("start_time_adivina"):
                    request.session["tiempo_partida"] = round(
                        time.time() - request.session["start_time_adivina"], 2,
                    )
                    
                if partida_torneo:
                    actualizar_puntuacion_torneo_adivina(
                        participacion_torneo,
                        request.session["intentos"],
                        request.session["tiempo_partida"],
                    )
                else:
                    registrar_partida_libre(request, request.user, "adivina")
                    
            request.session["jugada_actual"] = ""
            
        request.session.modified = True
        
        return {
            "primera_vez": False,
            "intentos": request.session.get("intentos", 0),
            "historial_jugadas": request.session.get("historial_jugadas", []),
            "juego_ganado": request.session.get("juego_ganado", False),
            "partida_torneo": partida_torneo,
            "participacion_torneo": participacion_torneo,
            "jugada_actual": request.session.get("jugada_actual", ""),
            "teclado": teclado,
            "tiempo_partida": request.session.get("tiempo_partida"),
            "start_time_adivina": request.session.get("start_time_adivina")
        }

    return {
        "primera_vez": True,
        "partida_torneo": partida_torneo,
        "participacion_torneo": participacion_torneo,
        "teclado": teclado,
    }
    