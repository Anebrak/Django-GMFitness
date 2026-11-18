"""
Panel del entrenador (/entrenador/...). Solo rol ENTRENADOR (decorador solo_entrenadores).

"Mis clientes" = clientes que tienen o tuvieron una rutina asignada por este entrenador.
Métricas (no hay modelo de sesión):
- sesión = una fecha distinta con registros de ProgresoEjercicio del cliente;
- adherencia = sesiones hechas / días planeados (rutina.dias_por_semana) en las últimas 4 semanas
  de la asignación activa (máx. 100 %);
- necesita atención = sin rutina activa o más de 7 días sin entrenar.

- GET  /entrenador/                                resumen
- GET  /entrenador/clientes/                       Mis clientes
- GET  /entrenador/clientes/<id>/                  detalle del cliente
- POST /entrenador/clientes/<id>/asignar/          asigna (o reemplaza) la rutina
- POST /entrenador/clientes/<id>/peso/             registra un peso (ProgresoFisico)
- POST /entrenador/clientes/<id>/cargas/           edita registros de cargas
"""
from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    AsignacionRutina, Cliente, EstadoAsignacion, EstadoRutina, Notificacion, ProgresoEjercicio,
    ProgresoFisico, RolUsuario, Rutina,
)
from .views_rutinas import decimal_o_none, entero, numero_texto

POR_PAGINA = 10
DIAS_SIN_ENTRENAR = 7
FILTROS_CLIENTES = [("activos", "Activos"), ("sin_rutina", "Sin rutina"),
                    ("atencion", "Necesitan atención"), ("inactivos", "Inactivos")]


# =========================================================
# Acceso
# =========================================================

def solo_entrenadores(vista):
    """Deja pasar solo a usuarios con rol ENTRENADOR que tengan su perfil."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.rol != RolUsuario.ENTRENADOR or not hasattr(request.user, "entrenador"):
            messages.error(request, "Esta sección es solo para entrenadores.")
            return redirect("inicio")
        return vista(request, *args, **kwargs)
    return envoltura


def volver(request, por_defecto, **kwargs):
    destino = request.POST.get("volver", "")
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                       require_https=request.is_secure()):
        return redirect(destino)
    return redirect(por_defecto, **kwargs)


# =========================================================
# Métricas de un cliente
# =========================================================

def mis_clientes(entrenador):
    ids = AsignacionRutina.objects.filter(entrenador=entrenador).values("cliente")
    return Cliente.objects.filter(id__in=ids).select_related("usuario")


def fechas_sesion(cliente):
    return sorted(set(cliente.progresos_ejercicio.values_list("fecha", flat=True)), reverse=True)


def adherencia(asignacion, sesiones, hoy, semanas=4):
    """(porcentaje, hechas, planeadas) en las últimas `semanas` semanas de la asignación."""
    if not asignacion or asignacion.fecha_inicio > hoy:
        return None, 0, 0
    desde = max(asignacion.fecha_inicio, hoy - timedelta(days=7 * semanas - 1))
    dias = (hoy - desde).days + 1
    planeadas = max(round(dias / 7 * asignacion.rutina.dias_por_semana), 1)
    hechas = sum(1 for f in sesiones if desde <= f <= hoy)
    return min(round(hechas * 100 / planeadas), 100), hechas, planeadas


def peso_hace(cliente, dias, hoy):
    """Peso registrado en o antes de hace `dias` días (o el primero, si no hay tan antiguo)."""
    progresos = cliente.progresos_fisicos.all()
    anterior = progresos.filter(fecha__lte=hoy - timedelta(days=dias)).order_by("-fecha", "-id").first()
    return (anterior or progresos.order_by("fecha", "id").first())


def variacion_peso(cliente, dias, hoy):
    if cliente.peso is None:
        return None
    anterior = peso_hace(cliente, dias, hoy)
    if not anterior:
        return None
    return cliente.peso - anterior.peso


def texto_ultima_sesion(fecha, hoy):
    if not fecha:
        return "Sin registros"
    dias = (hoy - fecha).days
    if dias == 0:
        return "Hoy"
    if dias == 1:
        return "Ayer"
    return f"Hace {dias} días"


def resumen_cliente(cliente, hoy):
    """Todo lo que muestra la fila de 'Mis clientes'."""
    asignacion = cliente.rutina_actual
    sesiones = fechas_sesion(cliente)
    ultima = sesiones[0] if sesiones else None
    pct, hechas, planeadas = adherencia(asignacion, sesiones, hoy)
    sin_entrenar = ultima is None or (hoy - ultima).days > DIAS_SIN_ENTRENAR
    semana = asignacion.semana_actual if asignacion else None
    return {
        "cliente": cliente, "usuario": cliente.usuario, "asignacion": asignacion,
        "semana": semana,
        "progreso_pct": round(semana * 100 / asignacion.rutina.semanas) if asignacion else 0,
        "adherencia": pct, "sesiones_hechas": hechas, "sesiones_planeadas": planeadas,
        "ultima_sesion": ultima, "texto_ultima": texto_ultima_sesion(ultima, hoy),
        "entreno_hoy": ultima == hoy,
        "variacion": variacion_peso(cliente, 28, hoy),
        "activo": cliente.usuario.is_active,
        "atencion": cliente.usuario.is_active and (asignacion is None or sin_entrenar),
        "objetivo": (asignacion.rutina.objetivo if asignacion and asignacion.rutina.objetivo else ""),
    }


def kpis(filas):
    activos = [f for f in filas if f["activo"] and f["asignacion"]]
    con_adherencia = [f["adherencia"] for f in activos if f["adherencia"] is not None]
    return {
        "activos": len(activos),
        "sin_rutina": sum(1 for f in filas if f["activo"] and not f["asignacion"]),
        "inactivos": sum(1 for f in filas if not f["activo"]),
        "entrenaron_hoy": sum(1 for f in filas if f["activo"] and f["entreno_hoy"]),
        "adherencia_media": round(sum(con_adherencia) / len(con_adherencia)) if con_adherencia else None,
        "atencion": sum(1 for f in filas if f["atencion"]),
    }


def rutinas_para_asignar(usuario):
    return Rutina.objects.filter(autor=usuario, estado=EstadoRutina.PUBLICADA).order_by("nombre")


def proximo_lunes(hoy):
    return hoy + timedelta(days=(7 - hoy.weekday()) % 7 or 7)


def contexto_asignar(usuario, hoy, valores=None, errores=None):
    return {
        "rutinas_asignables": rutinas_para_asignar(usuario),
        "fecha_por_defecto": proximo_lunes(hoy),
        "valores_asignar": valores or {}, "errores_asignar": errores or {},
    }


# =========================================================
# Resumen
# =========================================================

@solo_entrenadores
def resumen(request):
    hoy = timezone.localdate()
    filas = [resumen_cliente(c, hoy) for c in mis_clientes(request.user.entrenador)]
    contexto = {
        "seccion": "resumen", "kpis": kpis(filas),
        "atencion": [f for f in filas if f["atencion"]][:6],
        "borradores": Rutina.objects.filter(autor=request.user, estado=EstadoRutina.BORRADOR)
                                    .order_by("-fecha_actualizacion")[:5],
        "total_rutinas": Rutina.objects.filter(autor=request.user).count(),
    }
    return render(request, "entrenador/resumen.html", contexto)


# =========================================================
# Mis clientes
# =========================================================

@solo_entrenadores
def clientes(request):
    hoy = timezone.localdate()
    consulta = mis_clientes(request.user.entrenador)
    texto = request.GET.get("q", "").strip()
    for palabra in texto.split():
        consulta = consulta.filter(Q(usuario__first_name__icontains=palabra)
                                   | Q(usuario__last_name__icontains=palabra)
                                   | Q(usuario__email__icontains=palabra))
    todas = [resumen_cliente(c, hoy) for c in mis_clientes(request.user.entrenador)]
    filas = [resumen_cliente(c, hoy) for c in consulta.order_by("usuario__first_name", "usuario__last_name")]

    filtro = request.GET.get("filtro", "activos")
    if filtro == "activos":
        filas = [f for f in filas if f["activo"] and f["asignacion"]]
    elif filtro == "sin_rutina":
        filas = [f for f in filas if f["activo"] and not f["asignacion"]]
    elif filtro == "atencion":
        filas = [f for f in filas if f["atencion"]]
    elif filtro == "inactivos":
        filas = [f for f in filas if not f["activo"]]
    else:
        filtro = "todos"

    pagina = Paginator(filas, POR_PAGINA).get_page(request.GET.get("pagina"))
    contexto = {
        "seccion": "clientes", "kpis": kpis(todas), "pagina": pagina, "filtro": filtro,
        "filtros": FILTROS_CLIENTES, "q": texto,
        **contexto_asignar(request.user, hoy),
    }
    return render(request, "entrenador/clientes.html", contexto)


# =========================================================
# Detalle del cliente
# =========================================================

def barras_peso(cliente, hoy, semanas):
    """Último peso de cada semana (las semanas sin registro repiten el anterior)."""
    inicio = hoy - timedelta(days=hoy.weekday()) - timedelta(weeks=semanas - 1)
    registros = list(cliente.progresos_fisicos.filter(fecha__lte=hoy).order_by("fecha", "id"))
    previo = next((r.peso for r in reversed(registros) if r.fecha < inicio), None)
    barras = []
    for n in range(semanas):
        desde, hasta = inicio + timedelta(weeks=n), inicio + timedelta(weeks=n, days=6)
        en_semana = [r.peso for r in registros if desde <= r.fecha <= hasta]
        valor = en_semana[-1] if en_semana else previo
        previo = valor
        barras.append({"etiqueta": f"S{n + 1}", "valor": valor, "desde": desde})
    valores = [b["valor"] for b in barras if b["valor"] is not None]
    if valores:
        minimo, maximo = min(valores), max(valores)
        rango = (maximo - minimo) or Decimal(1)
        for b in barras:
            # Altura entre 25 % y 100 % para que se note la diferencia entre semanas
            b["alto"] = int(25 + (b["valor"] - minimo) / rango * 75) if b["valor"] is not None else 0
    return barras


def volumen_entre(cliente, desde, hasta):
    return sum((r.calcular_volumen() for r in cliente.progresos_ejercicio.filter(fecha__range=(desde, hasta))),
               Decimal(0))


def proxima_sesion(asignacion, sesiones, hoy):
    """Día de la semana actual que toca (sesiones hechas esta semana + 1)."""
    if not asignacion:
        return None
    rutina = asignacion.rutina
    inicio_semana = asignacion.fecha_inicio + timedelta(weeks=max((hoy - asignacion.fecha_inicio).days, 0) // 7)
    hechas = sum(1 for f in sesiones if inicio_semana <= f < hoy)
    numero = min(hechas + 1, rutina.dias_por_semana)
    semana = asignacion.semana_actual
    dia = rutina.dias.filter(semana=semana, dia=numero).first()
    detalle = rutina.detalle.filter(semana=semana, dia=numero).prefetch_related("series_detalle")
    total_series = sum(re.series for re in detalle)
    descanso = sum((s.descanso_segundos or 60) for re in detalle for s in re.series_detalle.all())
    minutos = round((total_series * 45 + descanso) / 60) if total_series else 0
    return {"dia": numero, "nombre": dia.nombre if dia else "", "ejercicios": len(detalle), "minutos": minutos}


def historial_cargas(cliente, ejercicio_id):
    """Registros del ejercicio agrupados por fecha, cada uno con sus series (una fila = una serie)."""
    registros = (cliente.progresos_ejercicio.filter(ejercicio_id=ejercicio_id)
                 .select_related("asignacion__rutina").order_by("-fecha", "numero_serie", "id"))
    por_fecha = OrderedDict()
    for r in registros:
        por_fecha.setdefault(r.fecha, []).append(r)
    filas = []
    for fecha, series in por_fecha.items():
        asignacion = next((s.asignacion for s in series if s.asignacion_id), None)
        filas.append({
            "fecha": fecha,
            "semana": asignacion.semana_de(fecha) if asignacion else None,
            "series": [{"id": s.id, "kg": s.carga_kg, "kg_texto": numero_texto(s.carga_kg),
                        "reps": s.repeticiones_realizadas, "editado": s.editado_por_entrenador}
                       for s in series],
            "volumen": sum((s.carga_kg * s.repeticiones_realizadas for s in series), Decimal(0)),
        })
    todas = [s for f in filas for s in f["series"]]
    mejor = max(todas, key=lambda s: (s["kg"], s["reps"]), default=None)
    rm = max((s["kg"] * (1 + Decimal(s["reps"]) / 30) for s in todas), default=None)
    progreso = None
    if len(filas) > 1:
        progreso = max(s["kg"] for s in filas[0]["series"]) - max(s["kg"] for s in filas[-1]["series"])
    return {
        "filas": filas, "columnas": range(1, max((len(f["series"]) for f in filas), default=0) + 1),
        "mejor": mejor, "rm": rm.quantize(Decimal("0.1")) if rm is not None else None, "progreso": progreso,
    }


def contexto_detalle(request, cliente, hoy):
    asignacion = cliente.rutina_actual
    sesiones = fechas_sesion(cliente)
    ultima = sesiones[0] if sesiones else None
    pct, hechas, planeadas = adherencia(asignacion, sesiones, hoy, semanas=52)

    rango = request.GET.get("rango", "12")
    semanas_grafico = 26 if rango == "26" else 12
    lunes = hoy - timedelta(days=hoy.weekday())
    vol_semana = volumen_entre(cliente, lunes, hoy)
    vol_anterior = volumen_entre(cliente, lunes - timedelta(weeks=1), lunes - timedelta(days=1))

    ejercicios_registrados = (cliente.progresos_ejercicio.values("ejercicio_id", "ejercicio__nombre")
                              .distinct().order_by("ejercicio__nombre"))
    ejercicio_id = entero(request.GET.get("ejercicio"), 1, 10**9)
    if ejercicio_id not in {e["ejercicio_id"] for e in ejercicios_registrados}:
        ejercicio_id = ejercicios_registrados[0]["ejercicio_id"] if ejercicios_registrados else None

    return {
        "seccion": "clientes", "cliente": cliente, "usuario_cliente": cliente.usuario,
        "asignacion": asignacion,
        "progreso_pct": round(asignacion.semana_actual * 100 / asignacion.rutina.semanas) if asignacion else 0,
        "variacion_12": variacion_peso(cliente, 84, hoy),
        "adherencia": pct, "sesiones_hechas": hechas, "sesiones_planeadas": planeadas,
        "texto_ultima": texto_ultima_sesion(ultima, hoy),
        "vol_semana": vol_semana,
        "vol_cambio": round((vol_semana - vol_anterior) * 100 / vol_anterior) if vol_anterior else None,
        "barras": barras_peso(cliente, hoy, semanas_grafico), "rango": str(semanas_grafico),
        "proxima": proxima_sesion(asignacion, sesiones, hoy),
        "ejercicios_registrados": ejercicios_registrados, "ejercicio_id": ejercicio_id,
        "historial": historial_cargas(cliente, ejercicio_id) if ejercicio_id else None,
        "hoy": hoy,
        **contexto_asignar(request.user, hoy),
    }


def cliente_de(request, pk):
    """El cliente solo se ve si es uno de mis clientes (404 si no)."""
    return get_object_or_404(mis_clientes(request.user.entrenador), pk=pk)


@solo_entrenadores
def cliente_detalle(request, pk):
    cliente = cliente_de(request, pk)
    return render(request, "entrenador/cliente.html", contexto_detalle(request, cliente, timezone.localdate()))


# =========================================================
# Asignar rutina (modal)
# =========================================================

@solo_entrenadores
@require_POST
def asignar_rutina(request, pk):
    hoy = timezone.localdate()
    # Se puede asignar a mis clientes o a cualquier cliente activo (así se suman clientes nuevos)
    cliente = get_object_or_404(Cliente.objects.select_related("usuario"), pk=pk, usuario__is_active=True)
    valores = {
        "rutina": request.POST.get("rutina", ""), "fecha_inicio": request.POST.get("fecha_inicio", "").strip(),
        "semana_inicio": request.POST.get("semana_inicio", "1"), "nota": request.POST.get("nota", "").strip(),
        "notificar": request.POST.get("notificar") == "on",
    }
    errores = {}
    rutina = rutinas_para_asignar(request.user).filter(pk=entero(valores["rutina"], 1, 10**9)).first()
    if not rutina:
        errores["rutina"] = ["Elige una de tus rutinas publicadas."]
    fecha = parse_date(valores["fecha_inicio"]) if valores["fecha_inicio"] else None
    if not fecha:
        errores["fecha_inicio"] = ["Escribe una fecha válida."]
    elif fecha < hoy - timedelta(days=30):
        errores["fecha_inicio"] = ["La fecha no puede ser de hace más de 30 días."]
    semana = entero(valores["semana_inicio"], 1, rutina.semanas if rutina else 24)
    if semana is None:
        errores["semana_inicio"] = ["Semana no válida para esta rutina."]
    if len(valores["nota"]) > 500:
        errores["nota"] = ["Máximo 500 caracteres."]

    if errores:
        contexto = contexto_detalle(request, mis_clientes(request.user.entrenador).filter(pk=cliente.pk).first()
                                    or cliente, hoy)
        contexto.update(contexto_asignar(request.user, hoy, valores, errores))
        contexto["modal_asignar_abierto"] = True
        return render(request, "entrenador/cliente.html", contexto, status=400)

    with transaction.atomic():
        anterior = cliente.rutina_actual
        # Reemplaza la asignación activa; el historial de cargas y peso se conserva
        cliente.asignaciones_rutina.filter(estado=EstadoAsignacion.ACTIVA).update(estado=EstadoAsignacion.CANCELADA)
        semanas_restantes = rutina.semanas - semana + 1
        AsignacionRutina.objects.create(
            cliente=cliente, entrenador=request.user.entrenador, rutina=rutina, fecha_inicio=fecha,
            fecha_fin=fecha + timedelta(weeks=semanas_restantes) - timedelta(days=1),
            semana_inicio=semana, nota=valores["nota"],
        )
        if valores["notificar"]:
            texto = (f"{request.user.get_full_name()} te asignó la rutina «{rutina.nombre}», "
                     f"desde el {fecha:%d/%m/%Y} (semana {semana}).")
            if valores["nota"]:
                texto += f" Nota: {valores['nota']}"
            Notificacion.objects.create(usuario=cliente.usuario, mensaje=texto[:500])

    nombre = cliente.usuario.first_name or cliente.usuario.email
    if anterior and anterior.rutina_id != rutina.id:
        messages.success(request, f"Se reemplazó «{anterior.rutina.nombre}» por «{rutina.nombre}» para {nombre}.")
    else:
        messages.success(request, f"Rutina «{rutina.nombre}» asignada a {nombre}.")
    return redirect("entrenador_cliente", pk=cliente.pk)


# =========================================================
# Registrar peso y editar cargas
# =========================================================

@solo_entrenadores
@require_POST
def registrar_peso(request, pk):
    cliente = cliente_de(request, pk)
    hoy = timezone.localdate()
    peso = decimal_o_none(request.POST.get("peso"), maximo=Decimal("400"))
    fecha = parse_date(request.POST.get("fecha", "")) or None
    errores = {}
    if not peso:
        errores["peso"] = ["Escribe un peso válido en kg (ej. 62,4)."]
    if not fecha or fecha > hoy:
        errores["fecha"] = ["La fecha no puede ser futura."]
    if errores:
        contexto = contexto_detalle(request, cliente, hoy)
        contexto.update({"errores_peso": errores, "valores_peso": request.POST, "modal_peso_abierto": True})
        return render(request, "entrenador/cliente.html", contexto, status=400)
    ProgresoFisico.objects.create(cliente=cliente, fecha=fecha, peso=peso)
    messages.success(request, f"Peso registrado: {numero_texto(peso)} kg.")
    return volver(request, "entrenador_cliente", pk=cliente.pk)


@solo_entrenadores
@require_POST
def editar_cargas(request, pk):
    """Cada serie llega como kg_<id> y reps_<id>. Las que cambian quedan 'Editado por entrenador'."""
    cliente = cliente_de(request, pk)
    ids = [entero(clave[3:], 1, 10**9) for clave in request.POST if clave.startswith("kg_")]
    registros = {r.id: r for r in cliente.progresos_ejercicio.filter(id__in=[i for i in ids if i])}
    errores, cambios = [], []
    for id_, registro in registros.items():
        kg = decimal_o_none(request.POST.get(f"kg_{id_}"), maximo=Decimal("1000"))
        reps = entero(request.POST.get(f"reps_{id_}"), 0, 999)
        if kg in (None, False) or reps is None:
            errores.append(f"{registro.fecha:%d/%m}: revisa kg y repeticiones.")
            continue
        if kg != registro.carga_kg or reps != registro.repeticiones_realizadas:
            registro.carga_kg, registro.repeticiones_realizadas = kg, reps
            registro.editado_por_entrenador = True
            cambios.append(registro)
    if errores:
        messages.error(request, "No se guardaron los cambios. " + " ".join(errores[:3]))
    elif cambios:
        with transaction.atomic():
            ProgresoEjercicio.objects.bulk_update(
                cambios, ["carga_kg", "repeticiones_realizadas", "editado_por_entrenador"])
        messages.success(request, f"Se actualizaron {len(cambios)} serie{'s' if len(cambios) != 1 else ''}.")
    else:
        messages.info(request, "No cambiaste ningún valor.")
    return volver(request, "entrenador_cliente", pk=cliente.pk)
