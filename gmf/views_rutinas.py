"""
Rutinas y ejercicios: pantallas compartidas por el ENTRENADOR y el CLIENTE.

Las rutinas son plantillas (autor = quien las crea) que se editan en borrador y se publican.
Solo el autor ve y edita las suyas. El entrenador las asigna a sus clientes (views_entrenador.py);
el cliente las usa para sí mismo.

- GET  /rutinas/                       Mis rutinas (filtros y búsqueda)
- POST /rutinas/                       crea una rutina (modal "Nueva rutina", paso 1 de 2)
- GET  /rutinas/<id>/                  constructor semana a semana (paso 2)
- POST /rutinas/<id>/guardar/          guarda todo el constructor (JSON, lo usa constructor.js)
- POST /rutinas/<id>/duplicar/         copia la rutina
- POST /rutinas/<id>/eliminar/         borra la rutina (solo si nunca se asignó)
- GET  /ejercicios/                    biblioteca de ejercicios (catálogo + personalizados)
- POST /ejercicios/nuevo/              crea un ejercicio personalizado (formulario o JSON)
"""
import json
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    EQUIPOS, GRUPOS_MUSCULARES, DiaRutina, Ejercicio, EstadoRutina, NivelRutina, RolUsuario,
    Rutina, RutinaEjercicio, SerieRutina, TipoEsfuerzo, TipoObjetivoEjercicio, TipoRepeticiones,
)

ROLES_CON_RUTINAS = [RolUsuario.ENTRENADOR, RolUsuario.CLIENTE]

OBJETIVOS = ["Hipertrofia", "Fuerza", "Definición", "Resistencia", "General"]
FILTROS_RUTINAS = [("", "Todas"), ("borradores", "Borradores"), ("publicadas", "Publicadas"),
                   ("guardadas", "Guardadas")]
MAX_NOMBRE_RUTINA = 50
MAX_NOMBRE_EJERCICIO = 50
MAX_SEMANAS = 24
MAX_DIAS = 7
MAX_SERIES = 20


# =========================================================
# Acceso y utilidades
# =========================================================

def con_rutinas(vista):
    """Entrenadores y clientes (los que crean rutinas)."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.rol not in ROLES_CON_RUTINAS:
            messages.error(request, "Esta sección es para entrenadores y clientes.")
            return redirect("inicio")
        return vista(request, *args, **kwargs)
    return envoltura


def es_json(request):
    return "application/json" in request.headers.get("Accept", "") or request.content_type == "application/json"


def entero(valor, minimo, maximo):
    """Texto -> int dentro del rango, o None si no es válido."""
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    return numero if minimo <= numero <= maximo else None


def decimal_o_none(valor, maximo=Decimal("9999")):
    """'47,5' -> Decimal('47.5'); vacío -> None; inválido -> False."""
    if valor in (None, ""):
        return None
    try:
        numero = Decimal(str(valor).replace(",", ".").strip())
    except InvalidOperation:
        return False
    if numero < 0 or numero > maximo or numero != numero.quantize(Decimal("0.01")):
        return False
    return numero


def numero_texto(valor):
    """Decimal -> texto sin ceros de sobra (47.50 -> "47.5")."""
    if valor is None:
        return ""
    texto = f"{valor:f}"
    return texto.rstrip("0").rstrip(".") if "." in texto else texto


def ejercicios_visibles(usuario):
    """Catálogo activo del gimnasio + los personalizados activos del usuario."""
    return Ejercicio.objects.filter(activo=True).filter(Q(autor__isnull=True) | Q(autor=usuario))


def datos_ejercicio(ej, usos=0):
    return {"id": ej.id, "nombre": ej.nombre, "equipo": ej.maquina, "musculos": ej.lista_musculos,
            "tipo": ej.tipo_objetivo, "usos": usos, "propio": ej.autor_id is not None}


def base_de(usuario):
    """Plantilla base según el rol (el cliente aún no tiene panel propio)."""
    return "entrenador/base_entrenador.html"


# =========================================================
# Mis rutinas + modal "Nueva rutina"
# =========================================================

def validar_nueva_rutina(post):
    valores = {
        "nombre": post.get("nombre", "").strip(),
        "semanas": post.get("semanas", "").strip(),
        "dias_por_semana": post.get("dias_por_semana", "4").strip(),
        "objetivo": post.get("objetivo", "").strip(),
        "nivel": post.get("nivel", "").strip(),
        "descripcion": post.get("descripcion", "").strip(),
    }
    errores = {}
    if not valores["nombre"]:
        errores["nombre"] = ["Escribe el nombre de la rutina."]
    elif len(valores["nombre"]) > MAX_NOMBRE_RUTINA:
        errores["nombre"] = [f"Máximo {MAX_NOMBRE_RUTINA} caracteres."]
    if entero(valores["semanas"], 1, MAX_SEMANAS) is None:
        errores["semanas"] = [f"Elige una duración entre 1 y {MAX_SEMANAS} semanas."]
    if entero(valores["dias_por_semana"], 1, MAX_DIAS) is None:
        errores["dias_por_semana"] = ["Elige entre 1 y 7 días."]
    if valores["objetivo"] and valores["objetivo"] not in OBJETIVOS:
        errores["objetivo"] = ["Objetivo no válido."]
    if valores["nivel"] and valores["nivel"] not in NivelRutina.values:
        errores["nivel"] = ["Nivel no válido."]
    if len(valores["descripcion"]) > 1000:
        errores["descripcion"] = ["Máximo 1000 caracteres."]
    return valores, errores


@con_rutinas
def rutinas(request):
    usuario = request.user
    valores, errores = {"dias_por_semana": "4"}, {}

    if request.method == "POST":
        valores, errores = validar_nueva_rutina(request.POST)
        if not errores:
            with transaction.atomic():
                rutina = Rutina.objects.create(
                    nombre=valores["nombre"], semanas=int(valores["semanas"]),
                    dias_por_semana=int(valores["dias_por_semana"]), objetivo=valores["objetivo"],
                    nivel=valores["nivel"], descripcion=valores["descripcion"], autor=usuario,
                    estado=EstadoRutina.BORRADOR,
                )
                rutina.crear_dias()
            return redirect("rutina_constructor", pk=rutina.pk)

    propias = Rutina.objects.filter(autor=usuario)
    guardadas_q = Q(copia_de__isnull=False) & ~Q(copia_de__autor=usuario)
    total_guardadas = propias.filter(guardadas_q).count()
    total_propias = propias.count() - total_guardadas

    filtro = request.GET.get("filtro", "")
    consulta = propias
    if filtro == "borradores":
        consulta = consulta.filter(estado=EstadoRutina.BORRADOR)
    elif filtro == "publicadas":
        consulta = consulta.filter(estado=EstadoRutina.PUBLICADA)
    elif filtro == "guardadas":
        consulta = consulta.filter(guardadas_q)
    texto = request.GET.get("q", "").strip()
    if texto:
        consulta = consulta.filter(nombre__icontains=texto)
    consulta = consulta.annotate(num_ejercicios=Count("detalle"),
                                 num_asignaciones=Count("asignaciones", distinct=True))

    contexto = {
        "plantilla_base": base_de(usuario), "seccion": "rutinas",
        "rutinas": consulta.order_by("-fecha_actualizacion", "-id"),
        "total_propias": total_propias, "total_guardadas": total_guardadas,
        "filtros": FILTROS_RUTINAS, "filtro": filtro, "q": texto,
        "objetivos": OBJETIVOS, "niveles": NivelRutina.choices,
        "opciones_semanas": range(1, MAX_SEMANAS + 1), "opciones_dias": range(1, MAX_DIAS + 1),
        "valores": valores, "errores": errores, "modal_abierto": bool(errores),
    }
    return render(request, "rutinas/rutinas.html", contexto, status=400 if errores else 200)


@con_rutinas
@require_POST
def rutina_duplicar(request, pk):
    rutina = get_object_or_404(Rutina, pk=pk, autor=request.user)
    with transaction.atomic():
        copia = rutina.duplicar(request.user)
    messages.success(request, f"Se creó «{copia.nombre}». Ya puedes editarla.")
    return redirect("rutina_constructor", pk=copia.pk)


@con_rutinas
@require_POST
def rutina_eliminar(request, pk):
    rutina = get_object_or_404(Rutina, pk=pk, autor=request.user)
    if rutina.asignaciones.exists():
        # Las asignaciones guardan el historial del cliente: esa rutina no se puede borrar
        messages.error(request, f"«{rutina.nombre}» ya se asignó a clientes y no se puede eliminar.")
    else:
        nombre = rutina.nombre
        rutina.delete()
        messages.success(request, f"Se eliminó «{nombre}».")
    return redirect("rutinas")


# =========================================================
# Constructor semana a semana
# =========================================================

def estado_constructor(rutina):
    """La rutina completa como diccionario para constructor.js."""
    semanas = {n: {"numero": n, "dias": {}} for n in range(1, rutina.semanas + 1)}
    for dia in rutina.dias.all():
        semana = semanas.setdefault(dia.semana, {"numero": dia.semana, "dias": {}})
        semana["dias"][dia.dia] = {"nombre": dia.nombre, "ejercicios": []}
    detalle = rutina.detalle.select_related("ejercicio").prefetch_related("series_detalle")
    for re in detalle:
        semana = semanas.setdefault(re.semana, {"numero": re.semana, "dias": {}})
        dia = semana["dias"].setdefault(re.dia, {"nombre": "", "ejercicios": []})
        series = [{"min": s.repeticiones_min, "max": s.repeticiones_max,
                   "kg": numero_texto(s.carga_kg), "descanso": s.descanso_segundos}
                  for s in re.series_detalle.all()]
        if not series:  # rutina antigua sin series detalladas
            series = [{"min": re.repeticiones_min, "max": re.repeticiones_max, "kg": "",
                       "descanso": re.descanso_segundos} for _ in range(re.series)]
        dia["ejercicios"].append({
            "ejercicio": re.ejercicio_id, "tipo_repeticiones": re.tipo_repeticiones,
            "tipo_esfuerzo": re.tipo_esfuerzo, "valor_esfuerzo": re.valor_esfuerzo, "series": series,
        })
    return {
        "id": rutina.id, "nombre": rutina.nombre, "estado": rutina.estado,
        "objetivo": rutina.objetivo,
        "semanas": [
            {"numero": s["numero"],
             "dias": [s["dias"][d] for d in sorted(s["dias"])]}
            for s in (semanas[n] for n in sorted(semanas))
        ],
    }


def catalogo_para(usuario, rutina):
    """Ejercicios que se pueden elegir (+ los que ya usa la rutina aunque estén inactivos)."""
    ids_usados = set(rutina.detalle.values_list("ejercicio_id", flat=True))
    consulta = Ejercicio.objects.filter(
        Q(activo=True, autor__isnull=True) | Q(activo=True, autor=usuario) | Q(id__in=ids_usados)
    ).annotate(usos=Count("rutinaejercicio"))
    catalogo = []
    for ej in consulta:
        dato = datos_ejercicio(ej, ej.usos)
        dato["elegible"] = ej.activo and (ej.autor_id in (None, usuario.id))
        catalogo.append(dato)
    return catalogo


@con_rutinas
def rutina_constructor(request, pk):
    rutina = get_object_or_404(Rutina, pk=pk, autor=request.user)  # solo el autor (404 si no)
    contexto = {
        "plantilla_base": base_de(request.user), "seccion": "rutinas",
        "rutina": rutina,
        "estado_rutina": estado_constructor(rutina),
        "catalogo": catalogo_para(request.user, rutina),
        "max_semanas": MAX_SEMANAS, "max_dias": MAX_DIAS, "max_series": MAX_SERIES,
        **contexto_modal_ejercicio(),
    }
    return render(request, "rutinas/constructor.html", contexto)


def validar_ejercicio_de_dia(item, permitidos, catalogo_tipos, donde):
    """Valida un ejercicio del constructor. Devuelve (datos, lista_de_errores)."""
    errores = []
    ej_id = entero(item.get("ejercicio"), 1, 10**9)
    if ej_id is None or ej_id not in permitidos:
        return None, [f"{donde}: el ejercicio no existe o no está disponible."]
    tipo = item.get("tipo_repeticiones") or TipoRepeticiones.RANGO
    if tipo not in TipoRepeticiones.values:
        errores.append(f"{donde}: tipo de repeticiones no válido.")
    esfuerzo = item.get("tipo_esfuerzo") or TipoEsfuerzo.RIR
    valor_esfuerzo = None
    if esfuerzo not in TipoEsfuerzo.values:
        errores.append(f"{donde}: tipo de esfuerzo no válido.")
    elif esfuerzo == TipoEsfuerzo.RIR:
        valor_esfuerzo = entero(item.get("valor_esfuerzo"), 0, 10)
        if valor_esfuerzo is None:
            errores.append(f"{donde}: el RIR va de 0 a 10.")
    series = item.get("series") or []
    if not isinstance(series, list) or not 1 <= len(series) <= MAX_SERIES:
        return None, errores + [f"{donde}: necesita entre 1 y {MAX_SERIES} series."]
    limpias = []
    for n, serie in enumerate(series, start=1):
        if not isinstance(serie, dict):
            errores.append(f"{donde}, serie {n}: datos no válidos.")
            continue
        mi = ma = None
        if tipo == TipoRepeticiones.RANGO:
            mi, ma = entero(serie.get("min"), 1, 999), entero(serie.get("max"), 1, 999)
            if mi is None or ma is None:
                errores.append(f"{donde}, serie {n}: escribe el rango (mínimo y máximo).")
            elif mi > ma:
                errores.append(f"{donde}, serie {n}: el máximo debe ser mayor o igual al mínimo.")
        elif tipo == TipoRepeticiones.MAXIMAS:
            mi = entero(serie.get("min"), 1, 999 if catalogo_tipos[ej_id] != "TIEMPO" else 3600)
            if mi is None:
                unidad = "los segundos" if catalogo_tipos[ej_id] == "TIEMPO" else "las repeticiones"
                errores.append(f"{donde}, serie {n}: escribe {unidad}.")
        kg = decimal_o_none(serie.get("kg"))
        if kg is False:
            errores.append(f"{donde}, serie {n}: carga no válida (kg, hasta 2 decimales).")
        descanso = serie.get("descanso")
        if descanso in (None, ""):
            descanso = None
        else:
            descanso = entero(descanso, 0, 3600)
            if descanso is None:
                errores.append(f"{donde}, serie {n}: el descanso va de 0 a 3600 segundos.")
        limpias.append({"min": mi, "max": ma, "kg": kg or None, "descanso": descanso})
    return {"ejercicio": ej_id, "tipo": tipo, "esfuerzo": esfuerzo,
            "valor_esfuerzo": valor_esfuerzo, "series": limpias}, errores


@con_rutinas
@require_POST
def rutina_guardar(request, pk):
    """Recibe el constructor completo (JSON) y reemplaza días, ejercicios y series."""
    rutina = get_object_or_404(Rutina, pk=pk, autor=request.user)
    try:
        datos = json.loads(request.body or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "errores": ["Datos no válidos."]}, status=400)

    errores = []
    accion = datos.get("accion", "guardar")
    if accion not in ("guardar", "borrador", "publicar"):
        errores.append("Acción no válida.")
    nombre = str(datos.get("nombre", rutina.nombre)).strip()
    if not nombre:
        errores.append("La rutina necesita un nombre.")
    elif len(nombre) > MAX_NOMBRE_RUTINA:
        errores.append(f"El nombre admite máximo {MAX_NOMBRE_RUTINA} caracteres.")

    semanas = datos.get("semanas")
    if not isinstance(semanas, list) or not 1 <= len(semanas) <= MAX_SEMANAS:
        return JsonResponse({"ok": False, "errores": [f"La rutina debe tener entre 1 y {MAX_SEMANAS} semanas."]},
                            status=400)

    permitidos = {e["id"]: e for e in catalogo_para(request.user, rutina)}
    # Un ejercicio inactivo solo se acepta si ya estaba en la rutina
    tipos = {i: e["tipo"] for i, e in permitidos.items()}
    nombres = {i: e["nombre"] for i, e in permitidos.items()}

    limpias, total_ejercicios = [], 0
    for ns, semana in enumerate(semanas, start=1):
        dias = semana.get("dias") if isinstance(semana, dict) else None
        if not isinstance(dias, list) or not 1 <= len(dias) <= MAX_DIAS:
            errores.append(f"Semana {ns}: debe tener entre 1 y {MAX_DIAS} días.")
            continue
        dias_limpios = []
        for nd, dia in enumerate(dias, start=1):
            dia = dia if isinstance(dia, dict) else {}
            nombre_dia = str(dia.get("nombre", "")).strip()
            if len(nombre_dia) > 60:
                errores.append(f"Semana {ns} · Día {nd}: el nombre admite máximo 60 caracteres.")
            ejercicios = []
            for item in dia.get("ejercicios") or []:
                item = item if isinstance(item, dict) else {}
                ej_id = entero(item.get("ejercicio"), 1, 10**9)
                donde = f"Semana {ns} · Día {nd} · {nombres.get(ej_id, 'ejercicio')}"
                limpio, errs = validar_ejercicio_de_dia(item, permitidos, tipos, donde)
                errores.extend(errs)
                if limpio:
                    ejercicios.append(limpio)
            total_ejercicios += len(ejercicios)
            dias_limpios.append({"nombre": nombre_dia[:60], "ejercicios": ejercicios})
        limpias.append(dias_limpios)

    if accion == "publicar" and total_ejercicios == 0 and not errores:
        errores.append("Agrega al menos un ejercicio antes de publicar la rutina.")
    if errores:
        return JsonResponse({"ok": False, "errores": errores[:8]}, status=400)

    with transaction.atomic():
        rutina.nombre = nombre
        rutina.semanas = len(limpias)
        rutina.dias_por_semana = max(len(d) for d in limpias)
        if accion == "publicar":
            rutina.estado = EstadoRutina.PUBLICADA
        elif accion == "borrador":
            rutina.estado = EstadoRutina.BORRADOR
        rutina.save()
        rutina.dias.all().delete()
        rutina.detalle.all().delete()  # las series se borran en cascada
        DiaRutina.objects.bulk_create([
            DiaRutina(rutina=rutina, semana=ns, dia=nd, nombre=dia["nombre"])
            for ns, dias in enumerate(limpias, start=1) for nd, dia in enumerate(dias, start=1)
        ])
        for ns, dias in enumerate(limpias, start=1):
            for nd, dia in enumerate(dias, start=1):
                for orden, item in enumerate(dia["ejercicios"], start=1):
                    primera = item["series"][0]
                    re = RutinaEjercicio.objects.create(
                        rutina=rutina, ejercicio_id=item["ejercicio"], semana=ns, dia=nd, orden=orden,
                        series=len(item["series"]), tipo_repeticiones=item["tipo"],
                        repeticiones_min=primera["min"], repeticiones_max=primera["max"],
                        tipo_esfuerzo=item["esfuerzo"], valor_esfuerzo=item["valor_esfuerzo"],
                        descanso_segundos=primera["descanso"],
                    )
                    SerieRutina.objects.bulk_create([
                        SerieRutina(rutina_ejercicio=re, numero=n, repeticiones_min=s["min"],
                                    repeticiones_max=s["max"], carga_kg=s["kg"], descanso_segundos=s["descanso"])
                        for n, s in enumerate(item["series"], start=1)
                    ])

    hora = timezone.localtime(rutina.fecha_actualizacion)
    return JsonResponse({"ok": True, "estado": rutina.estado, "nombre": rutina.nombre,
                         "guardado": hora.strftime("%H:%M")})


# =========================================================
# Biblioteca de ejercicios + "Crear ejercicio nuevo"
# =========================================================

def contexto_modal_ejercicio():
    return {"equipos": EQUIPOS, "grupos_musculares": GRUPOS_MUSCULARES,
            "tipos_objetivo": TipoObjetivoEjercicio.choices, "max_nombre_ejercicio": MAX_NOMBRE_EJERCICIO}


def validar_ejercicio_nuevo(post, usuario):
    valores = {
        "nombre": post.get("nombre", "").strip(),
        "tipo_objetivo": post.get("tipo_objetivo", "").strip(),
        "equipo": post.get("equipo", "").strip(),
        "musculos": [m for m in post.getlist("musculos") if m],
        "video_url": post.get("video_url", "").strip(),
    }
    errores = {}
    if not valores["nombre"]:
        errores["nombre"] = ["Escribe el nombre del ejercicio."]
    elif len(valores["nombre"]) > MAX_NOMBRE_EJERCICIO:
        errores["nombre"] = [f"Máximo {MAX_NOMBRE_EJERCICIO} caracteres."]
    elif ejercicios_visibles(usuario).filter(nombre__iexact=valores["nombre"]).exists():
        errores["nombre"] = ["Ya tienes un ejercicio con ese nombre en la biblioteca."]
    if valores["tipo_objetivo"] not in TipoObjetivoEjercicio.values:
        errores["tipo_objetivo"] = ["Elige Reps o Tiempo."]
    if valores["equipo"] not in EQUIPOS:
        errores["equipo"] = ["Elige el equipo."]
    if not valores["musculos"]:
        errores["musculos"] = ["Elige al menos un grupo muscular."]
    elif any(m not in GRUPOS_MUSCULARES for m in valores["musculos"]):
        errores["musculos"] = ["Grupo muscular no válido."]
    if valores["video_url"]:
        try:
            URLValidator(schemes=["http", "https"])(valores["video_url"])
        except ValidationError:
            errores["video_url"] = ["Escribe un enlace válido (https://...)."]
        else:
            if not any(d in valores["video_url"] for d in ("youtube.com/", "youtu.be/")):
                errores["video_url"] = ["El enlace debe ser de YouTube."]
    return valores, errores


@con_rutinas
def ejercicios(request):
    usuario = request.user
    consulta = ejercicios_visibles(usuario).annotate(usos=Count("rutinaejercicio"))
    texto = request.GET.get("q", "").strip()
    for palabra in texto.split():
        consulta = consulta.filter(Q(nombre__icontains=palabra) | Q(musculo__icontains=palabra))
    equipo = request.GET.get("equipo", "")
    if equipo in EQUIPOS:
        consulta = consulta.filter(maquina=equipo)
    if request.GET.get("propios") == "1":
        consulta = consulta.filter(autor=usuario)
    contexto = {
        "plantilla_base": base_de(usuario), "seccion": "ejercicios",
        "ejercicios": consulta.order_by("-usos", "nombre"), "q": texto, "equipo": equipo,
        "propios": request.GET.get("propios") == "1",
        "total_propios": Ejercicio.objects.filter(autor=usuario, activo=True).count(),
        **contexto_modal_ejercicio(),
    }
    return render(request, "rutinas/ejercicios.html", contexto)


@con_rutinas
@require_POST
def ejercicio_nuevo(request):
    valores, errores = validar_ejercicio_nuevo(request.POST, request.user)
    if errores:
        if es_json(request):
            return JsonResponse({"ok": False, "errores": errores}, status=400)
        contexto = {
            "plantilla_base": base_de(request.user), "seccion": "ejercicios",
            "ejercicios": ejercicios_visibles(request.user).annotate(usos=Count("rutinaejercicio"))
                                                          .order_by("-usos", "nombre"),
            "total_propios": Ejercicio.objects.filter(autor=request.user, activo=True).count(),
            "valores_ejercicio": valores, "errores_ejercicio": errores, "modal_ejercicio_abierto": True,
            **contexto_modal_ejercicio(),
        }
        return render(request, "rutinas/ejercicios.html", contexto, status=400)

    ejercicio = Ejercicio.objects.create(
        nombre=valores["nombre"], tipo_objetivo=valores["tipo_objetivo"], maquina=valores["equipo"],
        musculo=", ".join(valores["musculos"]), video_url=valores["video_url"], autor=request.user,
    )
    if es_json(request):
        dato = datos_ejercicio(ejercicio)
        dato["elegible"] = True
        return JsonResponse({"ok": True, "ejercicio": dato})
    messages.success(request, f"Ejercicio «{ejercicio.nombre}» creado en tu biblioteca.")
    return redirect("ejercicios")
