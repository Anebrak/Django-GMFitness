from django.urls import path

from . import views

# Espacio de nombres: en los templates se usa {% url 'gmf:inicio' %}
app_name = "gmf"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("cliente/", views.cliente, name="cliente"),
    path("rutinas/", views.rutinas, name="rutinas"),
    path("dietas/", views.dietas, name="dietas"),
    path("panel/", views.panel, name="panel"),
]
