from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import (
    password_validators_help_text_html, validate_password,
)
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    Cliente, Entrenador, Fisioterapeuta, Membresia, Nutricionista, RolUsuario,
    Sede, TipoMembresia, Usuario,
)


def inicio(request):
    planes_premium = Membresia.objects.filter(activa=True, tipo=TipoMembresia.PREMIUM).order_by("precio")

    # Profesionales activos de los tres tipos, con el nombre de su rol para la tarjeta
    profesionales = []
    for modelo, rol in ((Entrenador, "Entrenador"), (Nutricionista, "Nutricionista"),
                        (Fisioterapeuta, "Fisioterapeuta")):
        for perfil in modelo.objects.select_related("usuario").filter(usuario__is_active=True):
            profesionales.append({"usuario": perfil.usuario, "rol": rol, "especialidad": perfil.especialidad})

    plan_actual = None
    if request.user.is_authenticated and hasattr(request.user, "cliente"):
        plan_actual = request.user.cliente.plan

    contexto = {
        "planes_premium": planes_premium,
        "profesionales": profesionales,
        "sedes": Sede.objects.filter(activa=True).order_by("nombre"),
        "plan_actual": plan_actual,
    }
    return render(request, "inicio.html", contexto)


# Cuenta: ingresar, registro y salir
def ingresar(request):
    if request.user.is_authenticated:
        return redirect("inicio")

    # Página a la que se vuelve después de entrar (?next=...), solo si es de este sitio
    siguiente = request.POST.get("next") or request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        siguiente = ""

    if request.method == "POST":
        correo = request.POST.get("email", "").strip().lower()
        clave = request.POST.get("password", "")
        # authenticate() compara la clave cifrada; devuelve None si no coincide o la cuenta está inactiva
        usuario = authenticate(request, email=correo, password=clave)
        if usuario is not None:
            login(request, usuario)
            messages.success(request, f"¡Hola de nuevo, {usuario.first_name}!")
            # Sin ?next=, el administrador va directo a su panel y el entrenador al suyo
            if not siguiente and usuario.rol == RolUsuario.ADMINISTRADOR:
                return redirect("panel")
            if not siguiente and usuario.rol == RolUsuario.ENTRENADOR:
                return redirect("entrenador_resumen")
            return redirect(siguiente or "inicio")

        messages.error(request, "El correo o la contraseña no son correctos.")
        return render(request, "ingresar.html", {"form": request.POST, "next": siguiente})

    return render(request, "ingresar.html", {"next": siguiente})


def registro(request):
    if request.user.is_authenticated:
        return redirect("inicio")

    contexto = {"ayuda_clave": password_validators_help_text_html()}

    if request.method == "POST":
        nombre = request.POST.get("first_name", "").strip()
        apellido = request.POST.get("last_name", "").strip()
        correo = request.POST.get("email", "").strip().lower()
        clave1 = request.POST.get("password1", "")
        clave2 = request.POST.get("password2", "")

        # Validaciones: cada error queda asociado a su campo para mostrarlo debajo
        errores = {}
        if not nombre:
            errores["first_name"] = ["Este campo es obligatorio."]
        if not apellido:
            errores["last_name"] = ["Este campo es obligatorio."]
        if not correo:
            errores["email"] = ["Este campo es obligatorio."]
        else:
            try:
                validate_email(correo)
            except ValidationError:
                errores["email"] = ["Introduce un correo válido."]
            else:
                if Usuario.objects.filter(email__iexact=correo).exists():
                    errores["email"] = ["Ya existe una cuenta con este correo."]
        if not clave1:
            errores["password1"] = ["Este campo es obligatorio."]
        if not clave2:
            errores["password2"] = ["Este campo es obligatorio."]
        elif clave1 != clave2:
            errores["password2"] = ["Las contraseñas no coinciden."]
        else:
            # Reglas de AUTH_PASSWORD_VALIDATORS en settings.py (largo, muy común, solo números...)
            try:
                validate_password(clave1, Usuario(email=correo, first_name=nombre, last_name=apellido))
            except ValidationError as e:
                errores["password2"] = list(e.messages)

        if errores:
            contexto.update({"form": request.POST, "errores": errores})
            return render(request, "registro.html", contexto)

        try:
            # Usuario y Cliente se crean juntos: si uno falla, no se guarda ninguno
            with transaction.atomic():
                usuario = Usuario.objects.create_user(
                    correo, clave1, first_name=nombre, last_name=apellido, rol=RolUsuario.CLIENTE,
                )
                Cliente.objects.create(usuario=usuario)  # el sexo se completa después
        except IntegrityError as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                errores["email"] = ["Ya existe una cuenta con este correo."]
            messages.error(request, "No se pudo crear la cuenta.")
            contexto.update({"form": request.POST, "errores": errores})
            return render(request, "registro.html", contexto)

        login(request, usuario)
        messages.success(request, f"¡Bienvenido a GMFitness, {usuario.first_name}! Tu cuenta está lista.")
        return redirect("inicio")

    return render(request, "registro.html", contexto)


@require_POST
def salir(request):
    # Solo por POST (el botón del menú es un formulario con csrf_token)
    logout(request)
    messages.info(request, "Cerraste sesión.")
    return redirect("inicio")
