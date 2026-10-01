
from pathlib import Path
from decouple import config  # Importamos la función config de python-decouple para manejar variables de entorno

BASE_DIR = Path(__file__).resolve().parent.parent

# Utilizamos python-decouple para manejar variables de entorno
SECRET_KEY = config("SECRET_KEY")

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Mis apps
    'flipigames',
    'juegos',
    'torneo',
    
    # Apps de terceros
    'crispy_forms',
    'crispy_bootstrap5',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], # Le decimos a Django que busque plantillas en una carpeta "templates" en la raíz del proyecto
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'torneo.context_processors.torneo_context', # Añadimos nuestro procesador de contexto
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]



LANGUAGE_CODE = 'es'

TIME_ZONE = 'Europe/Madrid'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'

# Directorio de archivos estáticos
STATICFILES_DIRS = [
    BASE_DIR / 'static'
]

# Si un usuario intenta entrar en una vista protegida sin iniciar sesión,
# Django lo enviará a esta URL.
LOGIN_URL = 'flipigames:login'

# Después de iniciar sesión correctamente, Django lo redirigirá aquí.
LOGIN_REDIRECT_URL = 'flipigames:home'

# Después de cerrar sesión, el usuario volverá a esta página.
LOGOUT_REDIRECT_URL = 'flipigames:home'

# Configuración de Crispy Forms que le da estilo a los formularios
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Configuración del backend de correo electrónico para desarrollo
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@flipigames.local"