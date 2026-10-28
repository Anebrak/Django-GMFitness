"""
URLs principales de GMFitness.

Aqui solo se reparten las rutas: cada app maneja las suyas en su propio urls.py.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('gmf.urls')),
]
