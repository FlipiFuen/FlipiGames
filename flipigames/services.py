from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, login, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDay
from django.utils import timezone

from juegos.models import Partida
from torneo.models import Torneo
from torneo.services import get_periodo_actual
from .charts import crear_grafico_barras, crear_grafico_lineas, generar_graficos_perfil
from .forms import FormularioCambiarEmail, FormularioRegistroUsuario

# Creamos una función para devolver estadísticas vacías, para evitar repetir código en caso de error o ausencia de datos.
def estadisticas_vacias():
    """Devuelve un diccionario con estadísticas vacías.
    Returns:
        dict: Un diccionario con todas las estadísticas inicializadas a cero o None.
    """
    return {
        "total_partidas": 0,
        "semanas_participadas": 0,
        "mejor_ahorcado": None,
        "mejor_piedra": None,
        "mejor_adivina": None,
        "torneos_ganados": 0,
    }
    
def registrar_usuario(request):
    """Procesa el formulario de registro de usuario.
    
    Args:
        request: El objeto HttpRequest que contiene los datos del POST.
        
        Returns:
            dict: Un diccionario con el resultado del registro.
    """
    form = FormularioRegistroUsuario(request.POST)
    
    if not form.is_valid():
        # Si el formulario no es válido, se vuelve a renderizar la página con los errores.
        return {"ok": False, "form": form}
        
    try:
        usuario = form.save()
                    
        # Autentificamos al usuario
        if usuario is not None:
            login(request, usuario)
                        
        messages.success(request, f"¡Bienvenid@ { usuario.username }! Tu cuenta ha sido creada con éxito. Esperamos que disfrutes de nuestros juegos")
        return {"ok": True}
    
    except DatabaseError:
        messages.error(request, "Ha ocurrido un error con la base de datos durante el registro. Por favor, inténtalo de nuevo")
        # Si hay un error, también volvemos a mostrar el formulario.
        return {"ok": False, "form": form}

# ----- Funciones de Perfil y Estadisticas de Usuario

def calcular_estadisticas_usuario(registros):
    """Calcula las estadísticas del usuario a partir de sus registros de torneo.

    Args:
        registros: Un QuerySet de objetos Torneo del usuario.

    Returns:
        Un diccionario con las estadísticas calculadas.
    """
    try:
        if not registros.exists():
            return estadisticas_vacias()
        
        # Mejor puntuación en Ahorcado
        mejor_ahorcado_reg = registros.filter(puntos_ahorcado__gt=0).order_by("-puntos_ahorcado").first()
        
        # Mejor puntuación en Piedra-Papel-Tijera-Lagarto-Spock
        mejor_piedra_reg = registros.filter(puntos_piedra__gt=0).order_by("-puntos_piedra").first()
        
        # Mejor puntuación en Adivina el Número
        mejor_adivina_reg = registros.filter(juegos_adivina__gt=0, intentos_adivina__gt=0).order_by("intentos_adivina", "tiempo_adivina").first()
        
        # Contar torneos ganados
        torneos_ganados = 0
        usuario_id = registros.values_list("user_id", flat=True).first()
        periodos = registros.values_list("anio", "semana").distinct()
        
        for anio, semana in periodos:
            # Comprobamos para cada semana si el usuario fue el campeón
            campeon_periodo = (
                Torneo.objects.filter(
                anio=anio, 
                semana=semana, 
                juegos_adivina__gt=0, 
                intentos_adivina__gt=0
                ).order_by("intentos_adivina", "tiempo_adivina", "user__username").first()
            )
            if campeon_periodo and campeon_periodo.user_id == usuario_id:
                torneos_ganados += 1
    
        estadisticas = {
            "total_partidas": registros.aggregate(
                total = Sum(Coalesce("juegos_ahorcado", 0) + Coalesce("juegos_piedra", 0) + Coalesce("juegos_adivina", 0))
            )["total"] or 0,
            "semanas_participadas": registros.count(),
            "mejor_ahorcado": {
                "puntos": mejor_ahorcado_reg.puntos_ahorcado,
                "semana": mejor_ahorcado_reg.semana,
                "anio": mejor_ahorcado_reg.anio,
            } if mejor_ahorcado_reg else None,
            "mejor_piedra": {
                "puntos": mejor_piedra_reg.puntos_piedra,
                "semana": mejor_piedra_reg.semana,
                "anio": mejor_piedra_reg.anio,
            } if mejor_piedra_reg else None,
            "mejor_adivina": {
                "intentos": mejor_adivina_reg.intentos_adivina,
                "tiempo": mejor_adivina_reg.tiempo_adivina,
                "semana": mejor_adivina_reg.semana,
                "anio": mejor_adivina_reg.anio,
            } if mejor_adivina_reg else None,
            "torneos_ganados": torneos_ganados,
        }
        
        return estadisticas
    except (AttributeError, DatabaseError):
        # Si algo falla, devolvemos estadísticas vacías para evitar un crash
        return estadisticas_vacias()
        
def cambiar_email(request):
    """Procesa el formulario de cambio de email.

    Args:
        request: El objeto HttpRequest que contiene los datos del POST.

    Returns:
        True si el formulario es válido y el email se ha guardado.
        El objeto de formulario con errores si la validación falla.
    """
    form_email = FormularioCambiarEmail(request.POST, instance=request.user)
    if form_email.is_valid():
        form_email.save()
        messages.success(request, "Tu correo ha sido actualizado correctamente")
        return True
    
    return form_email

def cambiar_password(request):
    """Procesa el formulario de cambio de contraseña.

    Args:
        request: El objeto HttpRequest que contiene los datos del POST.

    Returns:
        True si el formulario es válido y la contraseña se ha cambiado.
        El objeto de formulario con errores si la validación falla.
    """
    form_password = PasswordChangeForm(user=request.user, data=request.POST)
    if form_password.is_valid():
        user = form_password.save()
        update_session_auth_hash(request, user) # Mantiene la sesión iniciada
        messages.success(request, "Tu contraseña ha sido actualizada con éxito")
        return True
    
    return form_password

def borrar_cuenta(request):
    """Procesa la eliminación de la cuenta de un usuario.

    Verifica la contraseña proporcionada. Si es correcta, cierra la sesión
    del usuario y elimina su cuenta de la base de datos.

    Args:
        request: El objeto HttpRequest.

    Returns:
        True si la cuenta fue eliminada, False si la contraseña es incorrecta.
    """
    password = request.POST.get("password")
    usuario = request.user
    
    if not usuario.check_password(password):
        messages.error(request, "La contraseña es incorrecta. No se ha podido eliminar la cuenta")
        return False
    
    logout(request)
    usuario.delete()
    messages.success(request, "Tu cuenta ha sido eliminada permanentemente con éxito")
    return True

def procesar_ajustes_cuenta(request):
    """Procesa los ajustes de la cuenta del usuario, incluyendo cambio de email, cambio de contraseña y eliminación de la cuenta.
    
    Args:
        request: El objeto HttpRequest que contiene los datos del POST.
        
    Returns:
        dict: Un diccionario con el resultado del procesamiento.
    """
    form_email = FormularioCambiarEmail(instance=request.user)
    form_password = PasswordChangeForm(user=request.user)
    
    if request.method != "POST":
        return {"redirect": None, "form_email": form_email, "form_password": form_password}
    
    accion = request.POST.get("accion")
    
    try:
        # Cambiar email
        if accion == "actualizar_email":
            resultado = cambiar_email(request)
            if resultado is True:
                return {"redirect": "flipigames:ajustes_cuenta"}
            return {"redirect": None, "form_email": resultado, "form_password": form_password}
                        
        # Cambiar contraseña
        elif accion == "actualizar_password":
            resultado = cambiar_password(request)
            if resultado is True:
                return {"redirect": "flipigames:ajustes_cuenta"}
            return {"redirect": None, "form_email": form_email, "form_password": resultado}
        
        # Darse de baja
        elif accion == "borrar_cuenta":
            if borrar_cuenta(request):
                return {"redirect": "flipigames:home"}
            return {"redirect": "flipigames:ajustes_cuenta", "form_email": form_email, "form_password": form_password}
        
    except DatabaseError:
        messages.error(request, "Ha ocurrido un error con la base de datos. Inténtalo de nuevo")
    
    return {"redirect": None, "form_email": form_email, "form_password": form_password}

def obtener_contexto_perfil(request):    
    """Obtiene el contexto necesario para renderizar la página de perfil del usuario.
    
    Args:
        request: El objeto HttpRequest.
        
    Returns:
        dict: Un diccionario con el contexto necesario para renderizar la página de perfil.
    """
    registros_torneo = Torneo.objects.filter(user=request.user)
    estadisticas_totales = calcular_estadisticas_usuario(registros_torneo)
    graficas = generar_graficos_perfil(registros_torneo)
    
    return {
        "estadisticas": estadisticas_totales,
        "grafica_partidas": graficas[0],
        "grafica_puntos": graficas[1],
        "grafica_evolucion": graficas[2],
    }
    
# ----- Administración

def obtener_usuarios_nuevos_por_dia():
    """
    Obtiene la cantidad de nuevos usuarios registrados por día en los últimos 30 días.
    
    Returns:
        Un QuerySet con los días y la cantidad de usuarios registrados en cada día.
    """
    
    fecha_inicio = timezone.now() - timedelta(days=30)
    
    return(
        User.objects.filter(date_joined__gte=fecha_inicio)
        .annotate(date=TruncDay("date_joined"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    
def obtener_participantes_por_semana():
    """Devuelve número de participantes por semana"""
    
    return(Torneo.objects.values("anio", "semana").annotate(count=Count("user", distinct=True)).order_by("anio", "semana"))
    
def obtener_juegos_libres_conteo():
    """Devuelve nombres y totales de juegos jugados en modo libre"""
    nombres_juegos = {
        "ahorcado": "Ahorcado",
        "pptls": "PPTLS",
        "adivina": "Adivina el Número"
    }
    juegos_libres = Partida.objects.values("juego").annotate(total=Count("id")).order_by("-total")
    conteos = {juego: 0 for juego in nombres_juegos}
    
    for item in juegos_libres:
        juego = item.get("juego")
        if juego in conteos:
            conteos[juego] = item["total"]
            
    if not any(conteos.values()):
        return None, None
    
    return(
        [nombres_juegos[juego] for juego in conteos.keys()],
        [conteos[juego] for juego in conteos.keys()],
    )
    
def obtener_campeon_global():
    """
    Devuelve el usuario con más torneos ganados y su número de victorias
    
    Returns: 
        Un diccionario con usuario y victorias, o None si no hay datos
    """
    
    try:
        periodos = Torneo.objects.values_list("anio", "semana").distinct()
        conteo_victorias = {}
        
        for anio, semana in periodos:
            campeon = (
                Torneo.objects.filter(anio=anio, semana=semana, juegos_adivina__gt=0, intentos_adivina__gt=0).order_by("intentos_adivina", "tiempo_adivina").first()
            )
            if campeon:
                usuario = campeon.user
                conteo_victorias[usuario] = conteo_victorias.get(usuario, 0) + 1
                
        if not conteo_victorias:
            return None
        
        campeon_global = max(conteo_victorias, key=conteo_victorias.get)
        
        return {
            "usuario": campeon_global,
            "victorias": conteo_victorias[campeon_global]
        }
    except DatabaseError:
        return None
    
def obtener_contexto_admin(request):
    """Obtiene el contexto necesario para renderizar la página de administración con estadísticas generales.
    
    Args:
        request: El objeto HttpRequest que contiene los datos del POST.
    
    Returns:
        dict: Un diccionario con el contexto necesario para renderizar la página de administración.
    """
    
    # Inicializamos el contexto con valores por defecto para evitar errores en caso de fallo de la base de datos
    contexto = {
        "total_usuarios": 0,
        "total_participaciones": 0,
        "anio_actual": 0,
        "semana_actual": 0,
        "participaciones_actuales": 0,
        "total_semanas": Torneo.objects.values("anio", "semana").distinct().count(),
        "campeon_global": None,
        "grafico_usuarios": None,
        "grafico_torneos": None,
        "grafico_juegos_libres": None,
    }
    
    # Estadísticas Generales
    total_usuarios = User.objects.count()
    total_participaciones = Torneo.objects.count()
    total_semanas = Torneo.objects.values("anio", "semana").distinct().count()
    campeon_global = obtener_campeon_global()
    anio_actual, semana_actual = get_periodo_actual()
    participaciones_actuales = Torneo.objects.filter(anio=anio_actual, semana=semana_actual).count()
            
    # Gráfico Nuevos Usuarios por Día (últimos 30 días)
    usuarios_dia = obtener_usuarios_nuevos_por_dia()
            
    if usuarios_dia:
        fechas = [registro["date"].strftime("%d-%Mm") for registro in usuarios_dia]
        conteos = [registro['count'] for registro in usuarios_dia]
        contexto["grafico_usuarios"] = crear_grafico_lineas(
            fechas,
            conteos,
            "Nuevos Usuarios por Dia (últimos 30 días)",
            "Fecha",
            "Nuevos Usuarios",
                )
                
    # Gráfico Registro en Torneos por Semana
    registros_semana = obtener_participantes_por_semana()
            
    if registros_semana:
        semanas = [f"Semana {registro['semana']}/{registro['anio']}" for registro in registros_semana]
        conteos = [registro['count'] for registro in registros_semana]
        contexto["grafico_torneos"] = crear_grafico_barras(
            semanas,
            conteos,
            "Participantes en Torneos por Semana",
            "Semana",
            "Participantes",
        )
                
    # Gráfico juegos más jugados en modo libre
    nombres_juegos, valores_juegos = obtener_juegos_libres_conteo()
        
    if nombres_juegos and valores_juegos:
        contexto["grafico_juegos_libres"] = crear_grafico_barras(
            nombres_juegos,
            valores_juegos,
            "Juegos Más Jugados Modo Libre",
            "Juegos",
            "Total de Partidas",
            ["#4e73df", "#1cc88a", "#36b9cc"],
            figsize = (10, 6),
        )
                
    contexto.update( 
        {
            "anio_actual": anio_actual,
            "semana_actual": semana_actual,
            "participaciones_actuales": participaciones_actuales,
            "total_usuarios": total_usuarios,
            "total_participaciones": total_participaciones,
            "total_semanas": total_semanas,
            "campeon_global": campeon_global,
        }
    )
    
    return contexto