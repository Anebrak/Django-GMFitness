from django.urls import path

from . import views, views_entrenador, views_mensajes, views_panel, views_rutinas

# Sin app_name: en los templates se usa {% url 'inicio' %} y en las vistas redirect("inicio")
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("ingresar/", views.ingresar, name="ingresar"),
    path("registro/", views.registro, name="registro"),
    path("salir/", views.salir, name="salir"),

    # Panel de administración (solo rol ADMINISTRADOR)
    path("panel/", views_panel.panel, name="panel"),
    path("panel/empleados/", views_panel.panel_empleados, name="panel_empleados"),
    path("panel/clientes/", views_panel.panel_clientes, name="panel_clientes"),
    path("panel/sedes/", views_panel.panel_sedes, name="panel_sedes"),
    path("panel/membresias/", views_panel.panel_membresias, name="panel_membresias"),
    path("panel/ejercicios/", views_panel.panel_ejercicios, name="panel_ejercicios"),
    path("panel/alimentos/", views_panel.panel_alimentos, name="panel_alimentos"),
    path("panel/<str:seccion>/<int:pk>/estado/", views_panel.panel_cambiar_estado, name="panel_estado"),
    path("panel/usuarios/<int:pk>/clave/", views_panel.panel_nueva_clave, name="panel_nueva_clave"),

    # Panel del entrenador (solo rol ENTRENADOR)
    path("entrenador/", views_entrenador.resumen, name="entrenador_resumen"),
    path("entrenador/clientes/", views_entrenador.clientes, name="entrenador_clientes"),
    path("entrenador/clientes/<int:pk>/", views_entrenador.cliente_detalle, name="entrenador_cliente"),
    path("entrenador/clientes/<int:pk>/asignar/", views_entrenador.asignar_rutina, name="entrenador_asignar"),
    path("entrenador/clientes/<int:pk>/peso/", views_entrenador.registrar_peso, name="entrenador_peso"),
    path("entrenador/clientes/<int:pk>/cargas/", views_entrenador.editar_cargas, name="entrenador_cargas"),

    # Rutinas y ejercicios (entrenador y cliente: mismo código)
    path("rutinas/", views_rutinas.rutinas, name="rutinas"),
    path("rutinas/<int:pk>/", views_rutinas.rutina_constructor, name="rutina_constructor"),
    path("rutinas/<int:pk>/guardar/", views_rutinas.rutina_guardar, name="rutina_guardar"),
    path("rutinas/<int:pk>/duplicar/", views_rutinas.rutina_duplicar, name="rutina_duplicar"),
    path("rutinas/<int:pk>/eliminar/", views_rutinas.rutina_eliminar, name="rutina_eliminar"),
    path("ejercicios/", views_rutinas.ejercicios, name="ejercicios"),
    path("ejercicios/nuevo/", views_rutinas.ejercicio_nuevo, name="ejercicio_nuevo"),

    # Mensajes (cualquier usuario con sesión)
    path("mensajes/", views_mensajes.mensajes_bandeja, name="mensajes"),
    path("mensajes/<int:usuario_id>/", views_mensajes.mensajes_bandeja, name="conversacion"),
]
