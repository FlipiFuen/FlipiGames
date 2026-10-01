
import pytest
from datetime import date, timedelta, datetime
from unittest.mock import MagicMock, mock_open, patch

from django.utils import timezone
from django.urls import reverse
from django.db import DatabaseError
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.conf import settings

from pytest_django.asserts import assertTemplateUsed, assertRedirects

from juegos import services
from juegos.models import Partida
from torneo.models import Torneo

# Marcador para indicar que las pruebas en este archivo necesitan acceso a la base de datos
pytestmark = pytest.mark.django_db

# ----- Fixtures: Datos de prueba reutilizables
@pytest.fixture
def test_usuario():
    """Crea y devuelve un usuario de prueba"""
    return User.objects.create_user(username="testuser", password="PasswordTest123")

@pytest.fixture
def usuario_logueado(client, test_usuario):
    """Devuelve un cliente de Django con un usuario de prueba logueado"""
    client.login(username="testuser", password="PasswordTest123")
    return client

@pytest.fixture
def semana_actual():
    """Devuelve la semana actual"""
    return timezone.localdate().isocalendar().week

@pytest.fixture
def participacion_torneo(test_usuario, semana_actual):
    """Crea una participación de torneo para el usuario de prueba en la semana actual"""
    return Torneo.objects.create(user=test_usuario, anio=services.obtener_anio_actual(), semana=semana_actual)

@pytest.fixture
def datos_partida_libre():
    """Prepara datos para registrar una partida libre"""
    return {
        "juego": "pptls",
        "puntos": 3,
        "ganado": True
    }

@pytest.fixture
def request_con_mensajes(rf):
    request = rf.get("/")
    request.session = {}
    request._messages = FallbackStorage(request)
    return request

def assert_redirect_with_message(respuesta, url_esperado, texto_esperado):
    """Comprueba una redirección y que aparece el mensaje esperado"""
    assertRedirects(respuesta, url_esperado)
    mensajes = list(get_messages(respuesta.wsgi_request))
    assert len(mensajes) >= 1
    assert texto_esperado in str(mensajes[0])

# ----- Pruebas para funciones auxiliares
class TestFuncionesAuxiliares:
    """Pruebas unitarias para las funciones auxiliares de los juegos"""
    
    def test_es_fin_de_semana_lunes(self):
        """Verifica que la función devuelve False para un lunes"""
        fecha_lunes = datetime(2026, 9, 14, 12, 0)
        
        with patch("juegos.services.timezone.localtime", return_value = fecha_lunes):
            
            assert services.es_fin_semana() is False

    def test_es_fin_semana_sabado(self):
        """Verifica que la función devuelve True para un sábado"""
        fecha_sabado = datetime(2026, 9, 19, 12, 0)
        
        with patch("juegos.services.timezone.localtime", return_value = fecha_sabado):

            assert services.es_fin_semana() is True
            
    def test_obtener_semana_actual(self):
        """Verifica que la función devuelve la semana actual correctamente"""
        fecha = date(2026, 5, 10)
        
        with patch("juegos.services.timezone.localdate", return_value=fecha):

            assert services.obtener_semana_actual() == fecha.isocalendar().week
            
    def test_limpiar_sesion_elimina_existentes(self):
        """Verifica que la función elimina correctamente las claves existentes de la sesión"""
        request = MagicMock()
        request.session = {"a": 1, "b": 2}
        
        services.limpiar_sesion(request, ["a", "inexistente"])
        
        assert request.session == {"b": 2}
        
    def test_registrar_partida_libre_correctamente(self, test_usuario, rf):
        """Verifica que se registra correctamente una partida libre en la base de datos"""
        request = rf.get("/")
        services.registrar_partida_libre(request, test_usuario, "pptls")
        
        assert Partida.objects.filter(user=test_usuario, juego="pptls").exists()
        
    def test_registrar_partida_libre_muestra_error(self, test_usuario, request_con_mensajes):
        """Verifica que se muestre un error al intentar registrar una partida libre en la base de datos"""
        request = request_con_mensajes
        
        with patch("juegos.services.Partida.objects.create", side_effect=DatabaseError):
            services.registrar_partida_libre(request, test_usuario, "pptls")
            
        mensajes = list(get_messages(request))
        assert len(mensajes) == 1
        assert str(mensajes[0]) == "Hubo un error al registrar la partida"
        
    def test_validar_participacion_torneo_valida(self, request, participacion_torneo):
        """Verifica que la función devuelve la participación correcta si el usuario está inscrito en el torneo"""
        request.user = participacion_torneo.user
        resultado = services.validar_participacion_torneo(request, "ahorcado")
        
        assert resultado == participacion_torneo
        
    def test_validar_participacion_torneo_alcanza_limite(self, request_con_mensajes, participacion_torneo):
        """Verifica que la función devuelve None y muestra un mensaje si el usuario ha alcanzado el límite de partidas para el torneo"""
        request = request_con_mensajes
        request.user = participacion_torneo.user
        participacion_torneo.juegos_ahorcado = services.MAX_PARTIDAS_TORNEO
        participacion_torneo.save()
        
        resultado = services.validar_participacion_torneo(request, "ahorcado")
        
        assert resultado is None
        mensajes = list(get_messages(request))
        assert "Ya has jugado tus" in str(mensajes[0])
    
    def test_validar_participacion_torneo_sin_inscripcion(self, request_con_mensajes, test_usuario):
        """Verifica que la función devuelve None y muestra un mensaje si el usuario no está inscrito en el torneo"""
        request = request_con_mensajes
        request.user = test_usuario
        resultado = services.validar_participacion_torneo(request, "ahorcado")
        
        assert resultado is None
        mensajes = list(get_messages(request))
        assert "Debes estar apuntado" in str(mensajes[0])
    
    @pytest.mark.parametrize(  # nos permite ejecutar la misma prueba con diferentes conjuntos de datos
        "juego, resultado, esperado",
        [
            ("ahorcado", "victoria", {"puntos_ahorcado": 3, "juegos_ahorcado": 1}),
            ("ahorcado", "derrota", {"juegos_ahorcado": 1}),
            ("piedra", "victoria", {"puntos_piedra": 3, "juegos_piedra": 1}),
            ("piedra", "empate", {"puntos_piedra": 1, "juegos_piedra": 1}),
            ("piedra", "derrota", {"juegos_piedra": 1}),
            ("adivina", "victoria", {"juegos_adivina": 1}),
            ("juego_inexistente", "victoria", {}),
            ("ahorcado", "resultado_invalido", {}),
        ],
    )
    
    def test_calcular_incrementos_torneo(self, juego, resultado, esperado):
        """Verifica que los incrementos de puntos se calculen correctamente"""
        assert services.calcular_incrementos_torneo(juego, resultado) == esperado
        
    def test_calcular_incrementos_resultado_invalido(self):
        """Un resultado desconocido no debe modificar el torneo"""
        assert services.calcular_incrementos_torneo("ahorcado", "resultado_invalido") == {}
        
    def test_aplicar_incrementos_propaga_error_base_de_datos(self, participacion_torneo):
        """Verifica que se propaga un error de base de datos al aplicar incrementos al torneo"""
        participacion_bloqueada = Torneo.objects.get(pk=participacion_torneo.pk)
        
        with patch("juegos.services.Torneo.objects.select_for_update") as select_for_update:
            select_for_update.return_value.get.return_value = (participacion_bloqueada)
            
            with patch.object(participacion_bloqueada, "save", side_effect=DatabaseError("fallo")):
                
                with pytest.raises(DatabaseError, match="fallo"):
                    services.aplicar_incrementos_torneo(participacion_torneo, "ahorcado", "victoria")
                
    def test_aplicar_incrementos_no_supera_limite_ahorcado(self, participacion_torneo):
        
        participacion_torneo.juegos_ahorcado = services.MAX_PARTIDAS_TORNEO
        participacion_torneo.puntos_ahorcado = 30
        participacion_torneo.save()
        
        resultado = services.aplicar_incrementos_torneo(participacion_torneo, "ahorcado", "victoria")
        
        participacion_torneo.refresh_from_db()
        
        assert resultado is False
        assert participacion_torneo.juegos_ahorcado == services.MAX_PARTIDAS_TORNEO
        assert participacion_torneo.puntos_ahorcado == 30
    
    # Pruebas para la lógica de PPTLS
    @pytest.mark.parametrize(
        "jugador, cpu, esperado",
        [
            ("piedra", "piedra", "empate"),
            ("papel", "papel", "empate"),
            ("tijera", "tijera", "empate"),
            ("tijera", "papel", "victoria"),
            ("papel", "tijera", "derrota"),
            ("papel", "piedra", "victoria"),
            ("piedra", "tijera", "victoria"),
            ("tijera", "piedra", "derrota"),
            ("lagarto", "spock", "victoria"),
            ("spock", "spock", "empate"),
            ("spock", "tijera", "victoria"),
            ("piedra", "lagarto", "victoria"),
            ("lagarto", "piedra", "derrota"),
            ("lagarto", "lagarto", "empate"),
            ("spock", "piedra", "victoria"),
            ("spock", "lagarto", "derrota"),
            ("lagarto", "papel","victoria"),
        ]
    )
    
    def test_determinar_resultado_pptls(self, jugador, cpu, esperado):
        """Comprueba la lógica de victoria, empate y derrota en PPTLS"""
        assert services.determinar_resultado_pptls(jugador, cpu) == esperado
        
    @pytest.mark.parametrize(
        "jugador,cpu,esperado",
        [
            ("papel", "spock", "victoria"),
            ("tijera", "lagarto", "victoria"),
            ("valor_invalido", "piedra", "derrota"),
        ]
    )
    def test_determinar_resultado_pptls_casos_faltantes(self, jugador, cpu, esperado):
        """Comprueba casos faltantes y valores inválidos en PPTLS"""
        assert services.determinar_resultado_pptls(jugador, cpu) == esperado
    
    def test_personalizar_mensaje_pptls(self):
        """Comprueba el mensaje personalizado en PPTLS"""
        assert services.personalizar_mensaje("piedra", "papel") == "Papel tapa a Piedra"
        assert services.personalizar_mensaje("papel", "tijera") == "Tijeras cortan a Papel"
        assert services.personalizar_mensaje("tijera", "lagarto") == "Tijeras decapitan a Lagarto"
        assert services.personalizar_mensaje("lagarto", "spock") == "Lagarto envenena a Spock"
        assert services.personalizar_mensaje("spock", "tijera") == "Spock destroza a Tijeras"
        
    def test_personalizar_mensaje_combinacion_inexistente(self):
        
        assert services.personalizar_mensaje("invalido", "desconocido") is None
        
    def test_actualizar_marcador_sesion_vacia(self):
        
        session = {}
        resultado = services.actualizar_marcador_pptls(session, "victoria")
        
        assert resultado == {
            "victorias": 1,
            "derrotas": 0,
            "empates": 0,
        }
        assert session == resultado
        
    def test_actualizar_marcador_resultado_invalido(self):
        
        session = {}
        resultado = services.actualizar_marcador_pptls(session, "resultado_invalido")
        
        assert resultado == {
            "victorias": 0,
            "derrotas": 0,
            "empates": 0,
        }
        
    # Pruebas para la lógica de Ahorcado
    
    # Usamos 'patch' para aislar las pruebas de dependencias externas como la aleatoriedad (random.choice), el sistema de archivos (get_palabra) o la fecha actual (date.today)
    @patch("juegos.services.get_palabra", return_value="CASA")
    def test_inicializar_ahorcado(self, mock_get_palabra):
        
        session = {}
        resultado = services.inicializar_ahorcado(session)
        
        assert resultado == {
            "palabra_secreta": "CASA",
            "letras_usadas": [],
            "letras_acertadas": [],
            "fallos": 0
        }
        assert session == resultado 
        
    @patch("juegos.services.get_palabra", return_value=None)
    def test_inicializar_ahorcado_sin_palabra(self, mock_get_palabra):
        """Verifica que no se inicializa el juego si no hay palabra disponible"""
        
        session = {"palabra_secreta": "ANTERIOR"}
        resultado = services.inicializar_ahorcado(session)
        
        assert resultado is None
        assert session == {"palabra_secreta": "ANTERIOR"}
    
    def test_procesar_jugada_ahorcado(self, rf, test_usuario):
        """Verifica el procesamiento de una jugada en Ahorcado"""
        
        # Acierto
        request = rf.post("/", {"letra": "T"})
        request.user = test_usuario
        request.session = {
            "palabra_secreta": "TEST",
            "letras_usadas": [],
            "letras_acertadas": [],
            "fallos": 0,
        }
        resultado = services.procesar_jugada_ahorcado(request, partida_torneo=False, participacion_torneo=None)
        
        assert resultado["letras_acertadas"] == ["T"]
        assert resultado["fallos"] == 0
        assert resultado["juego_ganado"] is False
        assert resultado["juego_perdido"] is False
        
        # Fallo
        request = rf.post("/", {"letra": "X"})
        request.user = test_usuario
        request.session = {
            "palabra_secreta": "TEST",
            "letras_usadas": ["T"],
            "letras_acertadas": ["T"],
            "fallos": 0,
        }
        resultado = services.procesar_jugada_ahorcado(request, partida_torneo=False, participacion_torneo=None)
                
        assert resultado["letras_acertadas"] == ["T"]
        assert resultado["fallos"] == 1
        assert resultado["juego_ganado"] is False
        assert resultado["juego_perdido"] is False
        
        # Jugada Ganadora
        request = rf.post("/", {"letra": "S"})
        request.user = test_usuario
        request.session = {
            "palabra_secreta": "TEST",
            "letras_usadas": ["T", "E"],
            "letras_acertadas": ["T", "E"],
            "fallos": 0,
        }
        resultado = services.procesar_jugada_ahorcado(request, partida_torneo=False, participacion_torneo=None)
        
        assert set(resultado["letras_acertadas"]) == {"T", "E", "S"}
        assert resultado["juego_ganado"] is True
        
        # Jugada Perdida
        request = rf.post("/", {"letra": "A"})
        request.user = test_usuario
        request.session = {
            "palabra_secreta": "TEST",
            "letras_usadas": [],
            "letras_acertadas": [],
            "fallos": services.MAX_FALLOS_AHORCADO - 1,
        }
        resultado = services.procesar_jugada_ahorcado(request, partida_torneo=False, participacion_torneo=None)
        
        assert resultado["fallos"] == services.MAX_FALLOS_AHORCADO
        assert resultado["juego_perdido"] is True       
        
    def test_procesar_jugada_ahorcado_ultimo_fallo(self, rf, test_usuario):
        """Verifica que se detecta correctamente la pérdida cuando se alcanza el máximo de fallos"""
        request = rf.post("/", {"letra": "X"})
        request.user = test_usuario
        request.session = {
            "palabra_secreta": "CASA",
            "letras_usadas": [],
            "letras_acertadas": [],
            "fallos": services.MAX_FALLOS_AHORCADO - 1,
        }
        resultado = services.procesar_jugada_ahorcado(request, partida_torneo=False, participacion_torneo=None)
        
        assert resultado["fallos"] == services.MAX_FALLOS_AHORCADO
        assert resultado["juego_perdido"] is True
        
    def test_procesar_jugada_ahorcado_ultima_letra(self, rf, test_usuario):
        """Verifica que se detecta correctamente la victoria cuando se acierta la última letra"""
        request = rf.post("/", {"letra": "A"})
        request.user = test_usuario
        request.session = {
            "palabra_secreta": "CASA",
            "letras_usadas": ["C", "S"],
            "letras_acertadas": ["C", "S"],
            "fallos": 0,
        }
        resultado = services.procesar_jugada_ahorcado(request, partida_torneo=False, participacion_torneo=None)
        assert resultado["juego_ganado"] is True
        assert resultado["juego_perdido"] is False
        
    @patch("juegos.services.random.randint", return_value=4)
    @patch("builtins.open", mock_open(read_data="casa\nluna\n")) # Simula un archivo con palabras
    def test_get_palabra_devuelve_palabra_mayusculas(self, mock_randint):
        """Verifica que la función devuelve una palabra aleatoria en mayúsculas"""
        
        with patch("juegos.services.random.choice", return_value="casa"):
            assert services.get_palabra() == "CASA"
            
    @patch("juegos.services.random.randint", return_value=4)
    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_palabra_archivo_inexistente(self, mock_open_file, mock_randint):
        """Verifica que la función devuelve None si el archivo de palabras no existe"""
        
        assert services.get_palabra() is None
        
    @patch("juegos.services.random.randint", return_value=4)
    @patch("builtins.open", mock_open(read_data=""))
    def test_get_palabra_archivo_vacio(self, mock_randint):
        """Verifica que la función devuelve None si el archivo de palabras está vacío"""
        assert services.get_palabra() is None
    
    # Pruebas para la lógica de Adivina el Número
    
    def test_generar_numero_secreto(self):
        """Verifica que se genera un número de 4 dígitos único"""
        numero_secreto = services.generar_numero_secreto()
        assert len(numero_secreto) == 4
        assert len(set(numero_secreto)) == 4
        assert all(digito.isdigit() for digito in numero_secreto)
        
    def test_inicializar_partida_adivina(self):
        """Verifica que se inicializa correctamente la partida de Adivina el Número"""
        session = {}

        with patch(
            "juegos.services.generar_numero_secreto",
            return_value=["1", "2", "3", "4"],
        ):
            services.inicializar_partida_adivina(session)

        assert session == {
            "numero_secreto": ["1", "2", "3", "4"],
            "intentos": 0,
            "historial_jugadas": [],
            "juego_ganado": False,
            "jugada_actual": "",
            "start_time_adivina": None,
            "tiempo_partida": None,
        }
        
    def test_manejar_teclado_rechaza_digito_repetido(self):
        """Verifica que no se añaden dígitos repetidos a la jugada actual"""
        session = {"jugada_actual": "12"}
        resultado = services.manejar_teclado_adivina(session, {"digito": "2"})
        
        assert resultado == "12" 
        
    def test_manejar_teclado_rechaza_digito_invalido(self):
        """Verifica que no se añaden dígitos no numéricos a la jugada actual"""
        session = {"jugada_actual": "12"}
        resultado = services.manejar_teclado_adivina(session,{"digito": "abc"})
        
        assert resultado == "12"
        assert session["jugada_actual"] == "12"
        
    def test_manejar_teclado_acepta_digito_valido(self):
        """Verifica que se añaden dígitos válidos a la jugada actual"""
        session = {"jugada_actual": "12"}
        resultado = services.manejar_teclado_adivina(session, {"digito": "3"})
        
        assert resultado == "123"
        assert session["jugada_actual"] == "123"
         
        
    def test_manejar_teclado_rechaza_quinto_digito(self):
        """Verifica que no se añaden más de 4 dígitos a la jugada actual"""
        session = {"jugada_actual": "1234"}
        resultado = services.manejar_teclado_adivina(session, {"digito": "5"})
        
        assert resultado == "1234"
    
    @pytest.mark.parametrize(
        "secreto, intento, esperado_aciertos, esperado_coincidencias",
        [
            (["1", "2", "3", "4"], "1234", 4, 0), # 
            (["1", "2", "3", "4"], "4321", 0, 4), # 0 aciertos)
            (["1", "2", "3", "4"], "1243", 2, 2), # 2 aciertos, 2 coincidencias
            (["1", "2", "3", "4"], "5678", 0, 0), # 0 aciertos, 0 coincidencias
            (["1", "2", "3", "4"], "1567", 1, 0), # 1 acierto, 0 coincidencias
            (["1", "2", "3", "4"], "5167", 0, 1), # 0 aciertos, 1 coincidencia
        ],
    )
    
    def test_procesar_jugada_adivina(self, secreto, intento, esperado_aciertos, esperado_coincidencias):
        """Verifica el cálculo de aciertos y coincidencias en Adivina el Número"""
        resultado = services.procesar_jugada_adivina(secreto, intento)
        assert resultado["aciertos"] == esperado_aciertos
        assert resultado["coincidencias"] == esperado_coincidencias
        
    def test_procesar_jugada_adivina_vacia(self):
        """Verifica que procesar una jugada vacía devuelve el estado inicial"""
        resultado = services.procesar_jugada_adivina(["1", "2", "3", "4"], "")
        
        assert resultado == {
            "jugada": "",
            "aciertos": 0,
            "coincidencias": 0,
            "resultado_digitos": []
        }
        
    def test_actualizar_puntuacion_adivina_mejora(self, participacion_torneo):
        """Verifica que la puntuación de Adivina el Número se actualiza correctamente si mejora"""
        participacion_torneo.juegos_adivina = 1
        participacion_torneo.intentos_adivina = 5
        participacion_torneo.tiempo_adivina = 30
        participacion_torneo.save()
        
        resultado = services.actualizar_puntuacion_torneo_adivina(participacion_torneo, intentos=3, tiempo_partida=20)
        
        participacion_torneo.refresh_from_db()
        
        assert resultado is True
        assert participacion_torneo.juegos_adivina == 2
        assert participacion_torneo.intentos_adivina == 3
        assert participacion_torneo.tiempo_adivina == 20
        
    def test_actualizar_puntuacion_adivina_no_empeora(self, participacion_torneo):
        """Verifica que la puntuación de Adivina el Número no se actualiza si no mejora"""
        participacion_torneo.juegos_adivina = 1
        participacion_torneo.intentos_adivina = 3
        participacion_torneo.tiempo_adivina = 20
        participacion_torneo.save()
        
        resultado = services.actualizar_puntuacion_torneo_adivina(participacion_torneo, intentos=5, tiempo_partida=30)
        
        participacion_torneo.refresh_from_db()
        
        assert resultado is True
        assert participacion_torneo.intentos_adivina == 3
        assert participacion_torneo.tiempo_adivina == 20
        assert participacion_torneo.juegos_adivina == 2

class TestAhorcadoView:
    """Pruebas para la vista de Ahorcado"""
    
    def test_acceso_sin_login(self, client):
        """Comprueba que redirige al login si el usuario no está autenticado"""
        url = reverse("juegos:ahorcado")
        respuesta = client.get(url)
        assertRedirects(respuesta, f"{reverse(settings.LOGIN_URL)}?next={url}")
        
    def test_ahorcado_modo_invalido_devuelve_404(self, usuario_logueado):
        
        url = reverse("juegos:ahorcado_modo", kwargs={"modo_juego": "inventado"})
        respuesta = usuario_logueado.get(url)
        
        assert respuesta.status_code == 404
        
    @patch("juegos.services.es_fin_semana", return_value=True)
    def test_ahorcado_torneo_fin_de_semana(self, mock_es_fin_semana, usuario_logueado):
        """Comprueba que se redirige si el juego Ahorcado en modo torneo se intenta acceder en fin de semana"""
        url = reverse("juegos:ahorcado_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert_redirect_with_message(respuesta, reverse("torneo:torneo"), "sólo está disponible")

    def test_get_primera_vez(self, usuario_logueado):
        """Verifica la carga inicial de la página del juego"""
        
        respuesta = usuario_logueado.get(reverse("juegos:ahorcado"))
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "juegos/ahorcado.html")
        assert respuesta.context["primera_vez"] is True
        assert "palabra_secreta" not in usuario_logueado.session
        
    
    @patch("juegos.services.get_palabra", return_value = "TEST")
    def test_post_iniciar_partida(self, mock_get_palabra, usuario_logueado):
        """Comprueba que una petición POST sin estado de juego inicializa una nueva partida"""
        
        respuesta = usuario_logueado.post(reverse("juegos:ahorcado"))
        assert respuesta.status_code == 200
        assert usuario_logueado.session["palabra_secreta"] == "TEST"
        assert usuario_logueado.session["letras_usadas"] == []
        assert usuario_logueado.session["letras_acertadas"] == []
        assert usuario_logueado.session["fallos"] == 0
        assert respuesta.context["primera_vez"] is False
        
    @patch("juegos.services.get_palabra", return_value="TEST")
    def test_post_letra_correcta(self, mock_get_palabra, usuario_logueado):
        """Verifica el comportamiento al pulsar una letra correcta"""
        # Iniciar Partida
        usuario_logueado.post(reverse("juegos:ahorcado"))
        # Enviar Letra
        respuesta = usuario_logueado.post(reverse("juegos:ahorcado"), {"letra": "T"})
        assert respuesta.status_code == 200
        assert usuario_logueado.session["letras_acertadas"] == ["T"]
        assert usuario_logueado.session["fallos"] == 0
    
    @patch("juegos.services.get_palabra", return_value = "TEST")    
    def test_post_letra_incorrecta(self, mock_get_palabra, usuario_logueado):
        """Verifica el comportamiento al pulsar una letra incorrecta"""
        
        usuario_logueado.post(reverse("juegos:ahorcado"))
        respuesta = usuario_logueado.post(reverse("juegos:ahorcado"), {"letra": "X"})
        assert respuesta.status_code == 200
        assert "X" not in usuario_logueado.session["letras_acertadas"]
        assert usuario_logueado.session["fallos"] == 1
        
    @patch("juegos.services.get_palabra", return_value="TEST")
    def test_post_letra_invalida_no_modifica_la_partida(self, mock_get_palabra, usuario_logueado):
        
        url = reverse("juegos:ahorcado")
        usuario_logueado.post(url)
        respuesta = usuario_logueado.post(url, {"letra": "123"})
        
        assert respuesta.status_code == 200
        assert usuario_logueado.session["letras_usadas"] == []
        assert usuario_logueado.session["letras_acertadas"] == []
        assert usuario_logueado.session["fallos"] == 0
        
    @patch("juegos.services.es_fin_semana", return_value=False)
    def test_ahorcado_torneo_sin_inscripcion(self, mock_es_fin_semana, usuario_logueado):
        """Verifica que no se puede jugar en torneo sin estar inscrito"""
        
        url = reverse("juegos:ahorcado_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert_redirect_with_message(respuesta, reverse("torneo:torneo"), "Debes estar apuntado")
    
    @patch("juegos.services.es_fin_semana", return_value = False)  
    @patch("juegos.services.get_palabra", return_value ="A")
    def test_post_ganar_partida_torneo(self, mock_get_palabra, mock_es_fin_semana, usuario_logueado, participacion_torneo):
        """Comprueba que se ganan puntos de torneo al ganar una partida"""
        
        url = reverse("juegos:ahorcado_modo", kwargs={"modo_juego": "torneo"})
        usuario_logueado.post(url) # Iniciar
        usuario_logueado.post(url, {"letra": "A"}) # Ganar partida
        
        participacion_torneo.refresh_from_db()
        assert participacion_torneo.juegos_ahorcado == 1
        assert participacion_torneo.puntos_ahorcado == 3
        
    @patch("juegos.services.es_fin_semana", return_value = False)  
    @patch("juegos.services.get_palabra", return_value ="A")
    def test_ahorcado_torneo_derrota(self, mock_get_palabra, mock_es_fin_semana, usuario_logueado, participacion_torneo):
        """Comprueba que no se ganan puntos de torneo al perder una partida"""
        
        url = reverse("juegos:ahorcado_modo", kwargs={"modo_juego": "torneo"})
        usuario_logueado.post(url) # Iniciar
        
        letras_erroneas = "BCDEFGH"
        for letra in letras_erroneas:
            usuario_logueado.post(url, {"letra": letra})
            
        participacion_torneo.refresh_from_db()
        
        assert participacion_torneo.juegos_ahorcado == 1
        assert participacion_torneo.puntos_ahorcado == 0

    @patch("juegos.services.es_fin_semana", return_value=False)
    def test_torneo_limite_partidas_alcanzado(self, mock_es_fin_semana, usuario_logueado, participacion_torneo):
        """Comprueba que se redirige si se ha alcanzado el límite de partidas para el torneo"""
        participacion_torneo.juegos_ahorcado = services.MAX_PARTIDAS_TORNEO
        participacion_torneo.save()
        
        url = reverse("juegos:ahorcado_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert_redirect_with_message(respuesta, reverse("torneo:torneo"), "Ya has jugado tus")
        
    @patch("juegos.services.get_palabra", return_value="A")
    def test_ahorcado_libre_victoria(self, mock_get_palabra, usuario_logueado, test_usuario):
        """Comprueba que se registra una partida libre al ganar en modo libre"""
        
        url = reverse("juegos:ahorcado")
        usuario_logueado.post(url)
        usuario_logueado.post(url, {"letra": "A"})
        
        assert Partida.objects.filter(user=test_usuario, juego="ahorcado").exists()
        
    @patch("juegos.services.get_palabra", return_value="AB")
    def test_ahorcado_no_repite_partida_terminada(self, mock_get_palabra, usuario_logueado, test_usuario):
        
        url = reverse("juegos:ahorcado")
        
        usuario_logueado.post(url)
        usuario_logueado.post(url,  {"letra": "A"})
        usuario_logueado.post(url,  {"letra": "B"})
        usuario_logueado.post(url,  {"letra": "C"})
        
        assert Partida.objects.filter(user=test_usuario, juego="ahorcado").count() == 1
        
    @patch("juegos.services.get_palabra", side_effect=["CASA", "LUNA"])
    def test_ahorcado_volver_a_jugar(self, mock_get_palabra, usuario_logueado):
        """Comprueba que al pulsar 'Volver a jugar' se reinicia la partida con una nueva palabra"""
        url = reverse("juegos:ahorcado")
        usuario_logueado.post(url)
        usuario_logueado.post(url, {"letra": "C"})
        respuesta = usuario_logueado.post(url, {"volver_jugar": "1"})
        
        assert respuesta.status_code == 200
        assert usuario_logueado.session["palabra_secreta"] == "LUNA"
        assert usuario_logueado.session["letras_usadas"] == []
        assert usuario_logueado.session["letras_acertadas"] == []
        assert usuario_logueado.session["fallos"] == 0
        
    @patch("juegos.services.get_palabra", return_value=None)
    def test_ahorcado_error_al_inicializar(self, mock_get_palabra, usuario_logueado):
        """Comprueba que se muestra un mensaje de error si no se puede inicializar el juego"""
        url = reverse("juegos:ahorcado")
        respuesta = usuario_logueado.post(url)
        
        assert_redirect_with_message(respuesta, url, "No se pudo iniciar el juego")
        
class TestPPTLSView:
    """Pruebas para la vista de Piedra-Papel-Tijera-Lagarto-Spock"""
    
    def test_pptls_modo_invalido_devuelve_404(self, usuario_logueado):
            
            url = reverse("juegos:pptls_modo", kwargs={"modo_juego": "inventado"})
            respuesta = usuario_logueado.get(url)
            
            assert respuesta.status_code == 404
    
    def test_acceso_sin_login(self, client):
            """Comprueba que redirige al login si el usuario no está autenticado"""
            url = reverse("juegos:pptls")
            respuesta = client.get(url)
            assertRedirects(respuesta, f"{reverse(settings.LOGIN_URL)}?next={url}")

    def test_get_primera_vez(self, usuario_logueado):
            """Verifica la carga inicial de la página del juego"""
            respuesta = usuario_logueado.get(reverse("juegos:pptls"))
            assert respuesta.status_code == 200
            assertTemplateUsed(respuesta, "juegos/pptls.html")
            assert respuesta.context["primera_vez"] is True
            assert "victorias" not in usuario_logueado.session
            
    def test_post_iniciar_partida(self, usuario_logueado):
        """Comprueba que un POST sin elección del jugador muestra la pantalla del juego"""
        respuesta = usuario_logueado.post(reverse("juegos:pptls"))
        assert respuesta.status_code == 200
        assert respuesta.context["primera_vez"] is False
        assert "eleccion_jugador" not in respuesta.context
        
    def test_post_jugada_invalida_no_registra_partida(self, usuario_logueado, test_usuario):
        """Comprueba que un POST con una jugada inválida no registra la partida"""
        respuesta = usuario_logueado.post(reverse("juegos:pptls"), {"eleccion": "jugada_inventada"})
        
        assert respuesta.status_code == 200
        assert "resultado" not in respuesta.context
        assert usuario_logueado.session.get("victorias", 0) == 0
        assert usuario_logueado.session.get("derrotas", 0) == 0
        assert usuario_logueado.session.get("empates", 0) == 0
        assert not Partida.objects.filter(user=test_usuario, juego="pptls").exists()
        
        
    @patch("random.choice", return_value="tijera")
    def test_post_jugar_ganar(self, mock_random_choice, usuario_logueado):
        """Verifica el comportamiento al ganar una partida"""
        respuesta = usuario_logueado.post(reverse("juegos:pptls"), {"eleccion": "piedra"})
        assert respuesta.status_code == 200
        assert respuesta.context["resultado"] == "victoria"
        assert respuesta.context["eleccion_cpu"] == "tijera"
        assert respuesta.context["eleccion_jugador"] == "piedra"
        assert usuario_logueado.session["victorias"] == 1
        assert usuario_logueado.session["derrotas"] == 0
    
    @patch("juegos.services.es_fin_semana", return_value = False)   
    @patch("random.choice", return_value="piedra")
    def test_post_jugar_empatar(self, mock_random_choice, mock_es_fin_semana, usuario_logueado, participacion_torneo):
        """Verifica el comportamiento al empatar una partida"""
        url = reverse("juegos:pptls_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.post(url, {"eleccion": "piedra"})
        
        assert respuesta.status_code == 200
        assert respuesta.context["resultado"] == "empate"
        
        participacion_torneo.refresh_from_db()
        assert participacion_torneo.juegos_piedra == 1
        assert participacion_torneo.puntos_piedra == 1
    
    @patch("juegos.services.es_fin_semana", return_value = False)    
    @patch("random.choice", return_value="papel")
    def test_post_jugar_perder(self, mock_random_choice, mock_es_fin_semana, usuario_logueado, participacion_torneo):
        """Verifica el comportamiento al perder una partida"""
        url = reverse("juegos:pptls_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.post(url, {"eleccion": "piedra"})
        
        assert respuesta.status_code == 200
        assert respuesta.context["resultado"] == "derrota"
        assert respuesta.context["eleccion_cpu"] == "papel"
        assert respuesta.context["eleccion_jugador"] == "piedra"
        
        participacion_torneo.refresh_from_db()
        assert participacion_torneo.juegos_piedra == 1
        assert usuario_logueado.session["victorias"] == 0
        assert usuario_logueado.session["derrotas"] == 1
    
    @patch("juegos.services.es_fin_semana", return_value = False)
    def test_torneo_sin_inscripcion(self, mock_es_fin_semana, usuario_logueado):
        """Comprueba que se redirige si el usuario no está inscrito en el torneo"""
        url = reverse("juegos:pptls_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assertRedirects(respuesta, reverse("torneo:torneo"))
        mensajes = list(get_messages(respuesta.wsgi_request))
        assert "Debes estar apuntado" in str(mensajes[0])
        
    @patch("juegos.services.es_fin_semana", return_value = True)
    def test_pptls_torneo_fin_semana(self, mock_es_fin_semana, usuario_logueado):
        """Comprueba que se redirige si el juego PPTLS en modo torneo se intenta acceder en fin de semana"""
        url = reverse("juegos:pptls_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert_redirect_with_message(respuesta, reverse("torneo:torneo"), "sólo está disponible")
        
    @patch("juegos.services.es_fin_semana", return_value=False)
    @patch("random.choice", return_value="tijera")
    def test_pptls_torneo_victoria(self, mok_random_choice, mock_es_fin_semana, usuario_logueado, participacion_torneo):
        """Verifica que se actualiza correctamente la puntuación del torneo al ganar una partida"""
        
        url = reverse("juegos:pptls_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.post(url, {"eleccion": "piedra"})
        
        participacion_torneo.refresh_from_db()
        
        assert respuesta.context["resultado"] == "victoria"
        assert participacion_torneo.juegos_piedra == 1
        assert participacion_torneo.puntos_piedra == 3
        
    @patch("random.choice", return_value="papel")
    def test_pptls_libre_derrota_registra_partida(self, mock_random_choice, usuario_logueado, test_usuario):
        """Comprueba que se registra una partida libre al perder en modo libre"""
        
        url = reverse("juegos:pptls")
        usuario_logueado.post(url, {"eleccion": "piedra"})
        
        assert Partida.objects.filter(user=test_usuario, juego="pptls").exists()
        
    @patch("juegos.services.es_fin_semana", return_value=False)
    def test_pptls_torneo_limite_partidas(self, mock_es_fin_semana, usuario_logueado, participacion_torneo):
        """Comprueba que se redirige si se ha alcanzado el límite de partidas para el torneo"""
        
        participacion_torneo.juegos_piedra = services.MAX_PARTIDAS_TORNEO
        participacion_torneo.save()
        
        url = reverse("juegos:pptls_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert_redirect_with_message(respuesta, reverse("torneo:torneo"), "Ya has jugado tus")
        
    @patch("juegos.services.es_fin_semana", return_value=False)
    def test_pptls_get_torneo_conserva_marcador(self, mock_es_fin_semana, usuario_logueado, participacion_torneo):
        """Verifica que el marcador de victorias se conserva al acceder a la vista del torneo"""
        session = usuario_logueado.session
        session["victorias"] = 3
        session.save()
        
        url = reverse("juegos:pptls_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert respuesta.status_code == 200
        assert usuario_logueado.session["victorias"] == 3
        
    def test_pptls_get_libre_reinicia_marcador(self, usuario_logueado):
        """Verifica que el marcador de victorias, derrotas y empates se reinicia al acceder a la vista del modo libre"""
        session = usuario_logueado.session
        session["victorias"] = 3
        session["derrotas"] = 2
        session["empates"] = 1
        session.save()
        
        respuesta = usuario_logueado.get(reverse("juegos:pptls"))
        
        assert respuesta.status_code == 200
        assert "victorias" not in usuario_logueado.session
        assert "derrotas" not in usuario_logueado.session
        assert "empates" not in usuario_logueado.session
        

class TestAdivinaNumeroView:
    """Pruebas para la vista de Adivina el Número"""
    
    def test_adivina_modo_invalido_devuelve_404(self, usuario_logueado):
            
            url = reverse("juegos:adivina_numero_modo", kwargs={"modo_juego": "inventado"})
            respuesta = usuario_logueado.get(url)
            
            assert respuesta.status_code == 404
            
    @patch("juegos.services.timezone.localdate")
    def test_adivina_acceso_torneo_valido(self, mock_date, usuario_logueado, participacion_torneo):
        """Comprueba que el juego Adivina el Número en modo torneo es accesible en sábado"""
        
        sabado = date(2026, 8, 8)
        mock_date.return_value = sabado
        semana = sabado.isocalendar().week
        
        participacion_torneo.semana = semana
        participacion_torneo.save()
        
        url = reverse("juegos:adivina_numero_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "juegos/adivina_numero.html")
    
    def test_adivina_acceso_sin_login(self, client):
        """Comprueba que redirige al login si el usuario no está autenticado"""
        url = reverse("juegos:adivina_numero")
        respuesta = client.get(url)
        assertRedirects(respuesta, f"{reverse(settings.LOGIN_URL)}?next={url}")
    
    @patch("juegos.services.timezone.localdate")
    def test_adivina_acceso_torneo_dia_incorrecto(self, mock_date, usuario_logueado, participacion_torneo):
        """Comprueba que el juego Adivina el Número en modo torneo sólo es accesible en sábado"""
        domingo = date(2026, 8, 9)
        mock_date.return_value = domingo
        
        url = reverse("juegos:adivina_numero_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert_redirect_with_message(respuesta, reverse("torneo:torneo"), "sólo está disponible los sábados")
        
    @patch("juegos.services.timezone.localdate")
    def test_adivina_acceso_torneo_top10_empates(self, mock_date, usuario_logueado, test_usuario):
        """
        Comprueba que pueden acceder más de 10 jugadores porque hay empates de puntuación y ocupan el mismo puesto (1,2,2,3,4)
        """
        hoy = date(2026, 8, 3)
        sabado = date(2026, 8, 8)
        mock_date.return_value = sabado
        semana = sabado.isocalendar().week
        
        # Creamos 10 usuarios con 30 puntos, todos ocupan el puesto 1
        for i in range(10):
            usuario = User.objects.create_user(username=f"topusuario{i}", password="PasswordTop123")
            Torneo.objects.create(user=usuario, semana=semana, juegos_ahorcado = 10, puntos_ahorcado = 30)
            
        # Usuario logueado con 20 puntos, puesto 2, debe entrar aunque ya hay 10 jugadores
        Torneo.objects.create(user=test_usuario, semana=semana, juegos_ahorcado = 10, puntos_ahorcado = 20)
        
        url = reverse("juegos:adivina_numero_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert respuesta.status_code == 200
        assertTemplateUsed(respuesta, "juegos/adivina_numero.html")

    @patch("juegos.services.timezone.localdate")
    def test_adivina_acceso_torneo_sin_ser_top10(self, mock_date,  usuario_logueado, participacion_torneo):
        """Verifica que se deniega el acceso si el usuario no está en el top10"""
        #Simulamos que es sábado
        sabado = date(2026, 8, 8)
        mock_date.return_value = sabado
        semana = sabado.isocalendar().week
        
        # Creamos 10 usuarios con más puntos que el usuario de prueba
        for i in range(10):
            usuario = User.objects.create_user(username=f"topusuario{i}", password="PasswordTop123")
            puntos = 30 - (i * 2)
            Torneo.objects.create(user=usuario, semana=semana, juegos_ahorcado = 10, puntos_ahorcado=puntos)
            
        url = reverse("juegos:adivina_numero_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert_redirect_with_message(respuesta, reverse("torneo:torneo"), "Debes estar en el top10")
        
    def test_adivina_post_manejar_teclado(self, usuario_logueado):
        """Verifica el funcionamiento del teclado virtual"""
        # Iniciar partida
        usuario_logueado.post(reverse("juegos:adivina_numero"))
        session = usuario_logueado.session
            
        # Añadir dígito
        usuario_logueado.post(reverse("juegos:adivina_numero"), {"digito": "1"})
        assert usuario_logueado.session["jugada_actual"] == "1"
            
        # Añadir otro dígito
        usuario_logueado.post(reverse("juegos:adivina_numero"), {"digito": "2"})
        assert usuario_logueado.session["jugada_actual"] == "12"
            
        # Borrar dígito
        usuario_logueado.post(reverse("juegos:adivina_numero"), {"accion": "borrar"})
        assert usuario_logueado.session["jugada_actual"] == "1"
            
        # Limpiar
        usuario_logueado.post(reverse("juegos:adivina_numero"), {"accion": "limpiar"})
        assert usuario_logueado.session["jugada_actual"] == ""
        
    @patch("juegos.services.timezone.localdate")
    def test_adivina_limite_partidas(self, mock_date, usuario_logueado, participacion_torneo):
        """Comprueba que se redirige si se ha alcanzado el límite de partidas para el torneo"""
        
        sabado = date(2026, 8, 8)
        mock_date.return_value = sabado
        semana = sabado.isocalendar().week
        
        participacion_torneo.anio = sabado.isocalendar().year
        participacion_torneo.semana = semana
        participacion_torneo.juegos_adivina = 10
        participacion_torneo.intentos_adivina = 4
        participacion_torneo.tiempo_adivina = 12
        participacion_torneo.save()
        
        url = reverse("juegos:adivina_numero_modo", kwargs={"modo_juego": "torneo"})
        respuesta = usuario_logueado.get(url)
        
        assert_redirect_with_message(respuesta, reverse("torneo:torneo"), "Ya has jugado las 10 partidas")
        
    @patch("juegos.services.generar_numero_secreto", return_value=["1", "2", "3", "4"])
    def test_adivina_intento_incorrecto(self, mock_generar_numero_secreto, usuario_logueado):
        """Verifica el comportamiento al enviar un intento incorrecto"""
        
        url = reverse("juegos:adivina_numero")
        usuario_logueado.post(url)
        
        session = usuario_logueado.session
        session["jugada_actual"] = "5678"
        session.save()
        
        respuesta = usuario_logueado.post(url, {"accion": "enviar"})
        
        assert respuesta.status_code == 200
        assert usuario_logueado.session["intentos"] == 1
        assert usuario_logueado.session["juego_ganado"] is False
        assert len(usuario_logueado.session["historial_jugadas"]) == 1
        assert usuario_logueado.session["jugada_actual"] == ""
        
    def test_adivina_no_procesa_jugada_incompleta(self, usuario_logueado):
        """Verifica que no se procesa una jugada si no tiene 4 dígitos"""
        url = reverse("juegos:adivina_numero")
        usuario_logueado.post(url)
        usuario_logueado.post(url, {"digito": "1"})
        usuario_logueado.post(url, {"accion": "enviar"})
        
        assert usuario_logueado.session["intentos"] == 0
        assert usuario_logueado.session["historial_jugadas"] == []
        
    @patch("juegos.services.generar_numero_secreto", side_effect=[
        ["1", "2", "3", "4"],
        ["5", "6", "7", "8"]
    ])
    def test_adivina_volver_jugar(self, mock_generar_numero_secreto, usuario_logueado):
        """Verifica que al pulsar 'Volver a jugar' se reinicia la partida con un nuevo número secreto"""
        url = reverse("juegos:adivina_numero")
        usuario_logueado.post(url)
        respuesta = usuario_logueado.post(url, {"volver_jugar": "1"})
        
        assert respuesta.status_code == 200
        assert usuario_logueado.session["numero_secreto"] == ["5", "6", "7", "8"]
        assert usuario_logueado.session["intentos"] == 0
        assert usuario_logueado.session["historial_jugadas"] == []
        assert usuario_logueado.session["juego_ganado"] is False
            
    @patch("juegos.services.generar_numero_secreto", return_value = ["1", "2", "3", "4"])
    def test_adivina_post_jugar_ganar(self, mock_generar_numero_secreto, usuario_logueado, participacion_torneo, test_usuario):
        """Verifica el comportamiento al ganar una partida"""
        
        url = reverse("juegos:adivina_numero")
        usuario_logueado.post(url) # Iniciar partida
        
        # Simulamos la entrada de 4 dígitos
        session = usuario_logueado.session
        session["jugada_actual"] = "1234"
        session.save()
        
        # Envía la jugada
        respuesta = usuario_logueado.post(url, {"accion": "enviar"})
        
        assert respuesta.status_code == 200
        assert usuario_logueado.session["juego_ganado"] is True
        assert usuario_logueado.session["intentos"] == 1
        historial = usuario_logueado.session["historial_jugadas"]
        assert historial[0]["aciertos"] == 4
        assert Partida.objects.filter(user=test_usuario, juego="adivina").exists()
        
    @patch("juegos.services.generar_numero_secreto", return_value=["1", "2", "3", "4"])
    def test_adivina_no_repite_partida_ganada(self, mock_generar_numero_secreto, usuario_logueado, test_usuario):
        
        url = reverse("juegos:adivina_numero")
        usuario_logueado.post(url)
        
        session = usuario_logueado.session
        session["jugada_actual"] = "1234"
        session.save()
        
        usuario_logueado.post(url, {"accion": "enviar"})
        primera_partida = Partida.objects.filter(user=test_usuario, juego="adivina").count()
        
        usuario_logueado.post(url, {"digito": "5"})
        usuario_logueado.post(url, {"accion": "enviar"})
        
        segunda_partida = Partida.objects.filter(user=test_usuario, juego="adivina").count()
        
        assert primera_partida == 1
        assert segunda_partida == 1
        assert usuario_logueado.session["juego_ganado"] is True
        
        