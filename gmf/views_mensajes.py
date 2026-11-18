"""
Mensajes entre usuarios (/mensajes/).

Una sola bandeja con dos pestañas para el personal del gimnasio:
- Clientes: conversaciones con usuarios de rol CLIENTE (para el entrenador, también sus clientes
  aunque aún no haya mensajes).
- Equipo de trabajo: cualquier otro rol (administrador, nutricionista, fisioterapeuta,
  recepcionista, entrenador). Se puede iniciar una conversación con cualquier empleado activo.
El cliente ve una sola lista: sus profesionales y el personal con el que ya habló.

- GET  /mensajes/                 bandeja (abre la conversación más reciente de la pestaña)
- GET  /mensajes/<usuario_id>/    bandeja con esa conversación abierta (marca como leídos)
- POST /mensajes/<usuario_id>/    envía un mensaje
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AsignacionDieta, AsignacionRutina, Mensaje, RolUsuario, Usuario

MAX_TEXTO = 2000


def puede_escribir(yo, otro):
    """El personal escribe a cualquiera; un cliente solo al personal (no a otros clientes)."""
    if otro == yo or not otro.is_active:
        return False
    return not (yo.rol == RolUsuario.CLIENTE and otro.rol == RolUsuario.CLIENTE)


def clientes_del_entrenador(usuario):
    """Clientes que tienen o tuvieron una rutina asignada por este entrenador."""
    if usuario.rol != RolUsuario.ENTRENADOR or not hasattr(usuario, "entrenador"):
        return Usuario.objects.none()
    ids = AsignacionRutina.objects.filter(entrenador=usuario.entrenador).values("cliente__usuario")
    return Usuario.objects.filter(id__in=ids, is_active=True)


def profesionales_del_cliente(usuario):
    """Entrenadores y nutricionistas que le asignaron algo al cliente."""
    if not hasattr(usuario, "cliente"):
        return Usuario.objects.none()
    ids_e = AsignacionRutina.objects.filter(cliente=usuario.cliente, entrenador__isnull=False) \
                                    .values("entrenador__usuario")
    ids_n = AsignacionDieta.objects.filter(cliente=usuario.cliente, nutricionista__isnull=False) \
                                   .values("nutricionista__usuario")
    return Usuario.objects.filter(Q(id__in=ids_e) | Q(id__in=ids_n), is_active=True)


def pestana_de(yo, otro):
    if yo.rol == RolUsuario.CLIENTE:
        return "todos"
    return "clientes" if otro.rol == RolUsuario.CLIENTE else "equipo"


def contactos(yo, pestana, texto=""):
    """Filas de la lista: usuario, último mensaje, no leídos. Ordenadas por actividad."""
    # Con quién ya hay conversación
    con_mensajes = set(
        Mensaje.objects.filter(remitente=yo).values_list("destinatario", flat=True)
    ) | set(Mensaje.objects.filter(destinatario=yo).values_list("remitente", flat=True))

    if pestana == "todos":  # cliente
        base = Usuario.objects.filter(Q(id__in=con_mensajes) | Q(id__in=profesionales_del_cliente(yo).values("id")))
        base = base.exclude(rol=RolUsuario.CLIENTE)
    elif pestana == "clientes":
        base = Usuario.objects.filter(rol=RolUsuario.CLIENTE).filter(
            Q(id__in=con_mensajes) | Q(id__in=clientes_del_entrenador(yo).values("id"))
        )
    else:  # equipo: todos los empleados activos (y los inactivos con los que ya se habló)
        base = Usuario.objects.exclude(rol=RolUsuario.CLIENTE).filter(Q(is_active=True) | Q(id__in=con_mensajes))
    base = base.exclude(id=yo.id)
    for palabra in texto.split():
        base = base.filter(Q(first_name__icontains=palabra) | Q(last_name__icontains=palabra)
                           | Q(email__icontains=palabra))

    no_leidos = dict(
        Mensaje.objects.filter(destinatario=yo, leido=False).values_list("remitente").annotate(n=Count("id"))
    )
    filas = []
    for u in base.select_related("sede"):
        ultimo = Mensaje.conversacion(yo, u).order_by("-fecha_envio", "-id").first()
        filas.append({"usuario": u, "ultimo": ultimo, "no_leidos": no_leidos.get(u.id, 0)})
    # Primero las conversaciones con mensajes (más recientes arriba), luego el resto por nombre
    filas.sort(key=lambda f: (f["ultimo"] is None,
                              -(f["ultimo"].fecha_envio.timestamp()) if f["ultimo"] else 0,
                              f["usuario"].get_full_name().lower()))
    return filas


def no_leidos_por_pestana(yo):
    consulta = Mensaje.objects.filter(destinatario=yo, leido=False)
    return {
        "clientes": consulta.filter(remitente__rol=RolUsuario.CLIENTE).count(),
        "equipo": consulta.exclude(remitente__rol=RolUsuario.CLIENTE).count(),
    }


def detalle_de(otro):
    """Texto bajo el nombre en la cabecera del chat."""
    if otro.rol == RolUsuario.CLIENTE:
        cliente = getattr(otro, "cliente", None)
        asignacion = cliente.rutina_actual if cliente else None
        if asignacion:
            return f"Rutina: {asignacion.rutina.nombre} · semana {asignacion.semana_actual} de {asignacion.rutina.semanas}"
        return "Sin rutina asignada"
    partes = []
    for perfil in ("entrenador", "nutricionista", "fisioterapeuta"):
        p = getattr(otro, perfil, None)
        if p and p.especialidad:
            partes.append(p.especialidad)
    if otro.sede:
        partes.append(otro.sede.nombre)
    return " · ".join(partes)


def dias_de_conversacion(mensajes_chat):
    """Agrupa los mensajes por día con su separador ("Hoy", "Ayer", "12 nov")."""
    hoy = timezone.localdate()
    grupos = []
    for m in mensajes_chat:
        fecha = timezone.localtime(m.fecha_envio).date()
        if not grupos or grupos[-1]["fecha"] != fecha:
            if fecha == hoy:
                etiqueta = "Hoy"
            elif (hoy - fecha).days == 1:
                etiqueta = "Ayer"
            else:
                etiqueta = fecha
            grupos.append({"fecha": fecha, "etiqueta": etiqueta, "mensajes": []})
        grupos[-1]["mensajes"].append(m)
    return grupos


@login_required
def mensajes_bandeja(request, usuario_id=None):
    yo = request.user
    otro = get_object_or_404(Usuario, pk=usuario_id) if usuario_id else None
    if otro == yo:
        return redirect("mensajes")

    error = ""
    if request.method == "POST":
        if not otro:
            return redirect("mensajes")
        texto = request.POST.get("texto", "").strip()
        if not puede_escribir(yo, otro):
            messages.error(request, "No puedes enviar mensajes a este usuario.")
            return redirect("conversacion", usuario_id=otro.id)
        if not texto:
            error = "Escribe un mensaje."
        elif len(texto) > MAX_TEXTO:
            error = f"El mensaje admite máximo {MAX_TEXTO} caracteres."
        else:
            Mensaje.objects.create(remitente=yo, destinatario=otro, texto=texto)
            return redirect("conversacion", usuario_id=otro.id)

    es_cliente = yo.rol == RolUsuario.CLIENTE
    if otro:
        pestana = pestana_de(yo, otro)
    else:
        pestana = "todos" if es_cliente else request.GET.get("pestana", "clientes")
        if pestana not in ("clientes", "equipo", "todos") or (pestana == "todos" and not es_cliente):
            pestana = "clientes"
    texto_buscar = request.GET.get("q", "").strip()
    filas = contactos(yo, pestana, texto_buscar)

    # Sin conversación elegida (y en escritorio): se abre la más reciente con mensajes
    if not otro and filas and filas[0]["ultimo"] and request.GET.get("lista") != "1":
        return redirect(f"{request.path}{filas[0]['usuario'].id}/")

    chat = []
    if otro:
        Mensaje.objects.filter(remitente=otro, destinatario=yo, leido=False).update(leido=True)
        for fila in filas:
            if fila["usuario"].id == otro.id:
                fila["no_leidos"] = 0
        if not any(f["usuario"].id == otro.id for f in filas):
            # Conversación nueva con alguien que no estaba en la lista: se muestra arriba
            filas.insert(0, {"usuario": otro, "ultimo": None, "no_leidos": 0})
        chat = dias_de_conversacion(Mensaje.conversacion(yo, otro).order_by("fecha_envio", "id"))

    contexto = {
        "seccion": "mensajes", "pestana": pestana, "es_cliente": es_cliente,
        "filas": filas, "q": texto_buscar, "otro": otro, "chat": chat,
        "detalle_otro": detalle_de(otro) if otro else "",
        "puede_escribir": puede_escribir(yo, otro) if otro else False,
        "no_leidos": no_leidos_por_pestana(yo), "error": error, "texto": request.POST.get("texto", ""),
        "max_texto": MAX_TEXTO, "hoy_texto": timezone.localdate().strftime("%Y%m%d"),
    }
    return render(request, "mensajes/mensajes.html", contexto, status=400 if error else 200)
