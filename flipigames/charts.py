import io
import base64
import matplotlib
matplotlib.use("Agg") # Configura Matplotlib para ejecutarse sin interfaz gráfia de usuario
import matplotlib.pyplot as plt

from django.db.models import Sum

# Utilidades base para la generación

def _figura_a_base64(fig):
    """Convierte una figura de Matplotlib a una cadena de texto en base64.

    Esto permite incrustar la imagen del gráfico directamente en una plantilla HTML.

    Args:
        fig: La figura de Matplotlib a convertir.

    Returns:
        Una cadena de texto con la imagen codificada en base64.
    """
    if fig is None:
        return None
    
    # Guardamos la figura en un buffer de memoria y la convertimos a base64
    with io.BytesIO() as buffer:
        fig.savefig(buffer, format="png", bbox_inches="tight")
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    
def crear_grafico_barras(etiquetas, valores, titulo, xlabel, ylabel, color="#4e73df", figsize=(10, 5), anotaciones=None):
    """
    Crea un gráfico de barras y lo devuelve como una cadena en base64
    
    Args:
        etiquetas: Lista de etiquetas para el eje x.
        valores: Lista de valores para el eje y.
        titulo: Título del gráfico.
        xlabel: Etiqueta del eje x.
        ylabel: Etiqueta del eje y.
        color: Color de las barras.
        figsize: Tamaño de la figura.

    Returns:
        Una cadena en base64 con la imagen del gráfico, o None si no hay datos.
    """
    
    if not etiquetas:
        return None
    
    # Creamos la figura y el eje para el gráfico de barras
    fig, ax = plt.subplots(figsize=figsize)
    try:
        barras = ax.bar(etiquetas, valores, color=color if isinstance(color, list) else [color] * len(etiquetas))
        ax.set_title(titulo, fontsize = 14, fontweight = "bold")
        ax.set_xlabel(xlabel, fontsize = 12)
        ax.set_ylabel(ylabel, fontsize = 12)
        ax.tick_params(axis = "both", labelsize = 11)
        if any(valores):
            ax.bar_label(barras, fmt="%d", padding=3)
        
        # Agregamos anotaciones si se proporcionan
        if anotaciones:
            for barra, texto in zip(barras, anotaciones):
                ax.text(
                    barra.get_x() + barra.get_width() / 2,
                    barra.get_height(),
                    texto,
                    ha = "center",
                    va = "bottom",
                    fontsize = 9,
                    color = "darkred",
                )
                
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()
        return _figura_a_base64(fig)
    finally:
        plt.close(fig)
        
def crear_grafico_lineas(etiquetas, valores, titulo, xlabel, ylabel, color="#4e73df", figsize=(10, 5)):
    """
    Crea un gráfico de líneas y lo devuelve como una cadena en base64
    
    Args:
        etiquetas: Lista de etiquetas para el eje x.
        valores: Lista de valores para el eje y.
        titulo: Título del gráfico.
        xlabel: Etiqueta del eje x.
        ylabel: Etiqueta del eje y.
        color: Color de las líneas.
        figsize: Tamaño de la figura.

    Returns:
        Una cadena en base64 con la imagen del gráfico, o None si no hay datos.
    """
    if not etiquetas:
        return None
    
    fig, ax = plt.subplots(figsize=figsize)
    try:
        ax.plot(etiquetas, valores, marker="o", linestyle="-", color=color, linewidth=2)
        ax.set_title(titulo)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()
        return _figura_a_base64(fig)
    finally:
        plt.close(fig)
        
def crear_grafico_pastel(etiquetas, valores, titulo, figsize=(6, 5)):
    """
    Crea un gráfico de pastel y lo devuelve como una cadena en base64
    
    Args:
        etiquetas: Lista de etiquetas para el eje x.
        valores: Lista de valores para el eje y.
        titulo: Título del gráfico.
        figsize: Tamaño de la figura.

    Returns:
        Una cadena en base64 con la imagen del gráfico, o None si no hay datos.
    """
    
    if not etiquetas or not any(valores):
        return None
    
    fig, ax = plt.subplots(figsize=figsize)
    try:
        ax.pie(
            valores,
            labels = etiquetas,
            autopct = "%1.1f%%",
            colors = ["#4e73df", "#1cc88a", "#36b9cc"],
            startangle = 140,
        )
        ax.set_title(titulo)
        fig.tight_layout()
        return _figura_a_base64(fig)
    finally:
        plt.close(fig)
        
# ----- Funciones específicas de gráficos de la aplicación

def generar_grafico_partidas(datos_agregados):
    """Genera un gráfico de tarta con la distribución de partidas jugadas.

    Args:
        datos_agregados: Un diccionario con el número de partidas por juego.

    Returns:
        Una cadena en base64 con la imagen del gráfico, o None si no hay datos.
    """
    etiquetas = ["Ahorcado", "Piedra-Papel-Tijeras-Lagarto-Spock", "Adivina el Número"]
    valores = [
        # Usamos "or 0" porque si no hay registros o la suma da nulo, Sum devuelve None lo que causaría problemas
        datos_agregados.get("total_ahorcado", 0) or 0,
        datos_agregados.get("total_piedra", 0) or 0,
        datos_agregados.get("total_adivina", 0) or 0,
    ]
    
    if not any(valores):
        return None
    
    # Filtramos juegos sin partidas para no mostrarlos en el gráfico
    valores_filtrados = [v for v in valores if v > 0]
    etiquetas_filtradas = [e for e, v in zip(etiquetas, valores) if v > 0]
    
    return crear_grafico_pastel(etiquetas_filtradas, valores_filtrados, "Partidas Jugadas por Juego")

def generar_grafico_puntos(datos_agregados):
    """Genera un gráfico de barras con los puntos totales obtenidos por juego.

    Args:
        datos_agregados: Un diccionario con los puntos totales por juego.

    Returns:
        Una cadena en base64 con la imagen del gráfico, o None si no hay datos.
    """
    juegos = [
        "Ahorcado",
        "Piedra-Papel-Tijera-Lagarto-Spock",
    ]
    puntos = [
        datos_agregados.get("puntos_ahorcado", 0),
        datos_agregados.get("puntos_piedra", 0),
    ]
    
    if not any(puntos):
        return None
    
    return crear_grafico_barras(
        juegos,
        puntos,
        "Puntos Totales Obtenidos",
        "Juegos",
        "Puntos Acumulados",
        ["#4e73df", "#1cc88a", "#36b9cc"],
        figsize = (6, 5),
    )
    
def generar_grafico_evolucion(semanas, puntos_semana):
    """Genera un gráfico de línea con la evolución de puntos a lo largo de las semanas.

    Args:
        semanas: Una lista de strings representando las semanas (e.g., "Semana 34").
        puntos_semana: Una lista de enteros con los puntos de cada semana.

    Returns:
        Una cadena en base64 con la imagen del gráfico, o None si hay menos de dos
        puntos de datos.
    """
    if len(semanas) < 2:
        return None
    
    return crear_grafico_lineas(
        semanas,
        puntos_semana,
        "Evolución de Puntos por Semana",
        "Semana",
        "Puntos Totales",
        "#e74a3b",
        figsize = (8, 4)
    )

def generar_graficos_perfil(registros):
    """Orquesta la generación de todos los gráficos para la página de perfil.

    Args:
        registros: Un QuerySet de objetos Torneo del usuario.

    Returns:
        Una tupla conteniendo las imágenes en base64 de los gráficos de
        partidas, puntos y evolución. Si no hay registros, devuelve
        (None, None, None).
    """
    if not registros.exists():
        return None, None, None
    
    # Agregamos los datos en la base de datos para mayor eficiencia
    datos_agregados = registros.aggregate(
        total_ahorcado=Sum('juegos_ahorcado'),
        total_piedra=Sum('juegos_piedra'),
        total_adivina=Sum('juegos_adivina'),
        puntos_ahorcado=Sum('puntos_ahorcado'),
        puntos_piedra=Sum('puntos_piedra'),
    )

    semanas_evolucion = [f"Semana{ r.semana }" for r in registros][::-1]
    puntos_evolucion = [r.puntos_ahorcado + r.puntos_piedra for r in registros]
    
    grafica_partidas = generar_grafico_partidas(datos_agregados)
    grafica_puntos = generar_grafico_puntos(datos_agregados)
    grafica_evolucion = generar_grafico_evolucion(semanas_evolucion, puntos_evolucion)
    
    return grafica_partidas, grafica_puntos, grafica_evolucion

def preparar_datos_graficos(ranking, semana):
    """Prepara y genera todos los gráficos para la página de estadísticas.

    Args:
        ranking (QuerySet[Torneo]): QuerySet con los participantes del torneo
            de una semana específica.
        semana (int): El número de la semana para la que se generan los gráficos.

    Returns:
        tuple[str | None, str | None, str | None]: Una tupla con las imágenes en base64
            para el gráfico de barras, de torta y de 'Adivina el Número'.
    """
    # Graficos de barras top10
    top_10 = ranking[:10]
    grafico_barras = crear_grafico_barras(
        [p.user.username for p in top_10],
        [p.total_puntos for p in top_10],
        f"Top 10 Jugadores - Semana {semana}",
        "Jugadores",
        "Puntos Totales",
        color = "skyblue",
    )
    
    # Gráfico de torta de distribución de puntos
    puntos_totales = ranking.aggregate(
        total_ahorcado = Sum("puntos_ahorcado"),
        total_piedra = Sum("puntos_piedra")
    )
    
    grafico_torta = crear_grafico_pastel(
        ["Ahorcado", "Piedra-Papel-Tijera-Lagarto-Spock"],
        [puntos_totales["total_ahorcado"] or 0, puntos_totales["total_piedra"] or 0],
        f"Distribución de Puntos por Juego - Semana {semana} ",
        figsize = (8, 8),
    )

    # Gráfico de barras para adivina el número
    mejores_jugadores = ranking.filter(juegos_adivina__gt=0).order_by("intentos_adivina", "tiempo_adivina", "user__username")[:10]
    
    grafico_adivina = crear_grafico_barras(
        [p.user.username for p in mejores_jugadores],
        [p.intentos_adivina for p in mejores_jugadores],
        f"Mejores Jugadores de Adivina el Número - Semana {semana}",
        "Jugadores",
        "Intentos",
        color = "mediumseagreen",
        anotaciones = [f"{p.tiempo_adivina} segundos" for p in mejores_jugadores]
    )
    
    return grafico_barras, grafico_torta, grafico_adivina
