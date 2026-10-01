
from django.shortcuts import render, redirect
from django.contrib import messages 
from django.contrib.auth.decorators import login_required 
from django.contrib.auth.forms import PasswordChangeForm
from django.db import DatabaseError

from . import services
from .forms import FormularioCambiarEmail, FormularioRegistroUsuario

# ----- Vista básica
def home(request):
    """Renderiza la página de inicio (home).

    Args:
        request: El objeto HttpRequest.

    Returns:
        Un HttpResponse que renderiza la plantilla 'flipigames/home.html'.
    """
    return render(request, 'flipigames/home.html')

def registro(request):
    """Gestiona el registro de un nuevo usuario.

    Args:
        request: El objeto HttpRequest.

    Returns:
        Un HttpResponse que redirige al home tras un registro exitoso, o que
        renderiza la plantilla 'flipigames/registro.html' con el formulario.
    """
    form = FormularioRegistroUsuario()
    
    # Si la petición no es POST, simplemente renderizamos el formulario vacío.
    if request.method != 'POST':
        return render(request, "flipigames/registro.html", {"form": form})
    
    # Procesamos la petición POST para registrar al usuario.
    try:
        resultado = services.registrar_usuario(request)
        
        if resultado["ok"]:
            return redirect("flipigames:home")
        
        return render(request, "flipigames/registro.html", {"form": resultado["form"]})
    except DatabaseError:
        messages.error(request, "Ha ocurrido un error en la base de datos durante el registro. Por favor inténtalo de nuevo")
        return render(request, "flipigames/registro.html", {"form": form})
        
@login_required    
def ajustes_cuenta(request):
    """Gestiona los ajustes de la cuenta del usuario, incluyendo cambio de email,
    cambio de contraseña y eliminación de la cuenta
    
    Args:
        request: El objeto HttpRequest.
        
        Returns:
            Un HttpResponse que redirige a la página de perfil tras una acción exitosa,
            o que renderiza la plantilla de ajustes con los formularios correspondientes.
    """
    form_email = FormularioCambiarEmail(instance=request.user)
    form_password = PasswordChangeForm(user=request.user)
    
    # Si la petición no es POST, simplemente renderizamos los formularios con los datos actuales.
    if request.method == "POST":
        try:
            respuesta = services.procesar_ajustes_cuenta(request)
            
            if respuesta.get("redirect"):
                return redirect(respuesta["redirect"])
            
            form_email = respuesta.get("form_email", form_email)
            form_password = respuesta.get("form_password", form_password)
        except DatabaseError:
            messages.error(request, "Ha ocurrido un error en la base de datos. Inténtalo de nuevo")
    
    # Si la petición no es POST, simplemente renderizamos los formularios con los datos actuales.
    contexto = {
        "form_email": form_email,
        "form_password": form_password,
    }
    
    return render(request, "flipigames/ajustes_cuenta.html", contexto)

@login_required
def perfil(request):
    """Renderiza la página de perfil del usuario con sus estadísticas y gráficos

    Args:
        request: El objeto HttpRequest.

    Returns:
        Un HttpResponse que renderiza la plantilla del perfil o redirige
        tras una acción exitosa.
    """
    
    try:
        contexto = services.obtener_contexto_perfil(request)
        return render(request, "flipigames/perfil.html", contexto)     

    except DatabaseError:
        messages.error(request, "No se pudieron cargar los datos de tu perfil. Inténtalo de nuevo más tarde")
        return redirect("flipigames:home")
    
@login_required
def admin_gestion(request):
    """Muestra un panel de administración con estadísticas generales de la aplicación
        Sólo accesible para superusuarios
        
        Args:
        request: El objeto HttpRequest.
        
        Returns:
        Un HttpResponse que renderiza la plantilla de la página de estadísticas para el administrador.
    """
    
    if not request.user.is_superuser:
        return redirect("flipigames:home")
    
    try:
        contexto = services.obtener_contexto_admin(request)
        return render(request, "flipigames/admin_gestion.html", contexto)
    except DatabaseError:
        messages.error(request, "No se pudieron cargar las estadísticas de administración. Inténtalo de nuevo más tarde")
        return render(
            request,
            "flipigames/admin_gestion.html",
            {
                "total_usuarios": 0,
                "total_participaciones": 0,
                "total_semanas": 0,
                "campeon_global": None,
                "grafico_usuarios": None,
                "grafico_torneos": None,
                "grafico_juegos_libres": None,
            },
        )