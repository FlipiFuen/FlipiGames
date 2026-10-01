from datetime import timedelta

import pytest
import base64
from unittest.mock import patch

from django.urls import reverse
from django.core import mail
from django.test import override_settings
from django.db import DatabaseError, IntegrityError
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.messages import get_messages
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from pytest_django.asserts import assertTemplateUsed # Usamos assertTemplateUsed para verificar que se está usando la plantilla correcta


from torneo.models import Torneo
from flipigames import services, charts
from juegos.models import Partida

# Le decimos a pytest que todas las pruebas de este archivo necesitan acceso a la base de datos
pytestmark = pytest.mark.django_db

# --- Fixtures: Nos permiten crear datos de prueba que se pueden reutilizar en múltiples pruebas
@pytest.fixture
def datos_usuario():
    """Devuelve un diccionario con datos para un nuevo usuario"""
    return {
        "username": "newuser",
        "email": "emilio@ejemplo.com",
        "password": "PasswordSegura123"
    }
 
@pytest.fixture   
def test_usuario():
    """Crea y devuelve un usuario de prueba persistente en la base de datos"""
    return User.objects.create_user(
        username = "testuser",
        email = "test@ejemplo.com",
        password = "PasswordTest123"
    )
    
@pytest.fixture
def usuario_logueado(client, test_usuario):
    """Devuelve un client de Django con el usuario de prueba ya autenticado"""
    client.login(username = test_usuario.username, password = "PasswordTest123")
    return client

@pytest.fixture
def datos_torneo(test_usuario):
    """Crea datos de torneo para el usuario de prueba"""
    Torneo.objects.create(
        user = test_usuario,
        semana = 30,
        juegos_ahorcado = 5,
        puntos_ahorcado = 15,
        juegos_piedra = 10,
        puntos_piedra = 20,
        juegos_adivina = 10,
        intentos_adivina = 3,
        tiempo_adivina = 20
    )
    Torneo.objects.create(
        user=test_usuario,
        semana=31,
        juegos_ahorcado=3,
        puntos_ahorcado=9,
        juegos_piedra=8,
        puntos_piedra=15,
        juegos_adivina=0,
        intentos_adivina=0,
        tiempo_adivina=0,
    )
    
@pytest.fixture
def usuario_antiguo():
    """Crea un usuario registrado hace más de 30 días"""
    usuario = User.objects.create_user(username="viejousuario", password="Password123")
    
    usuario.date_joined = timezone.now() - timedelta(days=40)
    usuario.save()
    
    return  usuario     
    
# --- Pruebas para la vista ---
def test_vista_home(client):
    """Comprueba que la página de inicio carga correctamente"""
    url = reverse("flipigames:home")
    respuesta = client.get(url)
    
    assert respuesta.status_code == 200 # Verifica que la respuesta sea exitosa (código 200)
    assertTemplateUsed(respuesta, "flipigames/home.html")
    
class TestRegistroView:
    """Pruebas para la vista de registro"""
    registro_url = reverse("flipigames:registro")
    
    def test_registro_view_get_request(self, client):
        """Comprueba que la página de registro se muestra con un formulario vacío"""
        respuesta = client.get(self.registro_url)
        
        assert respuesta.status_code == 200 # Verifica que la respuesta sea exitosa, codigo = 200
        assert "form" in respuesta.context
        assertTemplateUsed(respuesta, "flipigames/registro.html")
    
    def test_registro_exitoso_post(self, client, datos_usuario):
        """Verifica que un usuario puede registrarse correctamente"""
        # Hacemos una copia para poder modificarla y añadir el campo de confirmación
        datos_post = datos_usuario.copy()
        datos_post["password2"] = datos_post["password"]
        
        respuesta = client.post(self.registro_url, datos_post)
        
        # Comprueba que se redirige a la página de inicio
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("flipigames:home")
        
        # Verifica que el usuario fue creado en la base de datos
        assert User.objects.filter(username=datos_usuario["username"]).exists()
        
        # Comprueba que el usuario está autenticado después del registro
        nuevo_usuario = User.objects.get(username=datos_usuario["username"])
        assert respuesta.wsgi_request.user.is_authenticated
        assert respuesta.wsgi_request.user.id == nuevo_usuario.id
        
    def test_registro_fallido_usuario_existente(self, client, test_usuario, datos_usuario):
        """Comprueba que no se puede registrar a un usuario con  un nombre ya existente"""
        datos_post = datos_usuario.copy()
        datos_post["username"] = test_usuario.username
        datos_post["password2"] = datos_post["password"]
        
        respuesta = client.post(self.registro_url, datos_post)

        # Comprobamos que la página se vuelve a mostrar
        assert respuesta.status_code == 200
        
        # Verificamos que el formulario en el contexto contiene errores
        assert "form" in respuesta.context
        assert respuesta.context["form"].errors
        
        # Verificamos que el usuario no fue creado
        assert User.objects.count() == 1 # Sólo debe existir el test_usuario
        
    def test_registro_fallido_email_existente(self, client, test_usuario, datos_usuario):
        """Verifica que no se puede registrar un usuario con email ya registrado"""
        datos = datos_usuario.copy()
        
        # Asignamos el email del usuario de prueba existente
        datos["email"] = test_usuario.email
        datos["password2"] = datos["password"]
        
        respuesta = client.post(self.registro_url, datos)
        
        assert respuesta.status_code == 200
        assert "form" in respuesta.context
        assert respuesta.context["form"].errors
        assert "email" in respuesta.context["form"].errors
        assert User.objects.count() == 1
        
    def test_registro_falla_con_contraseñas_diferentes(self, client, datos_usuario):
        """Comprueba que no se registra a un usuario con contraseñas diferentes"""
        datos_post = datos_usuario.copy()
        datos_post["password2"] = "OtroPassword123"
        
        respuesta = client.post(self.registro_url, datos_post)
        
        assert respuesta.status_code == 200
        assert respuesta.context["form"].errors
        assert not User.objects.filter(username=datos_usuario["username"]).exists()
        
    def test_registro_falla_con_datos_vacios(self, client):
        """Verifica que el formulario rechaza una petición vacía"""
        respuesta = client.post(self.registro_url, {})
        
        assert respuesta.status_code == 200
        assert "form" in respuesta.context
        assert respuesta.context["form"].errors
        assert User.objects.count() == 0
        
    def test_registrar_usuario_form_invalido(self, client):
        
        respuesta = client.post(
            reverse("flipigames:registro"),
            {
                "username": "",
                "email": "no-es-email",
                "password": "Pass1234",
                "password2": "Pass1234",
            }
        )
        
        assert respuesta.status_code == 200
        assert "form" in respuesta.context
        assert respuesta.context["form"].errors
        
    def test_registro_captura_database_error(self,client, datos_usuario):
        
        datos = datos_usuario.copy()
        datos["password2"] = datos["password"]
        
        with patch(
            "flipigames.views.FormularioRegistroUsuario.save",
            side_effect = DatabaseError
        ):
            respuesta = client.post(reverse("flipigames:registro"), datos)
            
        assert respuesta.status_code == 200
        assert "form" in respuesta.context
        
        # Comprobamos que lanza el mensaje
        mensajes = list(get_messages(respuesta.wsgi_request))
        
        assert any(
            "error con la base de datos" in str(mensaje) for mensaje in mensajes
        )
    
class TestPerfilView:
    """Pruebas para la vista de perfil"""
    
    
    perfil_url = reverse("flipigames:perfil")
    ajustes_url = reverse("flipigames:ajustes_cuenta")
    
    def test_perfil_redireccion_sin_login(self, client):
        """Verifica que redirige al login si el usuario no está autenticado"""
        respuesta = client.get(self.perfil_url)
        login_url = reverse("flipigames:login")
        
        assert respuesta.status_code == 302
        assert respuesta.url == f"{login_url}?next={self.perfil_url}"
        
    def test_perfil_vista_con_login(self, usuario_logueado, datos_torneo):
        """Verifica que un usuario logueado puede ver su perfil y sus datos"""
        respuesta_perfil = usuario_logueado.get(self.perfil_url)
        
        assert respuesta_perfil.status_code == 200
        assertTemplateUsed(respuesta_perfil, "flipigames/perfil.html")
        assert "estadisticas" in respuesta_perfil.context
        
        # Comprueba que el contexto contiene los datos esperados
        respuesta_ajustes = usuario_logueado.get(self.ajustes_url)
        
        assert "form_email" in respuesta_ajustes.context
        assert "form_password" in respuesta_ajustes.context
        
    def test_perfil_sin_torneos(self, usuario_logueado):
        """Verifica que el perfil funciona sin registros de torneo"""
        respuesta = usuario_logueado.get(self.perfil_url)
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/perfil.html")
        assert respuesta.context["grafica_partidas"] is None
        assert respuesta.context["grafica_puntos"] is None
        assert respuesta.context["grafica_evolucion"] is None
        
    def test_perfil_captura_database_error(self, usuario_logueado):
        """Verifica que la vista de perfil maneja correctamente un error de base de datos"""
        with patch(
            "flipigames.services.Torneo.objects.filter",
            side_effect = DatabaseError,
        ):
            respuesta = usuario_logueado.get(reverse("flipigames:perfil"))
                
            assert respuesta.status_code == 302
            assert respuesta.url == reverse("flipigames:home")
            
    def test_perfil_captura_error_graficos(self, usuario_logueado, mocker):
        """Verifica que el perfil captura errores al generar gráficos"""
        mocker.patch(
            "flipigames.services.generar_graficos_perfil",
            side_effect = DatabaseError("fallo")
        )
        respuesta = usuario_logueado.get(self.perfil_url)
        
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("flipigames:home")
        
        mensajes = list(get_messages(respuesta.wsgi_request))
        
        assert any(
            "No se pudieron cargar los datos" in str(mensaje) for mensaje in mensajes
        )
        
    def test_ajustes_cuenta_get_con_usuario(self, usuario_logueado):
        """Comprueba que ajustes muestra los formularios en  una petición GET"""
        respuesta = usuario_logueado.get(self.ajustes_url)
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/ajustes_cuenta.html")
        assert "form_email" in respuesta.context
        assert "form_password" in respuesta.context
        
    def test_ajustes_cuenta_post_sin_accion(self, usuario_logueado):
        """Verifica que una petición sin acción muestra los formularios"""
        respuesta = usuario_logueado.post(self.ajustes_url, {})
        
        assert respuesta.status_code == 200
        assert "form_email" in respuesta.context
        assert "form_password" in respuesta.context
            
    def test_ajustes_cuenta_redirige_sin_login(self, client):
        """Verifica que los ajustes requieren autenticación"""
        respuesta = client.get(self.ajustes_url)
        login_url = reverse("flipigames:login")
        
        assert respuesta.status_code == 302
        assert respuesta.url == f"{login_url}?next={self.ajustes_url}"
        
    def test_ajustes_cuenta_captura_database_error(self, usuario_logueado, mocker):
        """Comprueba que la vista captura errores de base de datos"""
        mocker.patch(
            "flipigames.views.services.cambiar_email",
            side_effect = DatabaseError("fallo"),
        )
        respuesta = usuario_logueado.post(
            self.ajustes_url,
            {"accion": "actualizar_email", "email": "nuevo@correo.es"},
        )

        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/ajustes_cuenta.html")
        
        mensajes = list(get_messages(respuesta.wsgi_request))
        
        assert any(
            "error con la base de datos" in str(mensaje) for mensaje in mensajes
        )
        
    def test_cambiar_email_exitoso(self, usuario_logueado, test_usuario):
        """Verifica que un usuario puede cambiar su email correctamente"""
        nuevo_email = "correo@nuevo.es"
        datos_post = {"accion": "actualizar_email", "email": nuevo_email}
        
        respuesta = usuario_logueado.post(self.ajustes_url, datos_post)
        
        # Comprueba que se redirige a la página de ajustes
        assert respuesta.status_code == 302
        assert respuesta.url == self.ajustes_url
        
        # Refrescamos el usuario desde la base de datos para comprobar el cambio
        test_usuario.refresh_from_db()
        assert test_usuario.email == nuevo_email
        
    def test_cambiar_email_fallido(self, usuario_logueado):
        """Comprueba que el cambio de email falla con un formato inválido"""
        datos_post = {"accion": "actualizar_email", "email": "invalido"}

        respuesta = usuario_logueado.post(self.ajustes_url, datos_post)

        assert respuesta.status_code == 200
        assert "form_email" in respuesta.context
        assert respuesta.context["form_email"].errors
        
    def test_cambiar_email_duplicado_fallido(self, client, test_usuario, usuario_logueado):
        """Comprueba que un usuario no puede cambiar su email por uno ya en uso"""
        # Creamos un usuario de prueba diferente
        otro_usuario = User.objects.create_user(
            username = "otrousuario",
            email = "otro@ejemplo.com",
            password = "PasswordOtro123"
        )
        
        ajustes_url = reverse("flipigames:ajustes_cuenta")        
        datos_post = {"accion": "actualizar_email", "email": otro_usuario.email}
        
        respuesta = usuario_logueado.post(ajustes_url, datos_post)
        
        assert respuesta.status_code == 200
        assert "form_email" in respuesta.context
        assert respuesta.context["form_email"].errors
        assert "email" in respuesta.context["form_email"].errors
        
        # Comprobamos que el email del usuario logueado no se modificó
        test_usuario.refresh_from_db()
        assert test_usuario.email == "test@ejemplo.com"
        
    def test_cambiar_password_exitoso(self, usuario_logueado, test_usuario):
        """Verifica que un usuario puede cambiar su contraseña correctamente"""
        datos_post = {
            "accion": "actualizar_password",
            "old_password": "PasswordTest123",
            "new_password1": "PasswordNueva123",
            "new_password2": "PasswordNueva123"
        }
        
        respuesta = usuario_logueado.post(self.ajustes_url, datos_post)
        assert respuesta.status_code == 302
        
        # Verificamos que el usuario puede hacer login con la nueva contraseña
        assert usuario_logueado.login(username=test_usuario.username, password="PasswordNueva123")
        
    def test_cambiar_password_fallido(self, usuario_logueado):
        """Verifica que el cambio de contraseña falla con una contraseña incorrecta"""
        datos_post = {
            "accion": "actualizar_password",
            "old_password": "password_incorrecta",
            "new_password1": "PasswordNueva123",
            "new_password2": "PasswordNueva123"
        }
        
        respuesta = usuario_logueado.post(self.ajustes_url, datos_post)
        
        assert respuesta.status_code == 200
        assert "form_password" in respuesta.context
        assert respuesta.context["form_password"].errors
        
    def test_borrar_cuenta_exitoso(self, usuario_logueado, test_usuario):
        """Verifica que un usuario puede borrar su cuenta correctamente"""
        datos_post = {"accion": "borrar_cuenta", "password": "PasswordTest123"}
        
        respuesta = usuario_logueado.post(self.ajustes_url, datos_post)
        
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("flipigames:home")
        assert not User.objects.filter(id=test_usuario.id).exists()
        
    def test_borrar_cuenta_fallido(self, usuario_logueado, test_usuario):
        """Verifica que el borrado de cuenta falla con una contraseña incorrecta"""
        datos_post = {"accion": "borrar_cuenta", "password": "password_incorrecta"}
        
        respuesta = usuario_logueado.post(self.ajustes_url, datos_post)
        
        assert respuesta.status_code == 302 # La vista redirige igualmente
        assert respuesta.url == self.ajustes_url
        assert User.objects.filter(id=test_usuario.id).exists()
        
    def test_admin_gestion_redirige_usuario_normal(self, usuario_logueado):
        """Comprueba que un usuario normal es redirigido al home al intentar acceder a la gestión de admin"""
        respuesta = usuario_logueado.get(reverse("flipigames:admin_gestion"))
        
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("flipigames:home")
        
    def test_admin_gestion_redirige_sin_login(self, client):
        """Comprueba que un usuario anónimo es redirigido al login"""
        respuesta = client.get(reverse("flipigames:admin_gestion"))
        login_url = reverse("flipigames:login")
        
        assert respuesta.status_code == 302
        assert respuesta.url.startswith(login_url)
        
    def test_admin_gestion_muestra_estadisticas(self, client, django_user_model):
        """Verifica que un superusuario puede acceder a la gestión de admin y ver las estadísticas"""
        admin = django_user_model.objects.create_superuser(username="admin", password="PasswordAdmin123")
        
        client.force_login(admin)
        respuesta = client.get(reverse("flipigames:admin_gestion"))
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/admin_gestion.html")
        assert "total_usuarios" in respuesta.context
        assert "total_participaciones" in respuesta.context
        assert "total_semanas" in respuesta.context
        
    def test_admin_gestion_con_todos_los_datos(self, client, django_user_model, test_usuario, datos_torneo):
        """Comprueba que genera todos los gráficos con datos"""
        admin = django_user_model.objects.create_superuser(username="admin_completo", password="PasswordAdmin123")
        client.force_login(admin)
        
        Partida.objects.create(user=test_usuario, juego="ahorcado")
        Partida.objects.create(user=test_usuario, juego="pptls")
        Partida.objects.create(user=test_usuario, juego="adivina")
        
        respuesta = client.get(reverse("flipigames:admin_gestion"))
        
        assert respuesta.status_code == 200
        assert respuesta.context["total_usuarios"] == 2
        assert respuesta.context["total_participaciones"] == 2
        assert respuesta.context["total_semanas"] == 2
        assert respuesta.context["grafico_usuarios"] is not None
        assert respuesta.context["grafico_torneos"] is not None
        assert respuesta.context["grafico_juegos_libres"] is not None
        
    def test_admin_gestion_sin_datos(self, client, django_user_model):
        """Verifica el panel de administración sin datos registrados"""
        admin = django_user_model.objects.create_superuser(username="admin_vacio", password="PasswordAdmin123")
        client.force_login(admin)
        respuesta = client.get(reverse("flipigames:admin_gestion"))
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/admin_gestion.html")
        assert respuesta.context["total_usuarios"] == 1
        assert respuesta.context["total_participaciones"] == 0
        assert respuesta.context["total_semanas"] == 0
        assert respuesta.context["campeon_global"] is None
        assert respuesta.context["grafico_usuarios"] is not None
        assert respuesta.context["grafico_torneos"] is None
        assert respuesta.context["grafico_juegos_libres"] is None
        
    def test_admin_gestion_captura_database_error(self, client, django_user_model, mocker):
        """Comprueba que la vista administra errores de base de datos"""
        admin = django_user_model.objects.create_superuser(
            username = "admin_error",
            password = "PasswordAdmin123",
        )
        client.force_login(admin)
        
        # Forzamos un error antes de construir el contexto
        mocker.patch(
            "flipigames.services.User.objects.count",
            side_effect = DatabaseError("fallo")
        )
        
        respuesta = client.get(reverse("flipigames:admin_gestion"))
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/admin_gestion.html")
        assert "total_usuarios" in respuesta.context
        assert respuesta.context["total_usuarios"] == 0
        assert respuesta.context["total_participaciones"] == 0
        assert respuesta.context["total_semanas"] == 0
        assert respuesta.context["campeon_global"] is None
        assert respuesta.context["grafico_usuarios"] is None
        assert respuesta.context["grafico_torneos"] is None
        assert respuesta.context["grafico_juegos_libres"] is None
        
        mensajes = list(get_messages(respuesta.wsgi_request))
        
        assert any(
            "No se pudieron cargar las estadísticas" in str(mensaje) for mensaje in mensajes
        )
        
    def test_admin_gestion_muestra_campeon_global(self, client, django_user_model, test_usuario):
        """Comprueba que administraión muestra el campeón global"""
        admin = django_user_model. objects.create_superuser(username="admin_campeon", password="PasswordAdmin123")
        client.force_login(admin)
        
        Torneo.objects.create(
            user = test_usuario,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 1,
            tiempo_adivina = 10,
        )
        respuesta = client.get(reverse("flipigames:admin_gestion"))
        
        assert respuesta.status_code == 200
        assert respuesta.context["campeon_global"] is not None
        assert respuesta.context["campeon_global"]["usuario"] == test_usuario
        assert respuesta.context["campeon_global"]["victorias"] == 1
        
    def test_admin_gestion_rechaza_usuario_staff_no_superusuario(self, client, django_user_model):
        """Comprueba que staff sin privilegios de superusuario no accede al panel"""
        staff = django_user_model.objects.create_user(username="staff_sin_superusuario", password="PasswordStaff123")
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        
        client.force_login(staff)
        respuesta = client.get(reverse("flipigames:admin_gestion"))
        
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("flipigames:home")
            
    def test_ajustes_accion_desconocida(self, usuario_logueado):
        """Verifica que la vista de ajustes maneja correctamente una acción desconocida"""
        respuesta = usuario_logueado.post(
            reverse("flipigames:ajustes_cuenta"),
            {"accion": "accion_inexistente"},
        )
        
        assert respuesta.status_code == 200
        assert "form_email" in respuesta.context
        assert "form_password" in respuesta.context
        
class TestFlipigamesServices:
        
    def test_calcular_estadisticas_usuario_con_datos(self, test_usuario, datos_torneo):
        """Verifica que las estadísticas del usuario se calculan correctamente con registros existentes"""
        registros = Torneo.objects.filter(user=test_usuario)
        resultado = services.calcular_estadisticas_usuario(registros)
        
        assert resultado["total_partidas"] == 36
        assert resultado["semanas_participadas"] == 2
        assert resultado["mejor_ahorcado"] == {"puntos": 15, "semana": 30, "anio": 2026}
        assert resultado["mejor_piedra"] == {"puntos": 20, "semana": 30, "anio": 2026}
        assert resultado["mejor_adivina"]["intentos"] == 3
        assert resultado["torneos_ganados"] == 1
        
    def test_calcular_estadisticas_usuario_sin_registros(self, test_usuario):
        """Comprueba que las estadísticas del usuario se calculan correctamente cuando no hay registros"""
        resultado = services.calcular_estadisticas_usuario(Torneo.objects.filter(user=test_usuario))
        
        assert resultado == {
            "total_partidas": 0,
            "semanas_participadas": 0,
            "mejor_ahorcado": None,
            "mejor_piedra": None,
            "mejor_adivina": None,
            "torneos_ganados": 0,
        }
        
    def test_estadisticas_solo_ahorcado(self, test_usuario):
            """Verifica que las estadísticas se calculan correctamente cuando solo hay registros de Ahorcado"""
            Torneo.objects.create(user=test_usuario, semana=1, juegos_ahorcado=3, puntos_ahorcado=9)
            resultado = services.calcular_estadisticas_usuario(Torneo.objects.filter(user=test_usuario))
            
            assert isinstance(resultado, dict)
            assert resultado["total_partidas"] == 3
            assert resultado["mejor_ahorcado"] == {"puntos": 9, "semana": 1, "anio": 2026}
            assert resultado["mejor_piedra"] is None
            assert resultado["mejor_adivina"] is None
            
    def test_torneo_rechaza_puntos_ahorcado_negativos(self, test_usuario):
        """Verifica que el modelo Torneo rechaza puntos negativos en Ahorcado"""
        torneo = Torneo(user=test_usuario, semana=1, puntos_ahorcado=-1)
        
        with pytest.raises(IntegrityError):
            torneo.save()
            
    @pytest.mark.parametrize("semana_invalida", [0, 54])
    def test_torneo_rechaza_semana_invalida(self, test_usuario, semana_invalida):
        """Verifica que el modelo Torneo rechaza semanas inválidas"""
        torneo = Torneo(user=test_usuario, semana=semana_invalida)
        
        with pytest.raises(IntegrityError):
            torneo.save()
            
    def test_estadisticas_usuario_distingue_anios_al_contar_campeonatos(self, test_usuario, django_user_model):
        """Comprueba que el perfil no mezcla campeonatos de años distintos"""
        otro_usuario = django_user_model.objects.create_user(username="otro", password="Password123")
        
        Torneo.objects.create(
            user = test_usuario,
            anio = 2025,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 1,
            tiempo_adivina = 20,
        )
        Torneo.objects.create(
            user = otro_usuario,
            anio = 2026,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 1,
            tiempo_adivina = 10,
        )
        
        resultado = services.calcular_estadisticas_usuario(Torneo.objects.filter(user=test_usuario))
        
        assert resultado["torneos_ganados"] == 1
            
    def test_estadisticas_solo_piedra(self, test_usuario):
        """Verifica las estadisticas cuando sólo existen partidas de PPTLS"""
        Torneo.objects.create(user=test_usuario, semana=1, juegos_piedra=4, puntos_piedra=12)
        
        resultado = services.calcular_estadisticas_usuario(Torneo.objects.filter(user=test_usuario))
        
        assert isinstance(resultado, dict)
        assert resultado["total_partidas"] == 4
        assert resultado["mejor_ahorcado"] is None
        assert resultado["mejor_piedra"] == {"puntos": 12, "semana": 1, "anio": 2026}
        assert resultado["mejor_adivina"] is None
        
    def test_estadisticas_solo_adivina(self, test_usuario):
        """Verifica las estadísticas cuando sólo existen partidas de adivina"""
        Torneo.objects.create(
            user = test_usuario,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 2,
            tiempo_adivina = 15
        )
        resultado = services.calcular_estadisticas_usuario(Torneo.objects.filter(user=test_usuario))
        
        assert resultado["total_partidas"] == 1
        assert resultado["mejor_ahorcado"] is None
        assert resultado["mejor_piedra"] is None
        assert resultado["mejor_adivina"] == {"intentos": 2, "tiempo": 15, "semana": 1, "anio": 2026}
            
    def test_estadisticas_ignora_puntuaciones_cero(self, test_usuario):
        """Verifica que las estadísticas ignoran registros con puntuaciones cero"""
        Torneo.objects.create(
            user = test_usuario,
            semana = 1,
            juegos_ahorcado = 0,
            puntos_ahorcado = 0,
            juegos_piedra = 0,
            juegos_adivina = 0,
            intentos_adivina = 0,
            )
        resultado = services.calcular_estadisticas_usuario(Torneo.objects.filter(user=test_usuario))
            
        assert resultado["mejor_ahorcado"] is None
        assert resultado["mejor_piedra"] is None
        assert resultado["mejor_adivina"] is None
        
    def test_calcular_estadisticas_usuario_excepcion_tipo_invalido(self):
        """Gestión de excepciones: pytest.raises al pasar un tipo no válido"""
        resultado = services.calcular_estadisticas_usuario(12345)
                
        assert resultado == {
            "total_partidas": 0,
            "semanas_participadas": 0,
            "mejor_ahorcado": None,
            "mejor_piedra": None,
            "mejor_adivina": None,
            "torneos_ganados": 0,
                }
        
    def test_calcular_estadisticas_sin_registro_incluye_campeon(self, test_usuario):
        """Verifica que el resultado vacío mantiene siempre las mismas claves"""
        resultado = services.calcular_estadisticas_usuario(Torneo.objects.filter(user=test_usuario))
        
        assert resultado["torneos_ganados"] == 0
            
    def test_estadisticas_devuelve_vacio_si_falla_aggregate(self, test_usuario, monkeypatch):
        """Verifica que las estadísticas devuelven valores vacíos si falla la operación aggregate"""
        registros = Torneo.objects.filter(user=test_usuario)
            
         # Definimos una función que simula un fallo en la base de datos al llamar a aggregate
        def aggregate_fallido(*args, **kwargs):      
            raise DatabaseError("Error de Base de datos")
            
        monkeypatch.setattr(registros, "aggregate", aggregate_fallido)
        resultado = services.calcular_estadisticas_usuario(registros)
            
        assert resultado["total_partidas"] == 0
        assert resultado["torneos_ganados"] == 0
        
    def test_obtener_usuarios_nuevos_por_dia(self, test_usuario):
        """Verifica que se obtienen correctamente los usuarios nuevos por día"""
        resultado = services.obtener_usuarios_nuevos_por_dia()
        
        assert resultado.count() == 1
        assert resultado[0]["count"] == 1
        assert "date" in resultado[0]
        
    def test_obtener_usuarios_nuevos_por_dia_usuario_antiguo(self, usuario_antiguo):
        """Usuarios registrados hace más de 30 días no deben contarse"""
        resultado = services.obtener_usuarios_nuevos_por_dia()
        
        assert not any(r["date"] == usuario_antiguo.date_joined.date() for r in resultado)
        
    def test_obtener_participantes_por_semana(self, datos_torneo):
        """Verifica que se obtienen correctamente los participantes por semana"""
        
        resultado = list(services.obtener_participantes_por_semana())
        
        assert resultado[0] == {
            "anio": 2026,
            "semana": 30,
            "count": 1,
        }
        
    def test_participantes_por_semana_sin_datos(self):
        """Comprueba que no hay resultados cuando no existen torneos"""
        
        assert list(services.obtener_participantes_por_semana()) == []
        
    def test_obtener_juegos_libre_conteo(self, test_usuario):
        """Comprueba que se obtienen correctamente los juegos libres y su conteo"""
        Partida.objects.create(user=test_usuario, juego="ahorcado")
        Partida.objects.create(user=test_usuario, juego="pptls")
        Partida.objects.create(user=test_usuario, juego="adivina")
        
        nombres, valores = services.obtener_juegos_libres_conteo()
        
        assert nombres == ["Ahorcado", "PPTLS", "Adivina el Número"]
        assert valores == [1, 1, 1]
        
    def test_obtener_juegos_libres_devuelve_ceros_para_juegos_no_jugados(self, test_usuario):
        """Verifica que los juegos no jugados aparecen con conteo cero"""
        Partida.objects.create(user=test_usuario, juego="ahorcado")
        
        nombres, valores = services.obtener_juegos_libres_conteo()
        
        assert nombres == ["Ahorcado", "PPTLS", "Adivina el Número"]
        assert valores == [1, 0, 0]
        
    def test_obtener_campeon_global_sin_datos(self):
        """Verifica que se obtiene None cuando no hay datos de campeones"""
        assert services.obtener_campeon_global() is None
        
    def test_obtener_campeon_global_con_datos(self, test_usuario):
        """Verifica que se obtiene correctamente el campeón global cuando hay datos"""
        Torneo.objects.create(
            user = test_usuario,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 1,
            tiempo_adivina = 5,
        )
        resultado = services.obtener_campeon_global()
        
        assert resultado["usuario"] == test_usuario
        assert resultado["victorias"] == 1
        
    def test_campeon_global_usa_menor_tirmpo_en_empate(self, test_usuario, django_user_model):
        """Verifica que el desempate se resuelve usando el menor tiempo"""
        otro = django_user_model.objects.create_user(username="otro")
        
        Torneo.objects.create(
            user = test_usuario,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 2,
            tiempo_adivina = 20
        )
        Torneo.objects.create(
            user = otro,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 2,
            tiempo_adivina = 10,
        )
        resultado = services.obtener_campeon_global()
        
        assert resultado["usuario"] == otro
        assert resultado["victorias"] == 1
        
    def test_campeon_global_ignora_torneos_no_validos(self, test_usuario):
        """Comprueba que los torneos sin partidas válidas de Adivina se ignoran"""
        Torneo.objects.create(
            user = test_usuario,
            semana = 1,
            juegos_adivina = 0,
            intentos_adivina = 0,
            tiempo_adivina = 0,
        )
        
        assert services.obtener_campeon_global() is None
        
    def test_campeon_global_distingue_misma_semana_en_anios_diferentes(self, test_usuario, django_user_model):
        """Comprueba que una misma semana de años distintos son torneos diferentes"""
        otro_usuario = django_user_model.objects.create_user(username="otro", password="Password123")
        
        Torneo.objects.create(
            user = test_usuario,
            anio = 2025,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 1,
            tiempo_adivina = 20,
        )
        Torneo.objects.create(
            user = otro_usuario,
            anio = 2026,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 1,
            tiempo_adivina = 10,
        )
        
        resultado = services.obtener_campeon_global()
        
        assert resultado["victorias"] == 1
                
    def test_cambiar_email_valido(self, test_usuario, mocker):
        """Verifica que un usuario puede cambiar su email correctamente usando la función de servicios"""
        request = mocker.Mock()
        request.POST = {"email": "nuevo@correo.es"}
        request.user = test_usuario
        
        #Simulamos el envío del mensaje de confirmación
        mensaje_exito = mocker.patch("flipigames.services.messages.success")
        
        resultado = services.cambiar_email(request)
        
        assert resultado is True
        test_usuario.refresh_from_db()
        assert test_usuario.email == "nuevo@correo.es"
        mensaje_exito.assert_called_once()
        
    def test_cambiar_email_invalido_devuelve_formulario(self, test_usuario, mocker):
        """Verifica que un email inválido devuelve un formulario con errores usando la función de servicios"""
        request = mocker.Mock()
        request.POST = {"email": "correo_invalido"}
        request.user = test_usuario
        
        resultado = services.cambiar_email(request)
        
        assert resultado is not True
        assert hasattr(resultado, "errors")
        assert "email" in resultado.errors
        assert resultado.errors["email"]
        
        # El email original debe mantenerse sin cambios
        test_usuario.refresh_from_db()
        assert test_usuario.email == "test@ejemplo.com"
        
    def test_cambiar_email_database_error(self, test_usuario, mocker):
        """Verifica que un error de base de datos al cambiar el email lanza una excepción usando la función de servicios"""
        request = mocker.Mock()
        request.POST = {"email": "nuevo@correo.es"}
        request.user = test_usuario
        
        # Forzamos un error durante el guardado del formulario
        mocker.patch(
            "flipigames.services.FormularioCambiarEmail.save",
            side_effect = DatabaseError("fallo")
        )
        with pytest.raises(DatabaseError, match="fallo"):
            services.cambiar_email(request)
            
    def test_cambiar_password_valido(self, test_usuario, mocker):
        """Verifica que un usuario puede cambiar su contraseña correctamente usando la función de servicios"""
        request = mocker.Mock()
        request.POST = {
            "old_password": "PasswordTest123",
            "new_password1": "PasswordNuevo123",
            "new_password2": "PasswordNuevo123",
        }
        request.user = test_usuario
        
        # Comprobamos que la sesión se actualiza después del cambio
        actualizar_sesion = mocker.patch("flipigames.services.update_session_auth_hash")
        
        resultado = services.cambiar_password(request)
        
        assert resultado is True
        test_usuario.refresh_from_db()
        assert test_usuario.check_password("PasswordNuevo123")
        actualizar_sesion.assert_called_once()
        
    def test_cambiar_password_incorrecta_devuelve_formulario(self, test_usuario, mocker):
        """Verifica que una contraseña incorrecta devuelve un formulario con errores usando la función de servicios"""
        request = mocker.Mock()
        request.POST = {
            "old_password": "PasswordIncorrecta",
            "new_password1": "PasswordNuevo123",
            "new_password2": "PasswordNuevo123",
        }
        request.user = test_usuario
        resultado = services.cambiar_password(request)
        
        assert resultado is not True
        assert hasattr(resultado, "errors")
        assert resultado.errors
        
        # La contraseña nueva no debe haberse guardado
        test_usuario.refresh_from_db()
        assert test_usuario.check_password("PasswordTest123")
        
    def test_cambiar_password_confirmacion_diferente(self, test_usuario, mocker):
        """Comprueba que falla cuando las contraseñas nuevas no coinciden"""
        request = type("Request", (), {})()
        request.POST = {
            "old_password": "PasswordTest123",
            "new_password1": "PasswordNuevo123",
            "new_password2": "OtroPassword123"
        }
        request.user = test_usuario
        resultado = services.cambiar_password(request)
        
        assert resultado is not True
        assert "new_password2" in resultado.errors
        
    def test_cambiar_password_database_error(self, test_usuario, mocker):
        """Verifica que un error de base de datos al cambiar la contraseña lanza una excepción usando la función de servicios"""
        request = mocker.Mock()
        request.POST = {
            "old_password": "PasswordTest123",
            "new_password1": "PasswordNuevo123",
            "new_password2": "PasswordNuevo123",
        }
        request.user = test_usuario
        
        mocker.patch(
            "flipigames.services.PasswordChangeForm.save",
            side_effect = DatabaseError("fallo"),
        )
        with pytest.raises(DatabaseError, match="fallo"):
            services.cambiar_password(request)
            
    def test_borrar_cuenta_correcto(self, test_usuario, mocker):
        """Verifica que un usuario puede borrar su cuenta correctamente usando la función de servicios"""
        request = mocker.Mock()
        request.POST = { "password": "PasswordTest123" }
        request.user = test_usuario
        
        # Simulamos el cierre de sesión y el mensaje de confirmación
        cerrar_sesion = mocker.patch("flipigames.services.logout")
        mocker.patch("flipigames.services.messages.success")
        
        resultado = services.borrar_cuenta(request)
        
        assert resultado is True
        assert not User.objects.filter(pk=test_usuario.pk).exists()
        cerrar_sesion.assert_called_once_with(request)
        
    def test_borrar_cuenta_password_incorrecto(self, test_usuario, mocker):
        """Comprueba que una contraseña incorreccta no elimina la cuenta"""
        request = mocker.Mock()
        request.POST = {"password": "PasswordIncorrecto"}
        request.user = test_usuario
        
        mensaje_error = mocker.patch("flipigames.services.messages.error")
        resultado = services.borrar_cuenta(request)
        
        assert resultado is False
        assert User.objects.filter(pk=test_usuario.pk).exists()
        mensaje_error.assert_called_once()
        
        # Comprobamos el contenido del mensaje de error
        mensaje = mensaje_error.call_args.args[1]
        assert "contraseña es incorrecta" in mensaje
        
    def test_borrar_cuenta_password_vacia(self, test_usuario, mocker):
        """Verifica que un intento de borrar la cuenta con contraseña vacía devuelve False y no elimina el usuario"""
        request = mocker.Mock()
        request.POST = {"password": ""}
        request.user = test_usuario
        
        mensaje_error = mocker.patch("flipigames.services.messages.error")
        resultado = services.borrar_cuenta(request)
        
        assert resultado is False
        assert User.objects.filter(pk=test_usuario.pk).exists()
        mensaje_error.assert_called_once()
        
    def test_borrar_cuenta_error_al_eliminar(self, test_usuario, mocker):
        """Verifica que un error de base de datos al borrar la cuenta lanza una excepción usando la función de servicios"""
        request = mocker.Mock()
        request.POST = {"password": "PasswordTest123"}
        request.user = test_usuario
        
        mocker.patch("flipigames.services.logout")
        mocker.patch.object(test_usuario, "delete", side_effect = DatabaseError("fallo"))
        
        with pytest.raises(DatabaseError, match="fallo"):
            services.borrar_cuenta(request)
            
    def test_usuarios_nuevos_agrupa_por_dia(self, django_user_model):
        """Verifica que la función de servicios agrupa correctamente los usuarios nuevos por día"""
        User.objects.create_user(username="uno")
        User.objects.create_user(username="dos")
        
        resultado = list(services.obtener_usuarios_nuevos_por_dia())
        
        assert len(resultado) == 1
        assert resultado[0]["count"] == 2
        assert "date" in resultado[0]
        assert isinstance(resultado[0]["count"], int)
        
    def test_usuario_exactamente_30_dias(self, django_user_model):
        """Verifica que un usuario registrado hace exactamente 30 días se incluye en el conteo"""
        usuario = django_user_model.objects.create_user(username="limite")
        usuario.date_joined = timezone.now() - timedelta(days=29)
        usuario.save()
        
        resultado = services.obtener_usuarios_nuevos_por_dia()
        
        assert resultado.exists()
        
    def test_participantes_cuenta_usuarios_distintos(self, test_usuario, django_user_model):
        """Verifica que la función de servicios cuenta correctamente los usuarios distintos por semana"""
        otro = django_user_model.objects.create_user(username="otro")
        
        Torneo.objects.create(user=test_usuario, semana=1)
        Torneo.objects.create(user=otro, semana=1)
        
        resultado = list(services.obtener_participantes_por_semana())
        
        assert resultado == [{"anio": 2026, "semana": 1, "count": 2}]
        
    def test_participantes_por_semana_distingue_anio(self, test_usuario, django_user_model):
        """Comprueba que la misma semana de años diferentes no se agrupa"""
        otro_usuario = django_user_model.objects.create_user(username="otro", password="Password123")
        
        Torneo.objects.create(user=test_usuario, anio=2025, semana=1)
        Torneo.objects.create(user=otro_usuario, anio=2026, semana=1)
        
        resultado = list(services.obtener_participantes_por_semana())
        
        assert resultado == [
            {"anio": 2025, "semana": 1, "count": 1},
            {"anio": 2026, "semana": 1, "count": 1}
        ]
        
    def test_juegos_libres_acumula_por_tipo(self, test_usuario):
        """Verifica que la función de servicios acumula correctamente el conteo de juegos libres por tipo"""
        Partida.objects.create(user=test_usuario, juego="ahorcado")
        Partida.objects.create(user=test_usuario, juego="ahorcado")
        Partida.objects.create(user=test_usuario, juego="pptls") 
        
        nombres, valores = services.obtener_juegos_libres_conteo()
        
        assert nombres == ["Ahorcado", "PPTLS", "Adivina el Número"]
        assert valores == [2, 1, 0]
        
    def test_juegos_libres_solo_devuelve_none_sin_juegos(self, test_usuario):
        """Verifica que la función de servicios devuelve None cuando no hay juegos libres"""
        Partida.objects.create(user=test_usuario, juego="valor_invalido")
        
        assert services.obtener_juegos_libres_conteo() == (None, None) 
        
    def test_campeon_selecciona_menos_intentos_y_tiempo(self, test_usuario, django_user_model):
        """Verifica que el campeón global se selecciona correctamente usando menos intentos y tiempo en caso de empate"""
        otro = django_user_model.objects.create_user(username="otro")
        Torneo.objects.create(
            user = test_usuario,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 3,
            tiempo_adivina = 20,
        )
        Torneo.objects.create(
            user = otro,
            semana = 1,
            juegos_adivina = 1,
            intentos_adivina = 2,
            tiempo_adivina = 50,
        )
        resultado = services.obtener_campeon_global()
        
        assert resultado["usuario"] == otro
        assert resultado["victorias"] == 1
        
    def test_campeon_global_captura_database_error(self, mocker):
        """Verifica que la función de servicios maneja correctamente un error de base de datos al obtener el campeón global"""
        mocker.patch(
            "flipigames.services.Torneo.objects.values_list",
            side_effect = DatabaseError("fallo")
        )
        
        assert services.obtener_campeon_global() is None
        
    def test_contexto_admin_cuenta_semanas_por_anio(self, client, django_user_model, test_usuario):
        """Comprueba que semanas iguales de años distintos cuentan por separado"""
        admin = django_user_model.objects.create_superuser(username="admin:periodos", password="Password123")
        client.force_login(admin)
        
        Torneo.objects.create(user=test_usuario, anio=2025, semana=1)
        Torneo.objects.create(user=test_usuario, anio=2026, semana=1)
        
        respuesta = client.get(reverse("flipigames:admin_gestion"))
                               
        assert respuesta.status_code == 200
        assert respuesta.context["total_semanas"] == 2
        
    def test_obtener_contexto_admin_captura_database_error(self, client, django_user_model):
        """Verifica que la función de servicios maneja correctamente un error de base de datos al obtener el contexto admin"""
        admin = django_user_model.objects.create_superuser(username="admin_db", password="PasswordAdmin123")
        client.force_login(admin)
        
        with patch("flipigames.services.User.objects.count", side_effect=DatabaseError("fallo")):
            respuesta = client.get(reverse("flipigames:admin_gestion"))
            
        assert respuesta.status_code == 200
        assert respuesta.context["total_usuarios"] == 0
        assert respuesta.context["total_participaciones"] == 0
        assert respuesta.context["total_semanas"] == 0
        assert respuesta.context["grafico_usuarios"] is None
        
    def test_obtener_contexto_perfil_error_graficos(self, usuario_logueado):
        
        with patch("flipigames.services.generar_graficos_perfil", side_effect=DatabaseError("fallo")):
            respuesta = usuario_logueado.get(reverse("flipigames:perfil"))
            
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("flipigames:home")    
        
class TestCharts:
    """Pruebas para la generación de gráficos"""
    
    def test_figura_a_base64_con_figura_invalida(self):
        """Verifica que una figura inválida produce un AttributeError"""
        with pytest.raises(AttributeError):
            charts._figura_a_base64(12345)
            
    def test_figura_a_base64_con_figura_vacia(self):
        """Comprueba que una figura None devuelve None"""
        assert charts._figura_a_base64(None) is None
    
    def test_crear_grafico_lineas_sin_datos(self):
        """Verifica que la función de creación de gráficos de líneas devuelve None cuando no hay datos"""
        resultado = charts.crear_grafico_lineas([], [], "Título", "X", "Y")
        
        assert resultado is None
        
    def test_grafico_lineas_con_datos(self):
        """Verifica que la función de creación de gráficos de líneas devuelve un string base64 válido cuando hay datos"""
        resultado = charts.crear_grafico_lineas(
            ["Lunes", "Martes"],
            [1, 2],
            "Título",
            "Día",
            "Valor",
        )
        
        assert isinstance(resultado, str)
        assert base64.b64decode(resultado).startswith(b"\x89PNG")
        
    def test_crear_grafico_lineas_con_un_punto(self):
        """verifica que se genera un gráfico de líneas con un único punto"""
        resultado = charts.crear_grafico_lineas(
            ["Lunes"],
            [10],
            "Título",
            "Día",
            "Puntos",
        )
        
        assert isinstance(resultado, str)
        assert base64.b64decode(resultado).startswith(b"\x89PNG")
        
    def test_crear_grafico_lineas_con_listas_incompatibles(self):
        """Comprueba que falla si las etiquetas y los valores tienen distinta longitud"""
        with pytest.raises(ValueError):
            charts.crear_grafico_lineas(
                ["Lunes", "Martes"],
                [10],
                "Título",
                "Día",
                "Puntos",
            )
        
    def test_generar_graficos_partidas_sin_partidas(self):
        """Verifica que la función de generación de gráficos de partidas devuelve None cuando no hay datos"""
        resultado = charts.generar_grafico_partidas({})
        
        assert resultado is None
        
    def test_generar_grafico_partidas_con_datos(self):
        """Verifica que la función de generación de gráficos de partidas devuelve un string base64 válido cuando hay datos"""
        resultado = charts.generar_grafico_partidas({
            "total_ahorcado": 2,
            "total_piedra": 0,
            "total_adivina": 1,
        })
        
        assert isinstance(resultado, str)
        
    def test_generar_grafico_partidas_con_datos_nulos(self):
        """Comprueba que los valores None se convierten en 0"""
        resultado = charts.generar_grafico_partidas({
            "total_ahorcado": None,
            "total_piedra": 2,
            "total_adivina": None,
        })
            
        assert isinstance(resultado, str)
        assert base64.b64decode(resultado).startswith(b"\x89PNG")
        
    def test_generar_grafico_partidas_con_claves_ausentes(self):
        """Verifica que las claves ausentes se interpretan con valores 0"""
        resultado = charts.generar_grafico_partidas({"total_ahorcado": 2,})
        
        assert isinstance(resultado, str)
        assert base64.b64decode(resultado).startswith(b"\x89PNG")
        
    def test_generar_grafico_puntos_con_datos(self):
        """Comprueba que se genera un gráfico con puntos positivos"""
        resultado = charts.generar_grafico_puntos({
            "puntos_ahorcado": 10,
            "puntos_piedra": 5,
        })
        
        assert isinstance(resultado, str)
        assert base64.b64decode(resultado).startswith(b"\x89PNG")
        
    def test_generar_grafico_puntos_sin_puntos(self):
        """Verifica que la función de generación de gráficos de puntos devuelve None cuando no hay datos"""
        assert charts.generar_grafico_puntos({}) is None
        
    def test_generar_grafico_puntos_con_claves_ausentes(self):
        """Verifica que devuelve None si no existen puntos registrados"""
        resultado  = charts.generar_grafico_puntos({})
        
        assert resultado is None
        
    def test_generar_grafico_evolucion_con_datos(self, datos_torneo, test_usuario):
      
        grafico = charts.generar_grafico_evolucion(["Semana 30", "Semana 31"], [15, 20] )
        
        assert isinstance(grafico, str)
        assert grafico.startswith("iVBORw0KGgo") # cabecera base64 de png
        
    def test_generar_grafico_evolucion_sin_datos(self):
        """Comprueba que no se genera evolución sin semanas"""
        
        assert charts.generar_grafico_evolucion([], []) is None
        
    def test_generar_grafico_evolucion_con_una_semana(self):
        """Verifica que no se genera evolución con una sola semana"""
        
        assert charts.generar_grafico_evolucion(["Semana 1"], [10]) is None
        
    def test_generar_grafico_evolucion_con_listas_incompatibles(self):
        """Verifica que falla si semanas y puntos tienen distinta longitud"""
        with pytest.raises(ValueError):
            charts.generar_grafico_evolucion(
                ["Semana 1", "Semana 2"],
                [10]
            )
        
    def test_generar_graficos_perfil_completo(self, test_usuario, datos_torneo):
        """Verifica que crea el diccionario con los 3 gráficos del perfil"""
        registros = Torneo.objects.filter(user=test_usuario)
        g_partidas, g_puntos, g_evolucion = charts.generar_graficos_perfil(registros)
        
        assert isinstance(g_partidas, str)
        assert isinstance(g_puntos, str)
        assert isinstance(g_evolucion, str)
        
    def test_generar_graficos_perfil_sin_registros(self):
        """Comprueba que no se generan gráficos sin registros de torneo"""
        registros = Torneo.objects.none()
        
        assert charts.generar_graficos_perfil(registros) == (None, None, None)
        
    def test_generar_graficos_perfil_con_un_registro(self, test_usuario):
        """Verifica el perfil cuando sólo hay un registro de torneo"""
        Torneo.objects.create(
            user = test_usuario,
            semana = 1,
            juegos_ahorcado = 2,
            puntos_ahorcado = 5,
        )
        registros = Torneo.objects.filter(user=test_usuario)
        resultado = charts.generar_graficos_perfil(registros)
        
        # Con un registro no se puede crear el gráfico
        assert isinstance(resultado, tuple)
        assert len(resultado) == 3
        assert isinstance(resultado[0], str)
        assert isinstance(resultado[1], str)
        assert resultado[2] is None
        
    def test_generar_graficos_perfil_con_registros_sin_puntos(self, test_usuario):
        """Verifica el perfil cuando existen registros pero todos los puntos son ceros"""
        Torneo.objects.create(
            user = test_usuario,
            semana = 1,
            juegos_ahorcado = 1,
            juegos_piedra = 1,
            juegos_adivina = 1,
            intentos_adivina = 3,
            tiempo_adivina = 11,
        )
        Torneo.objects.create(
            user = test_usuario,
            semana = 2,
            juegos_ahorcado = 1,
            juegos_piedra = 1,
            juegos_adivina = 1,
            intentos_adivina = 3,
            tiempo_adivina = 11
        )
        registros = Torneo.objects.filter(user=test_usuario)
        resultado = charts.generar_graficos_perfil(registros)
        
        # El gráfico de partidas existe porque hay partidas jugadas
        assert isinstance(resultado[0], str)
        
        # El gráfico de puntos no se genera porque todos los puntos son 0
        assert resultado[1] is None
        
        # La evolución sí se genera porque hay 2 semanas
        assert isinstance(resultado[2], str)
        
    def test_crear_grafico_barras_con_valores_cero(self):
        """Verifica que se genera un gráfico de barras aunque todos los valores sean 0"""
        resultado = charts.crear_grafico_barras(
            ["Ahorcado", "PPTLS"],
            [0, 0],
            "Partidas",
            "Juego",
            "Cantidad",
        )
            
        assert isinstance(resultado, str)
        assert base64.b64decode(resultado).startswith(b"\x89PNG")
        
    def test_crear_grafico_barras_con_anotaciones(self):
        """Comprueba que las anotaciones se incluyen en el gráfico"""
        resultado = charts.crear_grafico_barras(
            ["Jugador 1", "Jugador 2"],
            [2, 1],
            "Clasificación",
            "Jugador",
            "Intentos",
            anotaciones = ["10 segundos", "15 segundos"],
        )
        
        assert isinstance(resultado, str)
        assert base64.b64decode(resultado).startswith(b"\x89PNG")
        
    def test_crear_grafico_barras_con_listas_incompatibles(self):
        """Comprueba que fMatplotlib genera el gráfico con valores reutilizables"""
        resultado = charts.crear_grafico_barras(
            ["Ahorcado", "PPTLS"],
            [1],
            "Partidas",
            "Juego",
            "Cantidad", 
        )
        
        assert isinstance(resultado, str)
        assert base64.b64decode(resultado).startswith(b"\x89PNG")
            
    def test_crear_grafico_pastel_sin_etiquetas(self):
        """Verifica que se genera un gráfico de pastel sin etiquetas"""
        resultado = charts.crear_grafico_pastel(
            [],
            [10, 20],
            "Distribución",
        )
        
        assert resultado is None
        
    def test_crear_grafico_pastel_con_valores_cero(self):
        """Comprueba que no se genera un gráfico de pastel con valores cero"""
        resultado = charts.crear_grafico_pastel(
            ["Ahorcado", "PPTLS"],
            [0, 0],
            "Distribución"
        )

        assert resultado is None
        
    def test_crear_grafico_pastel_con_valores_negativos(self):
        """Verifica que falla si el gráfico de pastel recibe valores negativos"""
        with pytest.raises(ValueError):
            charts.crear_grafico_pastel(
                ["Ahorcado", "PPTLS"],
                [-1, 2],
                "Distribución",
            )
 
 
class TestRestablecerContraseña:
    """Pruebas para la funcionalidad de restablecimiento de contraseña"""
    
    # Creamos un fixture para configurar el backend de correo electrónico de pruebas
    @pytest.fixture(autouse=True)
    def configurar_correo_pruebas(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    
    reset_url = reverse("flipigames:password_reset")
    
    def test_formulario_recuperacion_se_muestra(self, client):
        """Comprueba que se muestra el formulario de recuperación de contraseña"""
        respuesta = client.get(self.reset_url)
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/password_reset_form.html")
        assert "form" in respuesta.context
        
    def test_envia_email_con_enlace_valido(self, client, test_usuario):
        """Comprueba que se envía un correo electrónico con un enlace de restablecimiento válido"""
        respuesta = client.post(self.reset_url, {"email": test_usuario.email})
        
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("flipigames:password_reset_done")
        assert len(mail.outbox) == 1
        assert test_usuario.username in mail.outbox[0].body
        assert "restablecer-contrasena/" in mail.outbox[0].body
            
    def test_email_no_registrado_no_envia_correo(self, client):
        
        respuesta = client.post(self.reset_url, {"email": "nadie@ejemplo.com"})
        
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("flipigames:password_reset_done")
        assert len(mail.outbox) == 0
        
    def test_pantalla_correo_enviado(self, client):
        """Comprueba que se muestra la pantalla de correo enviado"""
        respuesta = client.get(reverse("flipigames:password_reset_done"))
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/password_reset_done.html")
        
    def test_enlace_valido_permite_establecer_contraseña(self, client, test_usuario):
        """Comprueba que un enlace válido permite establecer una nueva contraseña"""
        uid = urlsafe_base64_encode(force_bytes(test_usuario.pk))
        token = default_token_generator.make_token(test_usuario)
        url = reverse("flipigames:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
        
        primera_respuesta = client.get(url)
        assert primera_respuesta.status_code == 302
        
        respuesta = client.get(primera_respuesta.url)
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/password_reset_confirm.html")
        assert respuesta.context["validlink"] is True
        
    def test_restablece_contrasena_y_inicia_sesion(self, client, test_usuario):
        """Comprueba que se puede restablecer la contraseña y luego iniciar sesión con la nueva contraseña"""
        uid = urlsafe_base64_encode(force_bytes(test_usuario.pk))
        token = default_token_generator.make_token(test_usuario)
        url = reverse("flipigames:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
        url_formulario = client.get(url).url
        respuesta = client.post(url_formulario, {"new_password1": "NuevaPassword123", "new_password2": "NuevaPassword123"})
        
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("flipigames:password_reset_complete")
        
        test_usuario.refresh_from_db()
        assert test_usuario.check_password("NuevaPassword123")
        assert client.login(username=test_usuario.username, password="NuevaPassword123")
        
    def test_token_invalido_muestra_error(self, client, test_usuario):
        """Comprueba que un token inválido muestra un error en la página de restablecimiento de contraseña"""
        uid = urlsafe_base64_encode(force_bytes(test_usuario.pk))
        url = reverse("flipigames:password_reset_confirm", kwargs={"uidb64": uid, "token": "token-invalido"})
        respuesta = client.get(url)
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/password_reset_confirm.html")
        assert respuesta.context["validlink"] is False
        
    def test_no_acepta_contrasenas_distintas(self, client, test_usuario):
        """Comprueba que no se aceptan contraseñas distintas en el formulario de restablecimiento"""
        uid = urlsafe_base64_encode(force_bytes(test_usuario.pk))
        token = default_token_generator.make_token(test_usuario)
        url = reverse("flipigames:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
        url_formulario = client.get(url).url
        respuesta = client.post(url_formulario, {"new_password1": "NuevaPassword123", "new_password2": "OtraPassword123"})
                
        assert respuesta.status_code == 200
        assert "new_password2" in respuesta.context["form"].errors
        
    def test_pantalla_final(self, client):
        """Comprueba que se muestra la pantalla final de restablecimiento de contraseña"""
        respuesta = client.get(reverse("flipigames:password_reset_complete"))
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "flipigames/password_reset_complete.html")
        