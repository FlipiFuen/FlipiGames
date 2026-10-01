```
***************************
*        FLIPIGAMES       *
***************************
```

# FlipiGames: Plataforma de Minijuegos con Torneos Semanales

**FlipiGames** es una aplicación web desarrollada con **Django** que permite a los usuarios registrados disfrutar de juegos clásicos, competir en un torneo semanal y seguir su progreso con estadísticas detalladas y gráficos dinámicos.

---

## 🚀 Características Principales

*   **Sistema de Autenticación de Usuarios:** Registro, inicio de sesión y perfiles de usuario personalizados.
*   **Juegos Integrados:**
    *   **Ahorcado:** El clásico juego de adivinar la palabra oculta.
    *   **Piedra, Papel, Tijera, Lagarto, Spock:** La famosa expansión del juego tradicional.
    *   **Adivina el Número:** Un juego de lógica para adivinar un código de 4 cifras.
*   **Sistema de Torneos Semanales:**
    *   Inscripción al torneo de la semana actual.
    *   Acumulación de puntos y partidas jugadas en modo "Torneo".
    *   Ranking en tiempo real con filtros por juego, jugador o semana.
    *   Evento especial de fin de semana ("Adivina el Número"), para los jugadores en los 10 primeros puestos, que determina el ganador del Torneo.
*   **Perfil de Usuario Detallado:**
    *   Estadísticas generales (partidas jugadas, torneos participados, campeonatos ganados).
    *   Visualización de mejores puntuaciones históricas por juego.
    *   Gráficos de rendimiento generados con Matplotlib (distribución de partidas, puntos por juego, evolución semanal).
    *   Gestión de la cuenta: cambio de email y contraseña, y opción para eliminar la cuenta.
*   **Salón de la Fama:** Muestra las mejores puntuaciones históricas de todos los jugadores.
*   **Panel de Administración de Django:** Para una gestión sencilla de usuarios y datos del torneo.

## 📂 Estructura del Proyecto

GamesFlipi/
    ├── config/             # Configuración del proyecto Django (settings, urls, wsgi)
    ├── flipigames/         # App principal: perfiles de usuario, vistas y generación de gráficos
    ├── juegos/             # App de minijuegos: lógica de Ahorcado, PPTLS y Adivina Número
    ├── torneo/             # App de torneos: clasificaciones, eventos y sistema de puntos
    ├── templates/          # Plantillas HTML globales del sitio
    ├── static/             # Archivos estáticos (CSS, JS, imágenes)
    ├── db.sqlite3          # Base de datos SQLite3 de desarrollo
    ├── manage.py           # Gestor de comandos de Django
    ├── pytest.ini          # Configuración para la suite de pruebas Pytest
    ├── requirements.txt    # Lista de dependencias de Python
    └── .env                # Configuración local de demostración

## 🛠️ Tecnologías Utilizadas

*   **Backend:** Python 3.12, Django 6.0.7.
*   **Frontend:** HTML5, CSS3, Bootstrap 5.3, Django-Crispy-Forms.
*   **Base de Datos:** SQLite3 (para desarrollo).
*   **Librerías Python:** Matplotlib (para la generación de gráficos).
*   **Testing:** Pytest, Pytest-Django, Pytest-Mock

## ⚙️ Puesta en Marcha

### Prerrequisitos

- Python 3.12 o superior.
- Git.

### Instalación en Windows (PowerShell)

1. Clona el repositorio y entra en la carpeta:

   ```powershell
   git clone https://github.com/USUARIO/REPOSITORIO.git
   cd REPOSITORIO

2. Crea y activa un entorno virtual:

    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1

3. Instala las dependencias:

    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

4.  Crea un archivo .env en la raíz del proyecto, junto a manage.py. Genera una clave secreta con:
    python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
    Copia el resultado en .env:
        SECRET_KEY=pega_aqui_la_clave_generada
        DEBUG=True
        ALLOWED_HOSTS=127.0.0.1,localhost

    No publiques el archivo .env ni compartas su SECRET_KEY.

5. Crea las tablas de la base de datos:

    python manage.py migrate

6. Opcionalmente, crea un usuario administrador:

    python manage.py createsuperuser

7. Inicia el servidor:

    python manage.py runserver
    Abre http://127.0.0.1:8000/ en el navegador. El panel de administración está en http://127.0.0.1:8000/admin/.


### 🧪 Ejecutar Pruebas

El proyecto cuenta con una suite de tests para asegurar el correcto funcionamiento de las vistas y la lógica de negocio. Para ejecutarlos:

```bash
pytest
```
### Instalación en macOS/Linux

    Los pasos son los mismos, salvo la creación y activación del entorno virtual:

    python3 -m venv .venv
    source .venv/bin/activate

## 📌 Estado del proyecto

Proyecto final desarrollado con Django, con funcionalidades de usuarios, minijuegos, torneos, rankings, estadísticas, administración y pruebas automatizadas.

