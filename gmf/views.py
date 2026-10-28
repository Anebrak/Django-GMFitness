from django.shortcuts import render

# Por ahora las pantallas son solo visuales: los datos los maneja el JS en el
# navegador (localStorage). Cuando se conecten a la base de datos, estas vistas
# pasarán los datos reales a las plantillas.


def inicio(request):
    # "gmf/inicio.html" -> gmf/templates/gmf/inicio.html
    return render(request, "gmf/inicio.html")


def cliente(request):
    return render(request, "gmf/cliente.html")


def rutinas(request):
    return render(request, "gmf/rutinas.html")


def dietas(request):
    return render(request, "gmf/dietas.html")


def panel(request):
    # Panel de administración del gimnasio (distinto del admin de Django en /admin/)
    return render(request, "gmf/panel.html")
