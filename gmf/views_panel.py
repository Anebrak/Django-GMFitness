"""
Panel de administración del gimnasio (/panel/).

Solo entran usuarios con rol ADMINISTRADOR. Cada sección es una página con su tabla
(búsqueda, filtros y paginación) y una ventana modal para agregar o editar:
- GET  /panel/<seccion>/            lista
- POST /panel/<seccion>/            guarda (sin "id" = crear, con "id" = editar)
- POST /panel/<seccion>/<id>/estado/  activa o desactiva (nada se borra)
- POST /panel/usuarios/<id>/clave/    genera una contraseña temporal

Los campos de cada formulario se describen una sola vez (listas CAMPOS_...) y sirven
para dibujar el formulario y para validarlo.
"""
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    Alimento, Cliente, DuracionMembresia, Ejercicio, Entrenador, EstadoPago, EstadoSuscripcion,
    Fisioterapeuta, Membresia, Nutricionista, Pago, RolUsuario, Sede, Sexo, Suscripcion,
    TipoMembresia, Usuario,
)

POR_PAGINA = 10

# Roles que se gestionan en "Empleados" y el perfil que crea cada uno
PERFILES_PROFESIONAL = {
    RolUsuario.ENTRENADOR: Entrenador,
    RolUsuario.NUTRICIONISTA: Nutricionista,
    RolUsuario.FISIOTERAPEUTA: Fisioterapeuta,
}
ROLES_EMPLEADO = [
    RolUsuario.ENTRENADOR, RolUsuario.NUTRICIONISTA, RolUsuario.FISIOTERAPEUTA,
    RolUsuario.RECEPCIONISTA, RolUsuario.ADMINISTRADOR,
]

# Letras y números sin los que se confunden (0/O, 1/l/I)
CARACTERES_CLAVE = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

OPCIONES_ESTADO = [("", "Todos los estados"), ("activos", "Activos"), ("inactivos", "Inactivos")]

# Textos de cada sección (título, nombre en singular para "Agregar ...", ayuda y buscador)
SECCIONES = {
    "empleados": {"titulo": "Empleados", "singular": "empleado",
                  "descripcion": "Entrenadores, nutricionistas, fisioterapeutas, recepcionistas y administradores.",
                  "marcador": "Buscar por nombre, correo o teléfono"},
    "clientes": {"titulo": "Clientes", "singular": "cliente",
                 "descripcion": "Personas registradas en el gimnasio y su plan actual.",
                 "marcador": "Buscar por nombre, correo o teléfono"},
    "sedes": {"titulo": "Sedes", "singular": "sede",
              "descripcion": "Las sedes activas se muestran en la página de inicio.",
              "marcador": "Buscar por nombre, ciudad o dirección"},
    "membresias": {"titulo": "Membresías", "singular": "membresía",
                   "descripcion": "Planes Premium que se venden. El plan Gratis no necesita membresía.",
                   "marcador": ""},
    "ejercicios": {"titulo": "Ejercicios", "singular": "ejercicio",
                   "descripcion": "Catálogo para armar rutinas. Los inactivos no se ofrecen en rutinas nuevas.",
                   "marcador": "Buscar por nombre, grupo muscular o máquina"},
    "alimentos": {"titulo": "Alimentos", "singular": "alimento",
                  "descripcion": "Catálogo para dietas y diario de comidas. Valores por cada 100 g.",
                  "marcador": "Buscar por nombre, categoría o código"},
}


# =========================================================
# Acceso
# =========================================================

def solo_administradores(vista):
    """Deja pasar solo a usuarios con rol ADMINISTRADOR."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.rol != RolUsuario.ADMINISTRADOR:
            messages.error(request, "Solo los administradores pueden entrar al panel.")
            return redirect("inicio")
        return vista(request, *args, **kwargs)
    return envoltura


# =========================================================
# Utilidades
# =========================================================

def generar_clave_temporal():
    return get_random_string(10, CARACTERES_CLAVE)


def guardar_clave_para_mostrar(request, usuario, clave):
    """La contraseña temporal se muestra una sola vez, en la siguiente página."""
    request.session["clave_temporal"] = {"nombre": usuario.get_full_name() or usuario.email,
                                         "email": usuario.email, "clave": clave}


def volver(request, por_defecto):
    """Redirige a la página de la que vino el formulario (campo oculto 'volver')."""
    destino = request.POST.get("volver", "")
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                       require_https=request.is_secure()):
        return redirect(destino)
    return redirect(por_defecto)


def numero_texto(valor):
    """Decimal -> texto sin ceros de sobra para el formulario (130.00 -> "130", 2.70 -> "2.7")."""
    if valor is None:
        return ""
    texto = f"{valor:f}"
    return texto.rstrip("0").rstrip(".") if "." in texto else texto


def paginar(request, consulta):
    paginador = Paginator(consulta, POR_PAGINA)
    return paginador.get_page(request.GET.get("pagina"))


def filtrar_estado(consulta, estado, campo):
    if estado == "activos":
        return consulta.filter(**{campo: True})
    if estado == "inactivos":
        return consulta.filter(**{campo: False})
    return consulta


def buscar(consulta, texto, campos):
    """Filtra por cada palabra escrita en cualquiera de los campos."""
    for palabra in texto.split():
        condicion = Q()
        for campo in campos:
            condicion |= Q(**{f"{campo}__icontains": palabra})
        consulta = consulta.filter(condicion)
    return consulta


def opciones_sede():
    """Todas las sedes; las inactivas se marcan para no elegirlas por error."""
    sedes = Sede.objects.order_by("-activa", "nombre")
    return [("", "Sin sede")] + [(str(s.pk), s.nombre if s.activa else f"{s.nombre} (inactiva)")
                                 for s in sedes]


# =========================================================
# Validación de formularios
# =========================================================

def validar(campos, post):
    """
    Revisa los datos enviados según la lista de campos.
    Devuelve (datos, errores): datos ya convertidos (Decimal, int, bool...) y
    errores como {"campo": ["mensaje", ...]}.
    """
    datos, errores = {}, {}
    for campo in campos:
        nombre, tipo = campo["nombre"], campo.get("tipo", "texto")
        if campo.get("oculto"):
            continue

        if tipo == "checkbox":
            datos[nombre] = post.get(nombre) == "on"
            continue

        valor = post.get(nombre, "").strip()
        if not valor:
            if campo.get("obligatorio"):
                errores[nombre] = ["Este campo es obligatorio."]
            datos[nombre] = None if tipo in ("decimal", "entero") else ""
            continue

        maximo = campo.get("max_largo")
        if maximo and len(valor) > maximo:
            errores[nombre] = [f"Máximo {maximo} caracteres."]
            continue

        try:
            if tipo == "email":
                validate_email(valor)
                valor = valor.lower()
            elif tipo == "url":
                URLValidator()(valor)
            elif tipo == "decimal":
                valor = Decimal(valor.replace(",", "."))
                if not valor.is_finite():
                    raise InvalidOperation
                if valor < campo.get("minimo", 0):
                    errores[nombre] = [f"Debe ser mayor o igual a {campo.get('minimo', 0)}."]
                    continue
                if "maximo" in campo and valor > campo["maximo"]:
                    errores[nombre] = [f"Debe ser menor o igual a {campo['maximo']}."]
                    continue
            elif tipo == "entero":
                valor = int(valor)
                if valor < campo.get("minimo", 0):
                    errores[nombre] = [f"Debe ser mayor o igual a {campo.get('minimo', 0)}."]
                    continue
            elif tipo == "select":
                if valor not in [str(v) for v, _ in campo["opciones"] if v != ""]:
                    errores[nombre] = ["Elige una opción de la lista."]
                    continue
        except ValidationError:
            errores[nombre] = ["Escribe un correo válido." if tipo == "email" else "Escribe un enlace válido (https://...)."]
            continue
        except (InvalidOperation, ValueError):
            errores[nombre] = ["Escribe un número válido."]
            continue

        datos[nombre] = valor
    return datos, errores


def contexto_seccion(request, seccion, campos, pagina, registros_json, **extra):
    """Datos que necesitan todas las secciones con tabla y modal."""
    contexto = {
        "seccion": seccion,
        **SECCIONES[seccion],
        "campos": campos,
        "pagina": pagina,
        "registros_json": registros_json,
        "q": request.GET.get("q", ""),
        "estado": request.GET.get("estado", ""),
        "opciones_estado": OPCIONES_ESTADO,
        "clave_temporal": request.session.pop("clave_temporal", None),
        # Si hubo errores al guardar, el modal se vuelve a abrir con lo escrito
        "modal_abierto": False,
        "valores": {},
        "errores": {},
        "editando_id": "",
    }
    contexto.update(extra)
    return contexto


def reabrir_modal(contexto, post, errores):
    contexto.update({
        "modal_abierto": True,
        "valores": post,
        "errores": errores,
        "editando_id": post.get("id", ""),
    })
    return contexto


# =========================================================
# Resumen
# =========================================================

@solo_administradores
def panel(request):
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)

    vigente = Suscripcion.objects.filter(
        cliente=OuterRef("pk"), estado=EstadoSuscripcion.ACTIVA,
        fecha_inicio__lte=hoy, fecha_fin__gte=hoy,
    )
    clientes = Cliente.objects.filter(usuario__is_active=True)
    empleados = Usuario.objects.filter(rol__in=ROLES_EMPLEADO, is_active=True)

    ingresos_mes = Pago.objects.filter(
        estado=EstadoPago.APROBADO, fecha__date__gte=inicio_mes, fecha__date__lte=hoy,
    ).aggregate(total=Sum("monto"))["total"] or 0

    equipo = []
    for valor, texto in RolUsuario.choices:
        if valor in ROLES_EMPLEADO:
            equipo.append({"rol": texto, "total": empleados.filter(rol=valor).count()})

    contexto = {
        "seccion": "resumen",
        "total_clientes": clientes.count(),
        "total_premium": clientes.filter(Exists(vigente)).count(),
        "nuevos_mes": clientes.filter(usuario__date_joined__date__gte=inicio_mes).count(),
        "total_empleados": empleados.count(),
        "total_sedes": Sede.objects.filter(activa=True).count(),
        "ingresos_mes": ingresos_mes,
        "equipo": equipo,
        "ultimos_clientes": Cliente.objects.select_related("usuario").order_by("-usuario__date_joined")[:5],
        "membresias": Membresia.objects.filter(activa=True).order_by("precio"),
        "mes": hoy,
    }
    return render(request, "panel/resumen.html", contexto)


# =========================================================
# Empleados
# =========================================================

def campos_empleado():
    return [
        {"nombre": "first_name", "etiqueta": "Nombre", "obligatorio": True, "max_largo": 150},
        {"nombre": "last_name", "etiqueta": "Apellido", "obligatorio": True, "max_largo": 150},
        {"nombre": "email", "etiqueta": "Correo", "tipo": "email", "obligatorio": True, "completo": True},
        {"nombre": "telefono", "etiqueta": "Teléfono", "max_largo": 20},
        {"nombre": "sede", "etiqueta": "Sede", "tipo": "select", "opciones": opciones_sede()},
        {"nombre": "rol", "etiqueta": "Rol", "tipo": "select", "obligatorio": True, "solo_crear": True,
         "completo": True, "ayuda": "El rol no se puede cambiar después.",
         "opciones": [("", "Selecciona...")] + [(r.value, r.label) for r in ROLES_EMPLEADO]},
        {"nombre": "especialidad", "etiqueta": "Especialidad", "max_largo": 100, "solo_profesional": True,
         "marcador": "Ej: Fuerza e hipertrofia"},
        {"nombre": "tarjeta_profesional", "etiqueta": "Tarjeta profesional", "max_largo": 50,
         "solo_profesional": True},
    ]


def perfil_profesional(usuario):
    modelo = PERFILES_PROFESIONAL.get(usuario.rol)
    return modelo.objects.filter(usuario=usuario).first() if modelo else None


@solo_administradores
def panel_empleados(request):
    errores = None
    if request.method == "POST":
        errores = guardar_empleado(request)
        if not errores:
            return volver(request, "panel_empleados")

    consulta = Usuario.objects.filter(rol__in=ROLES_EMPLEADO).select_related("sede")
    consulta = buscar(consulta, request.GET.get("q", ""), ["first_name", "last_name", "email", "telefono"])
    consulta = filtrar_estado(consulta, request.GET.get("estado", ""), "is_active")
    rol = request.GET.get("rol", "")
    if rol in ROLES_EMPLEADO:
        consulta = consulta.filter(rol=rol)
    pagina = paginar(request, consulta.order_by("first_name", "last_name"))

    registros = []
    for u in pagina:
        perfil = perfil_profesional(u)
        u.perfil = perfil
        registros.append({
            "id": u.pk, "first_name": u.first_name, "last_name": u.last_name, "email": u.email,
            "telefono": u.telefono, "sede": str(u.sede_id or ""), "rol": u.rol,
            "especialidad": perfil.especialidad if perfil else "",
            "tarjeta_profesional": perfil.tarjeta_profesional if perfil else "",
        })
    contexto = contexto_seccion(
        request, "empleados", campos_empleado(), pagina, registros,
        rol=request.GET.get("rol", ""),
        opciones_rol=[("", "Todos los roles")] + [(r.value, r.label) for r in ROLES_EMPLEADO],
        roles_profesional=[r.value for r in PERFILES_PROFESIONAL],
    )
    if errores:
        messages.error(request, "Revisa los campos marcados.")
        return render(request, "panel/empleados.html", reabrir_modal(contexto, request.POST, errores),
                      status=400)
    return render(request, "panel/empleados.html", contexto)


def guardar_empleado(request):
    """Crea o edita un empleado. Devuelve los errores ({} si se guardó)."""
    post = request.POST
    usuario = None
    if post.get("id"):
        usuario = get_object_or_404(Usuario, pk=post["id"], rol__in=ROLES_EMPLEADO)

    campos = campos_empleado()
    if usuario:
        campos = [c for c in campos if not c.get("solo_crear")]
    datos, errores = validar(campos, post)

    rol = usuario.rol if usuario else datos.get("rol")
    es_profesional = rol in PERFILES_PROFESIONAL
    if es_profesional and not datos.get("especialidad"):
        errores["especialidad"] = ["La especialidad es obligatoria para los profesionales."]
    correo = datos.get("email")
    if correo and Usuario.objects.filter(email__iexact=correo).exclude(pk=usuario.pk if usuario else None).exists():
        errores["email"] = ["Ya existe una cuenta con este correo."]

    if errores:
        return errores

    with transaction.atomic():
        if usuario is None:
            clave = generar_clave_temporal()
            es_admin = rol == RolUsuario.ADMINISTRADOR
            usuario = Usuario.objects.create_user(
                correo, clave, first_name=datos["first_name"], last_name=datos["last_name"],
                telefono=datos["telefono"], sede_id=datos["sede"] or None, rol=rol,
                is_staff=es_admin, is_superuser=es_admin,
            )
            if es_profesional:
                PERFILES_PROFESIONAL[rol].objects.create(
                    usuario=usuario, especialidad=datos["especialidad"],
                    tarjeta_profesional=datos["tarjeta_profesional"],
                )
            guardar_clave_para_mostrar(request, usuario, clave)
            messages.success(request, f"Empleado {usuario.get_full_name()} creado.")
        else:
            usuario.first_name = datos["first_name"]
            usuario.last_name = datos["last_name"]
            usuario.email = correo
            usuario.telefono = datos["telefono"]
            usuario.sede_id = datos["sede"] or None
            usuario.save()
            if es_profesional:
                PERFILES_PROFESIONAL[rol].objects.update_or_create(
                    usuario=usuario, defaults={"especialidad": datos["especialidad"],
                                               "tarjeta_profesional": datos["tarjeta_profesional"]},
                )
            messages.success(request, f"Empleado {usuario.get_full_name()} actualizado.")
    return {}


# =========================================================
# Clientes
# =========================================================

def campos_cliente():
    return [
        {"nombre": "first_name", "etiqueta": "Nombre", "obligatorio": True, "max_largo": 150},
        {"nombre": "last_name", "etiqueta": "Apellido", "obligatorio": True, "max_largo": 150},
        {"nombre": "email", "etiqueta": "Correo", "tipo": "email", "obligatorio": True, "completo": True},
        {"nombre": "telefono", "etiqueta": "Teléfono", "max_largo": 20},
        {"nombre": "sexo", "etiqueta": "Sexo", "tipo": "select",
         "opciones": [("", "Sin indicar")] + list(Sexo.choices)},
        {"nombre": "sede", "etiqueta": "Sede", "tipo": "select", "opciones": opciones_sede(),
         "completo": True},
    ]


@solo_administradores
def panel_clientes(request):
    errores = None
    if request.method == "POST":
        errores = guardar_cliente(request)
        if not errores:
            return volver(request, "panel_clientes")

    hoy = timezone.localdate()
    vigente = Suscripcion.objects.filter(
        cliente=OuterRef("pk"), estado=EstadoSuscripcion.ACTIVA,
        fecha_inicio__lte=hoy, fecha_fin__gte=hoy,
    )
    consulta = Cliente.objects.select_related("usuario", "usuario__sede").annotate(es_premium=Exists(vigente))
    consulta = buscar(consulta, request.GET.get("q", ""),
                      ["usuario__first_name", "usuario__last_name", "usuario__email", "usuario__telefono"])
    consulta = filtrar_estado(consulta, request.GET.get("estado", ""), "usuario__is_active")
    plan = request.GET.get("plan", "")
    if plan == "premium":
        consulta = consulta.filter(es_premium=True)
    elif plan == "gratis":
        consulta = consulta.filter(es_premium=False)
    pagina = paginar(request, consulta.order_by("-usuario__date_joined"))

    registros = [{
        "id": c.usuario_id, "first_name": c.usuario.first_name, "last_name": c.usuario.last_name,
        "email": c.usuario.email, "telefono": c.usuario.telefono, "sexo": c.sexo,
        "sede": str(c.usuario.sede_id or ""),
    } for c in pagina]
    contexto = contexto_seccion(
        request, "clientes", campos_cliente(), pagina, registros,
        plan=request.GET.get("plan", ""),
        opciones_plan=[("", "Todos los planes"), ("gratis", "Gratis"), ("premium", "Premium")],
    )
    if errores:
        messages.error(request, "Revisa los campos marcados.")
        return render(request, "panel/clientes.html", reabrir_modal(contexto, request.POST, errores),
                      status=400)
    return render(request, "panel/clientes.html", contexto)


def guardar_cliente(request):
    """Crea o edita un cliente. Devuelve los errores ({} si se guardó)."""
    post = request.POST
    usuario = None
    if post.get("id"):
        usuario = get_object_or_404(Usuario, pk=post["id"], rol=RolUsuario.CLIENTE)

    datos, errores = validar(campos_cliente(), post)
    correo = datos.get("email")
    if correo and Usuario.objects.filter(email__iexact=correo).exclude(pk=usuario.pk if usuario else None).exists():
        errores["email"] = ["Ya existe una cuenta con este correo."]

    if errores:
        return errores

    with transaction.atomic():
        if usuario is None:
            clave = generar_clave_temporal()
            usuario = Usuario.objects.create_user(
                correo, clave, first_name=datos["first_name"], last_name=datos["last_name"],
                telefono=datos["telefono"], sede_id=datos["sede"] or None, rol=RolUsuario.CLIENTE,
            )
            Cliente.objects.create(usuario=usuario, sexo=datos["sexo"])
            guardar_clave_para_mostrar(request, usuario, clave)
            messages.success(request, f"Cliente {usuario.get_full_name()} creado.")
        else:
            usuario.first_name = datos["first_name"]
            usuario.last_name = datos["last_name"]
            usuario.email = correo
            usuario.telefono = datos["telefono"]
            usuario.sede_id = datos["sede"] or None
            usuario.save()
            Cliente.objects.update_or_create(usuario=usuario, defaults={"sexo": datos["sexo"]})
            messages.success(request, f"Cliente {usuario.get_full_name()} actualizado.")
    return {}


# =========================================================
# Usuarios (empleados y clientes): contraseña temporal
# =========================================================

@solo_administradores
@require_POST
def panel_nueva_clave(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    clave = generar_clave_temporal()
    usuario.set_password(clave)
    usuario.save(update_fields=["password"])
    guardar_clave_para_mostrar(request, usuario, clave)
    messages.success(request, f"Nueva contraseña temporal para {usuario.get_full_name() or usuario.email}.")
    return volver(request, "panel")


# =========================================================
# Sedes
# =========================================================

CAMPOS_SEDE = [
    {"nombre": "nombre", "etiqueta": "Nombre", "obligatorio": True, "max_largo": 100, "completo": True},
    {"nombre": "ciudad", "etiqueta": "Ciudad", "obligatorio": True, "max_largo": 100},
    {"nombre": "direccion", "etiqueta": "Dirección", "obligatorio": True, "max_largo": 200},
    {"nombre": "telefono", "etiqueta": "Teléfono", "obligatorio": True, "max_largo": 20},
    {"nombre": "correo", "etiqueta": "Correo", "tipo": "email"},
    {"nombre": "capacidad", "etiqueta": "Capacidad (personas)", "tipo": "entero", "minimo": 1},
    {"nombre": "activa", "etiqueta": "Sede activa", "tipo": "checkbox", "completo": True},
]


@solo_administradores
def panel_sedes(request):
    if request.method == "POST":
        sede = get_object_or_404(Sede, pk=request.POST["id"]) if request.POST.get("id") else Sede()
        datos, errores = validar(CAMPOS_SEDE, request.POST)
        if not errores:
            for campo, valor in datos.items():
                setattr(sede, campo, valor)
            nueva = sede.pk is None
            sede.save()
            messages.success(request, f"Sede {sede.nombre} {'creada' if nueva else 'actualizada'}.")
            return volver(request, "panel_sedes")

    consulta = Sede.objects.annotate(num_usuarios=Count("usuarios"))
    consulta = buscar(consulta, request.GET.get("q", ""), ["nombre", "ciudad", "direccion", "correo"])
    consulta = filtrar_estado(consulta, request.GET.get("estado", ""), "activa")
    pagina = paginar(request, consulta.order_by("nombre"))
    registros = [{"id": s.pk, "nombre": s.nombre, "ciudad": s.ciudad, "direccion": s.direccion,
                  "telefono": s.telefono, "correo": s.correo, "capacidad": s.capacidad or "",
                  "activa": s.activa} for s in pagina]
    contexto = contexto_seccion(request, "sedes", CAMPOS_SEDE, pagina, registros)
    if request.method == "POST":
        messages.error(request, "Revisa los campos marcados.")
        return render(request, "panel/sedes.html", reabrir_modal(contexto, request.POST, errores), status=400)
    return render(request, "panel/sedes.html", contexto)


# =========================================================
# Membresías
# =========================================================

CAMPOS_MEMBRESIA = [
    {"nombre": "tipo", "etiqueta": "Plan", "tipo": "select", "obligatorio": True,
     "opciones": list(TipoMembresia.choices)},
    {"nombre": "duracion", "etiqueta": "Duración", "tipo": "select", "obligatorio": True,
     "opciones": [("", "Selecciona...")] + list(DuracionMembresia.choices)},
    {"nombre": "precio", "etiqueta": "Precio (COP)", "tipo": "decimal", "obligatorio": True, "minimo": 1,
     "maximo": Decimal("9999999999"), "completo": True, "marcador": "89000"},
    {"nombre": "descripcion", "etiqueta": "Descripción", "tipo": "textarea", "completo": True},
    {"nombre": "activa", "etiqueta": "Membresía activa (se muestra en el inicio)", "tipo": "checkbox",
     "completo": True},
]


@solo_administradores
def panel_membresias(request):
    if request.method == "POST":
        membresia = (get_object_or_404(Membresia, pk=request.POST["id"])
                     if request.POST.get("id") else Membresia())
        datos, errores = validar(CAMPOS_MEMBRESIA, request.POST)
        # Solo un plan activo por tipo y duración, para no mostrar dos precios en el inicio
        if not errores and datos["activa"]:
            repetida = Membresia.objects.filter(tipo=datos["tipo"], duracion=datos["duracion"], activa=True)
            if repetida.exclude(pk=membresia.pk).exists():
                errores["duracion"] = ["Ya hay una membresía activa con esta duración. Desactívala primero."]
        if not errores:
            for campo, valor in datos.items():
                setattr(membresia, campo, valor)
            nueva = membresia.pk is None
            membresia.save()
            messages.success(request, f"Membresía {membresia} {'creada' if nueva else 'actualizada'}.")
            return volver(request, "panel_membresias")

    hoy = timezone.localdate()
    consulta = Membresia.objects.annotate(num_activas=Count(
        "suscripciones", filter=Q(suscripciones__estado=EstadoSuscripcion.ACTIVA,
                                  suscripciones__fecha_fin__gte=hoy),
    ))
    consulta = filtrar_estado(consulta, request.GET.get("estado", ""), "activa")
    pagina = paginar(request, consulta.order_by("tipo", "precio"))
    registros = [{"id": m.pk, "tipo": m.tipo, "duracion": m.duracion, "precio": numero_texto(m.precio),
                  "descripcion": m.descripcion, "activa": m.activa} for m in pagina]
    contexto = contexto_seccion(request, "membresias", CAMPOS_MEMBRESIA, pagina, registros)
    if request.method == "POST":
        messages.error(request, "Revisa los campos marcados.")
        return render(request, "panel/membresias.html", reabrir_modal(contexto, request.POST, errores),
                      status=400)
    return render(request, "panel/membresias.html", contexto)


# =========================================================
# Ejercicios
# =========================================================

CAMPOS_EJERCICIO = [
    {"nombre": "nombre", "etiqueta": "Nombre", "obligatorio": True, "max_largo": 150, "completo": True},
    {"nombre": "musculo", "etiqueta": "Grupo muscular", "obligatorio": True, "max_largo": 100,
     "marcador": "Ej: Pierna"},
    {"nombre": "maquina", "etiqueta": "Máquina / equipo", "max_largo": 100, "marcador": "Ej: Barra"},
    {"nombre": "imagen_url", "etiqueta": "URL de la imagen", "tipo": "url", "completo": True,
     "marcador": "https://..."},
    {"nombre": "descripcion", "etiqueta": "Descripción", "tipo": "textarea", "completo": True},
    {"nombre": "activo", "etiqueta": "Ejercicio activo", "tipo": "checkbox", "completo": True},
]


@solo_administradores
def panel_ejercicios(request):
    if request.method == "POST":
        ejercicio = (get_object_or_404(Ejercicio, pk=request.POST["id"])
                     if request.POST.get("id") else Ejercicio())
        datos, errores = validar(CAMPOS_EJERCICIO, request.POST)
        if not errores:
            for campo, valor in datos.items():
                setattr(ejercicio, campo, valor)
            nuevo = ejercicio.pk is None
            ejercicio.save()
            messages.success(request, f"Ejercicio {ejercicio.nombre} {'creado' if nuevo else 'actualizado'}.")
            return volver(request, "panel_ejercicios")

    consulta = buscar(Ejercicio.objects.all(), request.GET.get("q", ""), ["nombre", "musculo", "maquina"])
    consulta = filtrar_estado(consulta, request.GET.get("estado", ""), "activo")
    musculo = request.GET.get("musculo", "")
    if musculo:
        consulta = consulta.filter(musculo=musculo)
    pagina = paginar(request, consulta.order_by("nombre"))
    registros = [{"id": e.pk, "nombre": e.nombre, "musculo": e.musculo, "maquina": e.maquina,
                  "imagen_url": e.imagen_url, "descripcion": e.descripcion, "activo": e.activo}
                 for e in pagina]
    musculos = Ejercicio.objects.order_by("musculo").values_list("musculo", flat=True).distinct()
    contexto = contexto_seccion(
        request, "ejercicios", CAMPOS_EJERCICIO, pagina, registros, musculo=musculo,
        opciones_musculo=[("", "Todos los grupos")] + [(m, m) for m in musculos],
    )
    if request.method == "POST":
        messages.error(request, "Revisa los campos marcados.")
        return render(request, "panel/ejercicios.html", reabrir_modal(contexto, request.POST, errores),
                      status=400)
    return render(request, "panel/ejercicios.html", contexto)


# =========================================================
# Alimentos
# =========================================================

CAMPOS_ALIMENTO = [
    {"nombre": "nombre", "etiqueta": "Nombre", "obligatorio": True, "max_largo": 150, "completo": True},
    {"nombre": "categoria", "etiqueta": "Categoría", "max_largo": 50, "marcador": "Ej: Proteínas"},
    {"nombre": "codigo_barras", "etiqueta": "Código de barras", "max_largo": 20},
    {"nombre": "kcal", "etiqueta": "Calorías (kcal / 100 g)", "tipo": "decimal", "obligatorio": True,
     "maximo": Decimal("9999")},
    {"nombre": "proteinas", "etiqueta": "Proteínas (g / 100 g)", "tipo": "decimal", "obligatorio": True,
     "maximo": Decimal("100")},
    {"nombre": "carbohidratos", "etiqueta": "Carbohidratos (g / 100 g)", "tipo": "decimal",
     "obligatorio": True, "maximo": Decimal("100")},
    {"nombre": "grasas", "etiqueta": "Grasas (g / 100 g)", "tipo": "decimal", "obligatorio": True,
     "maximo": Decimal("100")},
    {"nombre": "porcion_gramos", "etiqueta": "Porción típica (g)", "tipo": "decimal", "obligatorio": True,
     "minimo": Decimal("0.1"), "maximo": Decimal("9999"), "marcador": "100"},
    {"nombre": "porcion_nombre", "etiqueta": "Nombre de la porción", "max_largo": 50,
     "marcador": "Ej: 1 unidad"},
    {"nombre": "imagen_url", "etiqueta": "URL de la imagen", "tipo": "url", "completo": True,
     "marcador": "https://..."},
    {"nombre": "activo", "etiqueta": "Alimento activo", "tipo": "checkbox", "completo": True},
]


@solo_administradores
def panel_alimentos(request):
    if request.method == "POST":
        alimento = (get_object_or_404(Alimento, pk=request.POST["id"])
                    if request.POST.get("id") else Alimento())
        datos, errores = validar(CAMPOS_ALIMENTO, request.POST)
        codigo = datos.get("codigo_barras")
        if codigo and Alimento.objects.filter(codigo_barras=codigo).exclude(pk=alimento.pk).exists():
            errores["codigo_barras"] = ["Ya hay un alimento con este código de barras."]
        if not errores:
            for campo, valor in datos.items():
                setattr(alimento, campo, valor)
            alimento.codigo_barras = codigo or None  # vacío = sin código (el campo es único)
            nuevo = alimento.pk is None
            alimento.save()
            messages.success(request, f"Alimento {alimento.nombre} {'creado' if nuevo else 'actualizado'}.")
            return volver(request, "panel_alimentos")

    consulta = buscar(Alimento.objects.all(), request.GET.get("q", ""), ["nombre", "categoria", "codigo_barras"])
    consulta = filtrar_estado(consulta, request.GET.get("estado", ""), "activo")
    categoria = request.GET.get("categoria", "")
    if categoria:
        consulta = consulta.filter(categoria=categoria)
    pagina = paginar(request, consulta.order_by("nombre"))
    registros = [{"id": a.pk, "nombre": a.nombre, "categoria": a.categoria,
                  "codigo_barras": a.codigo_barras or "", "kcal": numero_texto(a.kcal), "proteinas": numero_texto(a.proteinas),
                  "carbohidratos": numero_texto(a.carbohidratos), "grasas": numero_texto(a.grasas),
                  "porcion_gramos": numero_texto(a.porcion_gramos), "porcion_nombre": a.porcion_nombre,
                  "imagen_url": a.imagen_url, "activo": a.activo} for a in pagina]
    categorias = (Alimento.objects.exclude(categoria="").order_by("categoria")
                  .values_list("categoria", flat=True).distinct())
    contexto = contexto_seccion(
        request, "alimentos", CAMPOS_ALIMENTO, pagina, registros, categoria=categoria,
        opciones_categoria=[("", "Todas las categorías")] + [(c, c) for c in categorias],
    )
    if request.method == "POST":
        messages.error(request, "Revisa los campos marcados.")
        return render(request, "panel/alimentos.html", reabrir_modal(contexto, request.POST, errores),
                      status=400)
    return render(request, "panel/alimentos.html", contexto)


# =========================================================
# Activar / desactivar (nada se borra)
# =========================================================

# sección -> (modelo, campo de estado, filtro extra, nombre de la URL de la lista)
ESTADOS = {
    "empleados": (Usuario, "is_active", {"rol__in": ROLES_EMPLEADO}, "panel_empleados"),
    "clientes": (Usuario, "is_active", {"rol": RolUsuario.CLIENTE}, "panel_clientes"),
    "sedes": (Sede, "activa", {}, "panel_sedes"),
    "membresias": (Membresia, "activa", {}, "panel_membresias"),
    "ejercicios": (Ejercicio, "activo", {}, "panel_ejercicios"),
    "alimentos": (Alimento, "activo", {}, "panel_alimentos"),
}


@solo_administradores
@require_POST
def panel_cambiar_estado(request, seccion, pk):
    if seccion not in ESTADOS:
        return redirect("panel")
    modelo, campo, filtro, lista = ESTADOS[seccion]
    registro = get_object_or_404(modelo, pk=pk, **filtro)
    activar = request.POST.get("activar") == "1"

    if modelo is Usuario and registro.pk == request.user.pk and not activar:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
        return volver(request, lista)

    if modelo is Membresia and activar:
        repetida = Membresia.objects.filter(tipo=registro.tipo, duracion=registro.duracion, activa=True)
        if repetida.exclude(pk=registro.pk).exists():
            messages.error(request, "Ya hay una membresía activa con esa duración. Desactívala primero.")
            return volver(request, lista)

    setattr(registro, campo, activar)
    registro.save(update_fields=[campo])
    nombre = registro.get_full_name() if modelo is Usuario else str(registro)
    messages.success(request, f"{nombre}: {'activado' if activar else 'desactivado'}.")
    return volver(request, lista)
