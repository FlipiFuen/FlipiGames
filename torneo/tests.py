import pytest
import base64
import matplotlib.pyplot as plt
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.db.models import F
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed 

from torneo.models import Torneo
from flipigames import charts
from torneo import services

# Indicamos a pytest que use la base de datos de prueba
pytestmark = pytest.mark.django_db

@pytest.fixture
def datos_torneo(monkeypatch):
    """Prepara usuarios y participantes reutilizables"""
    
    semana = 20
    anio = services.get_anio_actual()
    # Fijamos el periodo que utilizaran los servicios durante la prueba
    monkeypatch.setattr(services, "get_periodo_actual", lambda: (anio, semana))
    monkeypatch.setattr(services, "get_semana_actual", lambda: semana)
    monkeypatch.setattr(services, "get_anio_actual", lambda: anio)
    
    usuarios = [
        User.objects.create_user(username="Sol", password="Password123"),
        User.objects.create_user(username="Vero", password="Password123"),
        User.objects.create_user(username="Indhira", password="Password123"),
        User.objects.create_user(username="Ling", password="Password123"),
    ]
    
    participaciones = [
        Torneo.objects.create(
            user = usuarios[0],
            anio = anio,
            semana = semana,
            juegos_ahorcado = 10,
            puntos_ahorcado = 30,
            juegos_piedra = 4,
            puntos_piedra = 10,
            juegos_adivina = 1,
            intentos_adivina = 3,
            tiempo_adivina = 15.5
        ),
        Torneo.objects.create(
                    user = usuarios[1],
                    anio = anio,
                    semana = semana,
                    juegos_ahorcado = 7,
                    puntos_ahorcado = 21,
                    juegos_piedra = 7,
                    puntos_piedra = 20,
                    juegos_adivina = 1,
                    intentos_adivina = 2,
                    tiempo_adivina = 20.0
        ),
        Torneo.objects.create(
                    user = usuarios[2],
                    anio = anio,
                    semana = semana,
                    juegos_ahorcado = 1,
                    puntos_ahorcado = 3,
                    juegos_piedra = 0,
                    puntos_piedra = 0,
        ),
        Torneo.objects.create(
                    user = usuarios[3],
                    anio = anio,
                    semana = semana,
                    juegos_ahorcado = 0,
                    puntos_ahorcado = 0,
                    juegos_piedra = 10,
                    puntos_piedra = 30,
                    juegos_adivina = 0,
                    intentos_adivina = 0,
                    tiempo_adivina = 0,
        ),
    ]
    
    return {
        "anio": anio,
        "semana": semana,
        "usuarios": usuarios,
        "participaciones": participaciones
    }
    
@pytest.fixture
def datos_desempate(monkeypatch):
    """Crea usuarios empatados en intentos pero con distinto tiempo"""
    semana = 50
    monkeypatch.setattr(services, "get_semana_actual", lambda: semana)
    
    usuario1 = User.objects.create_user(username="JugadorRapido", password="Password123")
    usuario2 = User.objects.create_user(username="JugadorLento", password="Password123")
    
    resultado1 = Torneo.objects.create(user=usuario1, semana=semana, juegos_adivina=1, intentos_adivina=2, tiempo_adivina=10.0)
    resultado2 = Torneo.objects.create(user=usuario2, semana=semana, juegos_adivina=1, intentos_adivina=2, tiempo_adivina=25.0)

    return {"semana": semana, "rapido": resultado1, "lento": resultado2}

def test_get_semana_actual_valida():
    """Comprueba que la semana actual es un entero válido"""
    resultado = services.get_semana_actual()
    
    assert isinstance(resultado, int)
    assert 1 <= resultado <= 53
    
# ----- Pruebs de registro

def test_registro_requiere_autenticacion(client):
    """Verifica que un usuario anónimo es redirigido al login"""
    respuesta = client.get(reverse("torneo:registro_torneo"))
    
    assert respuesta.status_code == 302
    assert "login" in respuesta.url
    
def test_registro_post_crea_participacion(client, django_user_model):
    """Comprueba el registro normal de un usuario autenticado"""
    usuario = django_user_model.objects.create_user(username="nuevo", password="Password123")
    client.force_login(usuario)
    
    respuesta = client.post(reverse("torneo:registro_torneo"), {"confirmacion": "on"})
    
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("torneo:torneo")
    assert Torneo.objects.filter(user=usuario, semana=services.get_semana_actual()).exists()
    
def test_registro_rechaza_usuario_ya_registrado(client, datos_torneo):
    """Comprueba que no se duplica una participación semanal"""
    usuario = datos_torneo["usuarios"][0]
    client.force_login(usuario)
    
    respuesta = client.get(reverse("torneo:registro_torneo"))
    
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("torneo:torneo")
    assert Torneo.objects.filter(user=usuario).count() == 1
    
def test_registro_post_formulario_invalido(client, django_user_model):
    """Verifica que un formulario inválido no crea una participación"""
    usuario = django_user_model.objects.create_user(username="form_invalido", password="PasswordInvalido123")
    client.force_login(usuario)
    respuesta = client.post(reverse("torneo:registro_torneo"), {})
    
    assert respuesta.status_code == 200
    assert "form" in respuesta.context
    assert Torneo.objects.filter(user=usuario).count() == 0
    
def test_registro_captura_database_error(client, django_user_model):
    """Comprueba la redirección cuando falla la base de datos"""
    usuario = django_user_model.objects.create_user(username="db_error", password="Password123")
    client.force_login(usuario)
    
    with patch(
        "torneo.services.Torneo.objects.filter",
        side_effect = DatabaseError,
    ):
        respuesta = client.get(reverse("torneo:registro_torneo"))
        
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("torneo:torneo")
    
#-----Pruebas para gráficos
    
def test_figura_a_base64_devuelve_none_figura_vacia():
    """Comprueba el tratamiento si recibe una figura inexistente"""
    assert charts._figura_a_base64(None) is None
    
def test_figura_a_base64_devuelve_png():
    """Comprueba que la función genera un gráfico en base64 válido"""
    figura, _ = plt.subplots()
    
    try:
        resultado = charts._figura_a_base64(figura)
    finally:
        plt.close(figura)
        
    assert isinstance(resultado, str)
    contenido = base64.b64decode(resultado)
    assert contenido.startswith(b"\x89PNG")
    
def test_crear_grafico_barras_devuelve_none_sin_jugadores():
    """Comprueba que no se genera un gráfico sin jugadores"""
    assert charts.crear_grafico_barras(
        [], [], "titulo", "X", "Y", "blue"
    ) is None
    
def test_crear_grafico_barras_devuelve_base64():
    """Comprueba la generarción normal de un gráfico de barras"""
    resultado = charts.crear_grafico_barras(
        ["Sol", "Vero"],
        [10, 20],
        "Puntuaciones",
        "Jugadores",
        "Puntos",
        "blue",
    )
    
    assert isinstance(resultado, str)
    assert len(resultado) > 0
    
def test_crear_grafico_pastel_devuelve_none_con_valores_cero():
    """Comprueba que no se genera un gráfico sin valores positivos"""
    resultado = charts.crear_grafico_pastel(
        ["Ahorcado", "Piedra"],
        [0, 0],
        "Distribucion",
        ["red", "blue"],
    )
    
    assert resultado is None
    
def test_crear_grafico_pastel_devuelve_base64():
    """Comprueba que el gráfico se genera correctamente"""
    resultado = charts.crear_grafico_pastel(
        ["Ahorcado", "Piedra"],
        [10, 20],
        "Distribucion",
    )
    
    assert isinstance(resultado, str)
    assert len(resultado) > 0
    
def test_preparar_datos_graficos_sin_participantes_devuelve_none():
    """Comprueba el caso de un ranking vacío"""
    ranking = Torneo.objects.none()
    resultado = charts.preparar_datos_graficos(ranking, 20)
    
    assert resultado == (None, None, None)
    
def test_preparar_datos_graficos_devuelve_tres_graficos(datos_torneo):
    """Comprueba la generación conjunta de los gráficos"""
    ranking = Torneo.objects.filter(semana=datos_torneo["semana"]).annotate(total_puntos = F("puntos_ahorcado") + F("puntos_piedra"))
    resultado = charts.preparar_datos_graficos(ranking, datos_torneo["semana"])
    
    assert isinstance(resultado, tuple)
    assert len(resultado) == 3
    assert all(isinstance(grafico, str) for grafico in resultado)
    
# ----- Pruebas de estadísticas
    
def test_get_ranking_filtrado_puestos_clasificacion(datos_torneo):
    """Comprueba la asignación de puestos en la clasificación"""
    ranking, semana, anio = services.get_ranking_filtrado({})
    
    assert semana == datos_torneo["semana"]
    assert anio == datos_torneo["anio"]
    assert [participante.user.username for participante in ranking] == ["Vero", "Sol", "Ling", "Indhira"]
    assert [participante.puesto for participante in ranking] == [1, 2, 3, 4]
    assert all(isinstance(participante.puesto, int) for participante in ranking)

# Usamos parametrize para probar distintos juegos y sus usuarios esperados   
@pytest.mark.parametrize(
    ("juego", "usuarios_esperados"),
    [
        ("ahorcado", ["Sol", "Vero", "Indhira"]),
        ("piedra", ["Ling", "Vero", "Sol"]),
        ("adivina", ["Vero", "Sol"])
    ],
)
def test_get_ranking_filtrado_por_juego(datos_torneo, juego, usuarios_esperados):
    """Comprueba los filtros y el orden específico de cada juego"""
    ranking, semana, anio = services.get_ranking_filtrado({"juego": juego})
    
    assert [participante.user.username for participante in ranking] == (usuarios_esperados)
    
def test_get_ranking_filtrado_por_semana_y_anio(datos_torneo):
    """Comprueba que una consulta númerica selecciona otra semana"""
    usuario = User.objects.create_user(username="usuario_futuro", password="Password123")
    Torneo.objects.create(user=usuario, semana=21, juegos_ahorcado = 10, puntos_ahorcado=30, juegos_piedra = 1, puntos_piedra=1)
    ranking, semana, anio = services.get_ranking_filtrado({"q": "21"})
    
    assert semana == 21
    assert anio == datos_torneo["anio"]
    assert [participante.user.username for participante in ranking] == ["usuario_futuro"]
    
@pytest.mark.parametrize("semana_invalida", ["o", "54","999"])
def test_get_ranking_filtrado_usa_semana_actual_si_q_invalido(datos_torneo, semana_invalida):
    """Usa la semana actual cuando q está fuera del rango"""
    ranking, semana, anio = services.get_ranking_filtrado({"q": semana_invalida})
    
    assert semana == datos_torneo["semana"]
    assert anio == datos_torneo["anio"]
    assert len(ranking) == 4
    
def test_get_ranking_filtrado_por_jugador_exacto(datos_torneo):
    """Comprueba el filtro de busqueda por jugador exacto"""
    ranking, semana, anio = services.get_ranking_filtrado({"jugador": "Sol"})
    
    assert [participante.user.username for participante in ranking] == ["Sol"]
    
def test_get_ranking_filtrado_usa_general_para_desconocido(datos_torneo):
    """Comprueba el comportamiento ante un juego no configurado"""
    ranking, semana, anio = services.get_ranking_filtrado({"juego": "desconocido"})
    
    assert ranking[0].user.username == "Vero"
    
def test_get_ranking_filtrado_sin_resultados_devuelve_lista_vacia(monkeypatch):
    """Comprueba el caso en el que no existen participantes"""
    # Mockeamos la función get_semana_actual para que devuelva un valor fijo
    monkeypatch.setattr(services, "get_semana_actual", lambda: 20)
    
    ranking, semana, anio = services.get_ranking_filtrado({})
    
    assert ranking == []
    assert semana == 20
    assert anio == services.get_anio_actual()
    
def test_get_ranking_filtrado_ignora_espacios_en_los_parametros(datos_torneo):
    """Verifica que los parámetros se limpian con strip()"""
    ranking, semana, _ = services.get_ranking_filtrado(
        {"juego": "  ahorcado  "}
    )
    
    assert semana == datos_torneo["semana"]
    assert [participante.user.username for participante in ranking] == ["Sol", "Vero", "Indhira"]
    
def test_get_ranking_filtrado_jugador_inexistente_devuelve_lista_vacia(datos_torneo):
    """Comprueba la búsqueda de un usuario que no existe"""
    ranking, semana, anio = services.get_ranking_filtrado({"jugador": "usuario_inexistente"})
    
    assert ranking == []
    
def test_get_ranging_filtrado_propaga_databaseerror():
    """Comprueba que los errores en base de datos no se ocultan"""
    with patch("torneo.services.Torneo.objects.filter", side_effect=DatabaseError):
        with pytest.raises(DatabaseError):
            services.get_ranking_filtrado({})
    
def test_get_ranking_filtrado_lanza_attributeerror_sin_parametros():
    """Comprueba el error ante un objeto que no implementa get"""
    with pytest.raises(AttributeError):
        services.get_ranking_filtrado(None)
 
@pytest.mark.parametrize(
    ("juego", "filtro_esperado", "orden_esperado"),
    [
        ("ahorcado", {"juegos_ahorcado__gt": 0}, ["-puntos_ahorcado", "user__username"]),
        ("piedra", {"juegos_piedra__gt": 0}, ["-puntos_piedra", "user__username"]),
        ("adivina", {"juegos_adivina__gt": 0}, ["intentos_adivina", "tiempo_adivina", "user__username"]),
        ("general", {}, ["-total_puntos", "user__username"]),
         
    ]
)       
def test_ranking_config_devuelve_configuracion_correcta(juego, filtro_esperado, orden_esperado):
    """Comprueba la configuración de cada modalidad del ranking"""
    resultado = services.get_ranking_config(juego)
    
    assert isinstance(resultado, dict)
    assert resultado["filters"] == filtro_esperado
    assert resultado["order"] == orden_esperado
    assert callable(resultado["valor"])
    
def test_get_ranking_config_acepta_cadena_vacia():
    """Verifica el comportamiento ante una modalidad vacía"""
    resultado = services.get_ranking_config("")
    general = services.get_ranking_config("general")
    
    assert resultado["filters"] == general["filters"]
    assert resultado["order"] == general["order"]
    assert callable(resultado["valor"])
    
def test_get_ranking_config_lanza_atributeerror_con_none():
    """Comprueba que una entrada nula provoca el erro esperado"""
    resultado = services.get_ranking_config(None)
    general = services.get_ranking_config("general")
    
    assert resultado["filters"] == general["filters"]
    assert resultado["order"] == general["order"]
    assert callable(resultado["valor"])
        
def test_calcular_puesto_devuelve_primer_puesto():
    """Comprueba que el primer participante ocupa el puesto 1"""
    participante = SimpleNamespace(puntos_ahorcado=50)
    resultado = services.calcular_puesto(participante, 0, [participante], "ahorcado")
    
    assert resultado == 1
    assert isinstance(resultado, int)
    
def test_calcular_puesto_comparte_puesto_en_empate():
    """Verifica que dos participantes con la misma puntuación empatan"""
    
    primero = SimpleNamespace(puntos_ahorcado=50, puesto=1)
    segundo = SimpleNamespace(puntos_ahorcado=50)
    resultado = services.calcular_puesto(segundo, 1, [primero, segundo], "ahorcado")
    
    assert resultado == 1
    
def test_calcular_puesto_asigna_puesto_siguiente_sin_empate():
    """Comprueba que una puntuación diferente ocupa el puesto siguiente"""
    primero = SimpleNamespace(puntos_ahorcado=50, puesto=1)
    segundo = SimpleNamespace(puntos_ahorcado=40)
    
    resultado = services.calcular_puesto(segundo, 1, [primero, segundo], "ahorcado")
    
    assert resultado == 2
    
def test_calcular_puesto_usa_intentos_y_tiempo_en_adivina():
    """Comprueba el desempate en Adivina el Número"""
    primero = SimpleNamespace(intentos_adivina=2, tiempo_adivina=10, puesto=1)
    segundo = SimpleNamespace(intentos_adivina=2, tiempo_adivina=20)
    resultado = services.calcular_puesto(segundo, 1, [primero, segundo], "adivina")
    
    assert resultado == 2
    
def test_calcular_puesto_lanza_indexerror_con_lista_vacia():
    """Verifica el error ante un índice incompatible con la lista"""
    participante = SimpleNamespace(puntos_ahorcado=10)
    
    with pytest.raises(IndexError):
        services.calcular_puesto(participante, 1, [], "ahorcado")
        
def test_get_mejores_puntuaciones_historicas_elige_los_mejores(django_user_model):
    """Comprueba que se selecciona el mejor resultado de cada juego"""
    usuario = django_user_model.objects.create_user(username="historico", password="PasswordHistorico123")
    
    ahorcado_malo = Torneo.objects.create(user=usuario, semana=1, juegos_ahorcado=5, puntos_ahorcado=10)
    ahorcado_bueno = Torneo.objects.create(user=usuario, semana=2, juegos_ahorcado=10, puntos_ahorcado=30)
    piedra_mala = Torneo.objects.create(user=usuario, semana=3, juegos_piedra=5, puntos_piedra=10)
    piedra_buena = Torneo.objects.create(user=usuario, semana=4, juegos_piedra=10, puntos_piedra=30)
    adivina_mala = Torneo.objects.create(user=usuario, semana=5, juegos_adivina=1, intentos_adivina=4, tiempo_adivina=20)
    adivina_buena = Torneo.objects.create(user=usuario, semana=6, juegos_adivina=1, intentos_adivina=2, tiempo_adivina=15)
    
    resultado = services.get_mejores_puntuaciones_historicas()
    
    assert resultado[0] != ahorcado_malo
    assert resultado[1] != piedra_mala
    assert resultado[2] != adivina_mala
        
def test_get_mejores_puntuaciones_historicas_excluye_ceros():
    """Comprueba que las mejores puntuaciones ignoran valores 0"""
    usuario = User.objects.create_user(username="historico", password="Password123")
    Torneo.objects.create(
        user = usuario,
        semana = 1,
        puntos_ahorcado = 0,
        puntos_piedra = 0,
        juegos_adivina = 0,
    )
    mejor = Torneo.objects.create(
        user = usuario,
        semana = 2,
        juegos_ahorcado = 10,
        puntos_ahorcado = 30,
        juegos_piedra = 10,
        puntos_piedra = 30,
        juegos_adivina = 1,
        intentos_adivina = 2,
        tiempo_adivina = 10,
    )
    
    resultado = services.get_mejores_puntuaciones_historicas()
    
    assert resultado[0] == mejor
    assert resultado[1] == mejor
    assert resultado[2] == mejor
    
def test_get_mejores_puntuaciones_historicas_devuelve_none_sin_datos():
    """Comprueba el caso límite sin puntuaciones históricas"""
    assert services.get_mejores_puntuaciones_historicas() == (None, None, None)
    
def test_campeon_semana_devuelve_mejor_jugador():
    """Verifica que el jugador con menos intentos y mejor tiempo es el campeón"""
    usuario1 = User.objects.create_user(username="lento", password="Password123")
    usuario2 = User.objects.create_user(username="rapido", password="Password123")
    
    Torneo.objects.create(
        user = usuario1,
        anio = services.get_anio_actual(),
        semana = 10,
        juegos_adivina = 1,
        intentos_adivina = 3,
        tiempo_adivina = 5
    )
    ganador = Torneo.objects.create(
        user = usuario2,
        anio = services.get_anio_actual(),
        semana = 10,
        juegos_adivina = 1,
        intentos_adivina = 2,
        tiempo_adivina = 30,
    )
    
    assert services.get_campeon_semana(services.get_anio_actual(), 10) == ganador
    
@pytest.mark.parametrize("semana", [0, -1])
def test_get_campeon_semana_devuelve_none_semana_invalida(semana):
    """Comprueba semanas menores que 1"""
    assert services.get_campeon_semana(services.get_anio_actual(), semana) is None
    
def test_get_campeon_semana_sin_participantes_devuelve_none():
    """Comprueba que una semana sin participantes no tiene campeón"""
    assert services.get_campeon_semana(services.get_anio_actual(), 999) is None
    
def test_get_campeon_semana_ignora_partidas_sin_juegos_adivina(django_user_model):
    """Verifica que se excluyen registros sin partidas de adivina"""
    usuario = django_user_model.objects.create_user(username="sin_adivina", password="Password123")
    
    Torneo.objects.create(
        user = usuario, 
        anio = services.get_anio_actual(), 
        semana = 30, 
        juegos_adivina = 0, 
        intentos_adivina = 0, 
        tiempo_adivina = 0,
        )
    
    assert services.get_campeon_semana(services.get_anio_actual(), 30) is None
    
@pytest.mark.parametrize("semana", [None, "semana"])
def test_get_campeon_semana_lanza_typeerror_con_tipo_invalido(semana):
    """Comprueba el error ante valores que no pueden compararse con uno"""
    with pytest.raises((TypeError, AttributeError)):
        services.get_campeon_semana(services.get_anio_actual(), semana)
        
def test_estadisticas_get_muestra_contexto(datos_torneo, client):
    """Comprueba la carga normal de estadísticas"""
    client.force_login(datos_torneo["usuarios"][0])
    respuesta = client.get(
        reverse("torneo:estadisticas_torneo"),
        {"semana": datos_torneo["semana"]}
    )
    
    assert respuesta.status_code == 200
    assertTemplateUsed(respuesta, "torneo/estadisticas_torneo.html")
    assert respuesta.context["semana_mostrar"] == datos_torneo["semana"]
    assert isinstance(respuesta.context["grafica_barras"], str)
    assert isinstance(respuesta.context["grafica_torta"], str)
    
def test_estadisticas_filtra_anio_semana(datos_torneo, client):
    """Comprueba que las estadísticas filtran correctamente por año y semana"""
    usuario_historico = User.objects.create_user(username="jugador_2025", password="Password123")
    otro_usuario = User.objects.create_user(username="jugador_2026", password="Password123")
    
    Torneo.objects.create(user=usuario_historico, anio=2025, semana=10, juegos_ahorcado=10, puntos_ahorcado=30)
    Torneo.objects.create(user=otro_usuario, anio=datos_torneo["anio"], semana=10, juegos_ahorcado=1, puntos_ahorcado=3)
    
    ranking_recibido = []
    
    # Creamos una función para capturar el ranking que se pasa a preparar_datos_graficos
    def capturar_ranking(ranking, semana):
        ranking_recibido.extend(list(ranking))
        return None, None, None
    
    client.force_login(datos_torneo["usuarios"][0])
    
    with patch("torneo.services.preparar_datos_graficos", side_effect=capturar_ranking):
        respuesta = client.get(reverse("torneo:estadisticas_torneo"), {"anio": 2025, "semana": 10})
        
        assert respuesta.status_code == 200
        assert respuesta.context["anio_mostrar"] == 2025
        assert respuesta.context["semana_mostrar"] == 10
        assert [participante.user.username for participante in ranking_recibido] == ["jugador_2025"]
        assert all(
            participante.anio == 2025 and participante.semana == 10 for participante in ranking_recibido
        )
        
    
def test_estadisticas_semana_invalida_usa_semana_actual(datos_torneo, client):
    """Comprueba el valor predeterminado ante una semana invalida"""
    client.force_login(datos_torneo["usuarios"][0])
    respuesta = client.get(reverse("torneo:estadisticas_torneo"), {"semana": "no-es-un-numero"})
    
    assert respuesta.status_code == 200
    assert respuesta.context["semana_mostrar"] == datos_torneo["semana"]
    
def test_estadisticas_semana_futura_renderiza_sin_error(client, django_user_model):
    """Verifica la vista de estadísticas con una semana futura"""
    usuario = django_user_model.objects.create_user(username="estadisticas_futuras", password="Password123")
    client.force_login(usuario)
    respuesta = client.get(reverse("torneo:estadisticas_torneo"), {"semana": 999})
    
    assert respuesta.status_code == 200
    assert respuesta.context["semana_mostrar"] == services.get_semana_actual()
    
def test_estadisticas_sin_datos_devuelve_graficas_none(client, django_user_model):
    """Comprueba la vista con una semana sin participantes"""
    usuario = django_user_model.objects.create_user(username="sin_datos", password="Password123")
    client.force_login(usuario)
    respuesta = client.get(reverse("torneo:estadisticas_torneo"))
    
    assert respuesta.status_code == 200
    assert respuesta.context["grafica_barras"] is None
    assert respuesta.context["grafica_torta"] is None
    assert respuesta.context["grafica_adivina"] is None
    
def test_estadisticas_captura_database_error(client, django_user_model):
    """Comprueba la redirección ante un fallo de la base de datos"""
    usuario = django_user_model.objects.create_user(username="estadisticas_error", password="Password123")
    client.force_login(usuario)
        
    with patch(
        "torneo.services.Torneo.objects.filter",
        side_effect = DatabaseError
    ):
        respuesta = client.get(reverse("torneo:estadisticas_torneo"))
            
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("torneo:torneo")
        
# ----- Pruebas para torneo
    
def test_torneo_get_muestra_contexto(datos_torneo, client):
    """Verifica la carga normal de la vista principal"""
    client.force_login(datos_torneo["usuarios"][0])
    respuesta = client.get(reverse("torneo:torneo"))
    
    assert respuesta.status_code == 200
    assertTemplateUsed(respuesta, "torneo/torneo.html")
    assert respuesta.context["semana_actual"] == datos_torneo["semana"]
    assert "page_obj" in respuesta.context
    assert respuesta.context["page_obj"].paginator.count == 4
    
def test_torneo_con_ranking_vacio_renderiza_contexto_minimo(client, django_user_model, monkeypatch):
    """Verifica la vista principal cuando no hay participantes en la semana"""
    usuario = django_user_model.objects.create_user(username="ranking_vacio", password="Password123")
    client.force_login(usuario)
    
    monkeypatch.setattr(
        services,
        "get_ranking_filtrado",
        lambda _get: ([], services.get_semana_actual(), services.get_anio_actual())
    )
    respuesta = client.get(reverse("torneo:torneo"))
    
    assert respuesta.status_code == 200
    assert "page_obj" in respuesta.context
    assert respuesta.context["page_obj"].paginator.count == 0
    
def test_filtra_por_q_y_jugador(client, django_user_model, datos_torneo):
    """Comprueba que la vista recoge los filtros de usuario y búsqueda"""
    usuario = datos_torneo["usuarios"][0]
    client.force_login(usuario)
    
    respuesta = client.get(
        reverse("torneo:torneo"),
        {"q": "Indhi", "jugador": "Indhira", "juego": "ahorcado"}
    )
    
    assert respuesta.status_code == 200
    assert respuesta.context["q"] == "Indhi"
    assert respuesta.context["jugador"] == "Indhira"
    assert respuesta.context["juego_seleccionado"] == "ahorcado"
    
def test_torneo_captura_database_error(client, django_user_model):
    """Comprueba el contexto mínimo ante un fallo de la base de datos"""
    usuario = django_user_model.objects.create_user(username="torneo_error", password="Password123")
    client.force_login(usuario)
    
    with patch(
        "torneo.views.services.get_ranking_filtrado",
        side_effect = DatabaseError
    ):
        respuesta = client.get(reverse("torneo:torneo"))
        
    assert respuesta.status_code == 200
    assert respuesta.context["semana_actual"] == services.get_semana_actual()
    
def test_reglas_torneo_renderiza_template(client):
    """Verifica que la vista de reglas carga correctamente la plantilla"""
    respuesta = client.get(reverse("torneo:reglas_torneo"))
    
    assert respuesta.status_code == 200
    assertTemplateUsed(respuesta, "torneo/reglas_torneo.html")
    
def test_paginar_ranking_devuelve_pagina_correcta():
    """Verifica la paginación normal de un ranking"""
    ranking = list(range(25))
    
    pagina = services.paginar_ranking(ranking, page_number=2, per_page=10)
    
    assert pagina.number == 2
    assert pagina.object_list == list(range(10, 20))
    assert pagina.paginator.num_pages == 3
    
def test_paginar_ranking_usa_primera_pagina_si_numero_es_none():
    """comprueba el valor predeterminado cuando no se indica página"""
    pagina = services.paginar_ranking(list(range(3)), page_number=None, per_page=10)
    
    assert pagina.number == 1
    assert list(pagina.object_list) == [0, 1, 2]
    
def test_paginar_ranking_numero_no_entero_usa_primera_pagina():
    """Verfica el comportamiento de Paginator con una página inválida"""
    pagina = services.paginar_ranking(list(range(25)), page_number="no-es-un-numero", per_page=10)
    
    assert pagina.number == 1
    
def test_paginar_ranking_lista_vacia_devuelve_pagina_vacia():
    """comprueba la paginación de un ranking sin participantes"""
    pagina = services.paginar_ranking([], page_number=1, per_page=10)
    
    assert pagina.number == 1
    assert pagina.paginator.num_pages == 1
    assert list(pagina.object_list) == []
    
def test_paginar_ranking_lanza_zerodivisionerror_con_per_page_cero():
    """Verifica que no se permite un tamaño de página igual a cero"""
    with pytest.raises(ValueError, match="per_page debe ser mayor que cero"):
        services.paginar_ranking([1, 2, 3], page_number=1, per_page=0)
        
def test_paginar_ranking_lanza_valueerror_con_per_page_negativo():
    """Verifica que no se permite un tamaño de página negativo"""
    with pytest.raises(ValueError, match="per_page debe ser mayor que cero"):
        services.paginar_ranking([1, 2, 3], page_number=1, per_page=-1)