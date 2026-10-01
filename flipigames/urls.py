from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views

app_name = 'flipigames' # Nombre para usar rutas como flipigames:home

urlpatterns = [
    path('', views.home, name='home'), # Ruta de la página raiz
    path('registro/', views.registro, name='registro'), # Ruta a la página de rgistro de usuarios
    path('perfil/', views.perfil, name='perfil'), # Ruta a la página de perfil del usuario
    path('perfil/ajustes_cuenta/', views.ajustes_cuenta, name='ajustes_cuenta'), # Ruta a la página de ajustes de la cuenta
    path('admin_gestion/', views.admin_gestion, name='admin_gestion'), # Ruta a la página de gestión del superusuario

    # Login usando la vista genérica de Django y nuestro template personalizado
    path('login/', auth_views.LoginView.as_view(template_name='flipigames/login.html'), name='login'),

    # Logout usando la vista genérica de Django
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Recuperación de contraseña
    path(
        "recuperar_contrasena/",
        auth_views.PasswordResetView.as_view(
            template_name = "flipigames/password_reset_form.html",
            email_template_name = "flipigames/password_reset_email.html",
            subject_template_name = "flipigames/password_reset_subject.txt",
            success_url = reverse_lazy("flipigames:password_reset_done"),
        ),
        name = "password_reset",
    ),
    
    path(
        "recuperar-contrasena/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name = "flipigames/password_reset_done.html",
        ),
        name = "password_reset_done",
    ),
    
    path(
        "restablecer-contrasena/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name = "flipigames/password_reset_confirm.html",
            success_url = reverse_lazy("flipigames:password_reset_complete")
        ),
        name = "password_reset_confirm",
    ),
    
    path(
        "restablecer-contrasena/completado",
        auth_views.PasswordResetCompleteView.as_view(
            template_name = "flipigames/password_reset_complete.html",
        ),
        name = "password_reset_complete",
    )
]
