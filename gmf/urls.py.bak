from django.urls import path

from . import views, views_panel

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
]
