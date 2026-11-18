from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import (
    Cliente, Entrenador, Membresia, Nutricionista, RolUsuario, Sede, Usuario,
)

DATOS_REGISTRO = {
    "first_name": "Ana",
    "last_name": "Pérez",
    "email": "Ana@Correo.com",
    "password1": "Gimnasio#2026",
    "password2": "Gimnasio#2026",
}


class InicioTests(TestCase):
    def test_premium_mensual_creado_por_la_migracion(self):
        plan = Membresia.objects.get(tipo="PREMIUM", duracion="MENSUAL")
        self.assertEqual(plan.precio, Decimal("89000"))
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "$89.000")
        self.assertContains(r, "Se paga mensualmente")

    def test_inicio_sin_datos_muestra_estados_vacios(self):
        Membresia.objects.all().delete()
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Muy pronto conocerás a nuestro equipo")
        self.assertContains(r, "Pronto publicaremos nuestras sedes")
        self.assertContains(r, "Estamos preparando los precios")
        self.assertContains(r, reverse("ingresar"))
        self.assertContains(r, reverse("registro"))

    def test_inicio_con_datos(self):
        Membresia.objects.create(tipo="PREMIUM", duracion="ANUAL", precio=Decimal("890000"), activa=False)
        Sede.objects.create(nombre="Sede Centro", direccion="Cra 50 #45-10", ciudad="Medellín",
                            telefono="3001234567", correo="centro@gmf.co")
        Sede.objects.create(nombre="Sede Cerrada", direccion="x", ciudad="x", telefono="1", activa=False)
        u = Usuario.objects.create_user("e@gmf.co", "x", first_name="Carlos",
                                        last_name="Restrepo", rol=RolUsuario.ENTRENADOR)
        Entrenador.objects.create(usuario=u, especialidad="Fuerza")
        inactivo = Usuario.objects.create_user("n@gmf.co", "x", first_name="Oculto",
                                               last_name="N", rol=RolUsuario.NUTRICIONISTA, is_active=False)
        Nutricionista.objects.create(usuario=inactivo, especialidad="x")

        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "$89.000")
        self.assertNotContains(r, "$890.000")      # membresía inactiva
        self.assertContains(r, "Sede Centro")
        self.assertNotContains(r, "Sede Cerrada")  # sede inactiva
        self.assertContains(r, "Carlos Restrepo")
        self.assertContains(r, ">CR<")
        self.assertNotContains(r, "Oculto")        # profesional inactivo


class RegistroTests(TestCase):
    def test_registro_crea_usuario_cliente_y_entra(self):
        r = self.client.post(reverse("registro"), DATOS_REGISTRO, follow=True)
        self.assertRedirects(r, reverse("inicio"))
        u = Usuario.objects.get(email="ana@correo.com")
        self.assertEqual(u.rol, RolUsuario.CLIENTE)
        self.assertEqual(Cliente.objects.get(usuario=u).sexo, "")  # se completa después
        self.assertTrue(r.context["user"].is_authenticated)
        self.assertContains(r, "Bienvenido a GMFitness, Ana")
        self.assertContains(r, "Tu plan actual")

    def test_registro_errores(self):
        Usuario.objects.create_user("ana@correo.com", "x")
        datos = dict(DATOS_REGISTRO, password2="otra", first_name="")
        r = self.client.post(reverse("registro"), datos)
        self.assertEqual(r.status_code, 200)
        errores = r.context["errores"]
        for campo in ("email", "password2", "first_name"):
            self.assertIn(campo, errores)
        self.assertContains(r, "Ya existe una cuenta con este correo.")
        self.assertEqual(Cliente.objects.count(), 0)

    def test_registro_no_pide_identidad_ni_sexo(self):
        r = self.client.get(reverse("registro"))
        self.assertNotContains(r, 'name="numero_identidad"')
        self.assertNotContains(r, 'name="sexo"')

    def test_clave_debil(self):
        datos = dict(DATOS_REGISTRO, password1="123", password2="123")
        r = self.client.post(reverse("registro"), datos)
        self.assertIn("password2", r.context["errores"])

    def test_usuario_con_sesion_no_ve_registro(self):
        self.client.post(reverse("registro"), DATOS_REGISTRO)
        r = self.client.get(reverse("registro"))
        self.assertRedirects(r, reverse("inicio"))


class IngresoTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user("ana@correo.com", "Gimnasio#2026",
                                                   first_name="Ana", last_name="Pérez")

    def test_ingresar_y_salir(self):
        r = self.client.post(reverse("ingresar"),
                             {"email": "ana@correo.com", "password": "Gimnasio#2026"}, follow=True)
        self.assertRedirects(r, reverse("inicio"))
        self.assertContains(r, "Hola de nuevo, Ana")
        self.assertContains(r, ">AP<")
        r = self.client.post(reverse("salir"), follow=True)
        self.assertRedirects(r, reverse("inicio"))
        self.assertFalse(r.context["user"].is_authenticated)
        self.assertContains(r, "Cerraste sesión.")

    def test_ingresar_mal(self):
        r = self.client.post(reverse("ingresar"), {"email": "ana@correo.com", "password": "mala"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "El correo o la contraseña no son correctos.")

    def test_salir_por_get_no_esta_permitido(self):
        self.client.login(email="ana@correo.com", password="Gimnasio#2026")
        r = self.client.get(reverse("salir"))
        self.assertEqual(r.status_code, 405)


# =========================================================
# Panel de administración
# =========================================================
from .models import Alimento, Ejercicio, Suscripcion  # noqa: E402


class PanelBase(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            "admin@gmf.co", "Clave#2026", first_name="Daniel", last_name="Martínez",
            rol=RolUsuario.ADMINISTRADOR, is_staff=True, is_superuser=True,
        )
        self.client.login(email="admin@gmf.co", password="Clave#2026")

    def crear_cliente(self, correo="cli@gmf.co", nombre="Ana"):
        u = Usuario.objects.create_user(correo, "x", first_name=nombre, last_name="Pérez")
        Cliente.objects.create(usuario=u)
        return u


class PanelAccesoTests(TestCase):
    def test_anonimo_va_a_ingresar(self):
        r = self.client.get(reverse("panel"))
        self.assertRedirects(r, reverse("ingresar") + "?next=" + reverse("panel"))

    def test_cliente_no_entra(self):
        Usuario.objects.create_user("c@gmf.co", "Clave#2026", first_name="C", last_name="C")
        self.client.login(email="c@gmf.co", password="Clave#2026")
        for nombre in ("panel", "panel_empleados", "panel_clientes", "panel_sedes",
                       "panel_membresias", "panel_ejercicios", "panel_alimentos"):
            r = self.client.get(reverse(nombre))
            self.assertRedirects(r, reverse("inicio"), msg_prefix=nombre)

    def test_admin_entra_a_todas_y_va_al_panel_al_ingresar(self):
        Usuario.objects.create_user("a@gmf.co", "Clave#2026", first_name="A", last_name="A",
                                    rol=RolUsuario.ADMINISTRADOR)
        r = self.client.post(reverse("ingresar"), {"email": "a@gmf.co", "password": "Clave#2026"})
        self.assertRedirects(r, reverse("panel"))
        for nombre in ("panel", "panel_empleados", "panel_clientes", "panel_sedes",
                       "panel_membresias", "panel_ejercicios", "panel_alimentos"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)
        self.assertContains(self.client.get(reverse("inicio")), 'id="btn-ir-panel"')


class PanelEmpleadosTests(PanelBase):
    def test_crear_entrenador_con_clave_temporal(self):
        sede = Sede.objects.create(nombre="Centro", direccion="x", ciudad="Medellín", telefono="1")
        r = self.client.post(reverse("panel_empleados"), {
            "first_name": "Carlos", "last_name": "Ríos", "email": "Carlos@GMF.co", "telefono": "300",
            "sede": sede.pk, "rol": "ENTRENADOR", "especialidad": "Fuerza", "tarjeta_profesional": "",
        }, follow=True)
        u = Usuario.objects.get(email="carlos@gmf.co")
        self.assertEqual(u.rol, RolUsuario.ENTRENADOR)
        self.assertEqual(u.entrenador.especialidad, "Fuerza")
        clave = r.context["clave_temporal"]["clave"]
        self.assertTrue(u.check_password(clave))
        self.assertContains(r, clave)
        # Se muestra una sola vez
        self.assertNotContains(self.client.get(reverse("panel_empleados")), clave)

    def test_crear_admin_y_recepcionista(self):
        for rol, correo in (("ADMINISTRADOR", "ad@gmf.co"), ("RECEPCIONISTA", "re@gmf.co")):
            self.client.post(reverse("panel_empleados"), {
                "first_name": "X", "last_name": "Y", "email": correo, "rol": rol})
        self.assertTrue(Usuario.objects.get(email="ad@gmf.co").is_superuser)
        self.assertFalse(Usuario.objects.get(email="re@gmf.co").is_staff)

    def test_errores_reabren_modal(self):
        r = self.client.post(reverse("panel_empleados"), {
            "first_name": "", "last_name": "Y", "email": "admin@gmf.co", "rol": "NUTRICIONISTA"})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.context["modal_abierto"])
        for campo in ("first_name", "email", "especialidad"):
            self.assertIn(campo, r.context["errores"])
        self.assertContains(r, "Daniel Martínez", status_code=400)  # la tabla de fondo sigue llena

    def test_editar_no_cambia_rol(self):
        u = Usuario.objects.create_user("n@gmf.co", "x", first_name="N", last_name="U",
                                        rol=RolUsuario.NUTRICIONISTA)
        Nutricionista.objects.create(usuario=u, especialidad="Vieja")
        self.client.post(reverse("panel_empleados"), {
            "id": u.pk, "first_name": "Nora", "last_name": "U", "email": "n@gmf.co",
            "rol": "ADMINISTRADOR", "especialidad": "Deportiva"})
        u.refresh_from_db()
        self.assertEqual((u.first_name, u.rol, u.nutricionista.especialidad),
                         ("Nora", RolUsuario.NUTRICIONISTA, "Deportiva"))

    def test_desactivar_activar_y_no_a_si_mismo(self):
        u = Usuario.objects.create_user("r@gmf.co", "x", first_name="R", last_name="E",
                                        rol=RolUsuario.RECEPCIONISTA)
        url = reverse("panel_estado", args=["empleados", u.pk])
        self.client.post(url)
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.client.post(url, {"activar": "1"})
        u.refresh_from_db()
        self.assertTrue(u.is_active)
        self.client.post(reverse("panel_estado", args=["empleados", self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_filtros_y_busqueda(self):
        Usuario.objects.create_user("e@gmf.co", "x", first_name="Elena", last_name="Z",
                                    rol=RolUsuario.ENTRENADOR)
        r = self.client.get(reverse("panel_empleados"), {"rol": "ENTRENADOR"})
        self.assertContains(r, "Elena")
        self.assertNotContains(r, "admin@gmf.co")
        r = self.client.get(reverse("panel_empleados"), {"q": "dani mart"})
        self.assertContains(r, "admin@gmf.co")
        self.assertNotContains(r, "Elena")


class PanelClientesTests(PanelBase):
    def test_crear_editar_y_plan(self):
        r = self.client.post(reverse("panel_clientes"), {
            "first_name": "Luis", "last_name": "G", "email": "luis@gmf.co", "sexo": "M"}, follow=True)
        u = Usuario.objects.get(email="luis@gmf.co")
        self.assertEqual((u.rol, u.cliente.sexo), (RolUsuario.CLIENTE, "M"))
        self.assertIsNotNone(r.context["clave_temporal"])
        self.client.post(reverse("panel_clientes"), {
            "id": u.pk, "first_name": "Luis", "last_name": "Gómez", "email": "luis@gmf.co", "sexo": ""})
        u.refresh_from_db()
        self.assertEqual((u.last_name, u.cliente.sexo), ("Gómez", ""))
        # Plan: Premium solo con suscripción vigente
        Suscripcion.objects.create(cliente=u.cliente, membresia=Membresia.objects.first())
        self.assertContains(self.client.get(reverse("panel_clientes"), {"plan": "premium"}), "luis@gmf.co")
        self.assertNotContains(self.client.get(reverse("panel_clientes"), {"plan": "gratis"}), "luis@gmf.co")

    def test_nueva_clave(self):
        u = self.crear_cliente()
        r = self.client.post(reverse("panel_nueva_clave", args=[u.pk]),
                             {"volver": reverse("panel_clientes")}, follow=True)
        u.refresh_from_db()
        self.assertTrue(u.check_password(r.context["clave_temporal"]["clave"]))


class PanelCatalogosTests(PanelBase):
    def test_sede(self):
        r = self.client.post(reverse("panel_sedes"), {
            "nombre": "Norte", "ciudad": "Bello", "direccion": "Cll 1", "telefono": "300",
            "capacidad": "120", "activa": "on"})
        self.assertRedirects(r, reverse("panel_sedes"))
        sede = Sede.objects.get(nombre="Norte")
        self.assertEqual(sede.capacidad, 120)
        r = self.client.post(reverse("panel_sedes"), {"nombre": "", "capacidad": "-3", "correo": "malo"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.context["errores"]) >= {"nombre", "capacidad", "correo"}, True)
        self.client.post(reverse("panel_estado", args=["sedes", sede.pk]))
        sede.refresh_from_db()
        self.assertFalse(sede.activa)

    def test_membresia_no_duplica_activa(self):
        r = self.client.post(reverse("panel_membresias"), {
            "tipo": "PREMIUM", "duracion": "MENSUAL", "precio": "95000", "activa": "on"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("duracion", r.context["errores"])
        self.client.post(reverse("panel_membresias"), {
            "tipo": "PREMIUM", "duracion": "ANUAL", "precio": "890.000,00".replace(".", ""), "activa": "on"})
        anual = Membresia.objects.get(duracion="ANUAL")
        self.assertEqual(anual.precio, Decimal("890000.00"))
        self.assertContains(self.client.get(reverse("inicio")), "$890.000")

    def test_ejercicio_y_alimento(self):
        self.client.post(reverse("panel_ejercicios"), {
            "nombre": "Sentadilla", "musculo": "Pierna", "maquina": "Barra", "activo": "on"})
        ej = Ejercicio.objects.get(nombre="Sentadilla")
        self.client.post(reverse("panel_estado", args=["ejercicios", ej.pk]))
        ej.refresh_from_db()
        self.assertFalse(ej.activo)

        self.client.post(reverse("panel_alimentos"), {
            "nombre": "Arroz", "categoria": "Cereales", "kcal": "130", "proteinas": "2,7",
            "carbohidratos": "28", "grasas": "0.3", "porcion_gramos": "150", "codigo_barras": "",
            "activo": "on"})
        al = Alimento.objects.get(nombre="Arroz")
        self.assertEqual((al.proteinas, al.codigo_barras), (Decimal("2.7"), None))
        r = self.client.post(reverse("panel_alimentos"), {
            "id": al.pk, "nombre": "Arroz", "kcal": "abc", "proteinas": "200",
            "carbohidratos": "28", "grasas": "0", "porcion_gramos": "0"})
        self.assertEqual(set(r.context["errores"]), {"kcal", "proteinas", "porcion_gramos"})

    def test_volver_no_sale_del_sitio(self):
        s = Sede.objects.create(nombre="S", direccion="x", ciudad="x", telefono="1")
        r = self.client.post(reverse("panel_estado", args=["sedes", s.pk]), {"volver": "https://malo.com/"})
        self.assertRedirects(r, reverse("panel_sedes"))


# =========================================================
# Panel del entrenador, rutinas, ejercicios y mensajes
# =========================================================
import json
from datetime import timedelta

from django.utils import timezone

from .models import (
    AsignacionRutina, DiaRutina, Ejercicio, EstadoAsignacion, EstadoRutina, Mensaje, Notificacion,
    ProgresoEjercicio, ProgresoFisico, Rutina, SerieRutina,
)


def crear_entrenador(email="ent@gmf.co", nombre="Carlos"):
    u = Usuario.objects.create_user(email, "x", first_name=nombre, last_name="Méndez", rol=RolUsuario.ENTRENADOR)
    Entrenador.objects.create(usuario=u, especialidad="Fuerza")
    return u


def crear_cliente(email="laura@gmf.co", nombre="Laura"):
    u = Usuario.objects.create_user(email, "x", first_name=nombre, last_name="Gómez", rol=RolUsuario.CLIENTE)
    return Cliente.objects.create(usuario=u)


def estado_simple(ejercicio_id, semanas=2):
    """Constructor con un ejercicio en el día 1 de cada semana."""
    return {"accion": "guardar", "nombre": "Hipertrofia volumen", "semanas": [
        {"dias": [
            {"nombre": "Pecho y tríceps", "ejercicios": [{
                "ejercicio": ejercicio_id, "tipo_repeticiones": "RANGO", "tipo_esfuerzo": "RIR", "valor_esfuerzo": 2,
                "series": [{"min": 8, "max": 10, "kg": "70", "descanso": 90},
                           {"min": 8, "max": 10, "kg": "72.5", "descanso": 90},
                           {"min": 6, "max": 8, "kg": "75", "descanso": 120}]}]},
            {"nombre": "", "ejercicios": []},
        ]} for _ in range(semanas)]}


class AccesoEntrenadorTests(TestCase):
    def test_solo_entrenadores_y_redireccion_al_ingresar(self):
        ent = crear_entrenador()
        cli = crear_cliente()
        self.assertRedirects(self.client.get(reverse("entrenador_clientes")),
                             f"{reverse('ingresar')}?next={reverse('entrenador_clientes')}")
        self.client.force_login(cli.usuario)
        self.assertRedirects(self.client.get(reverse("entrenador_resumen")), reverse("inicio"))
        self.client.logout()
        r = self.client.post(reverse("ingresar"), {"email": "ent@gmf.co", "password": "x"})
        self.assertRedirects(r, reverse("entrenador_resumen"))
        r = self.client.get(reverse("entrenador_resumen"))
        self.assertContains(r, "Mis clientes")
        self.assertContains(r, "Mensajes")

    def test_el_cliente_usa_rutinas_pero_no_el_panel(self):
        cli = crear_cliente()
        self.client.force_login(cli.usuario)
        r = self.client.get(reverse("rutinas"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, reverse("entrenador_clientes"))
        recep = Usuario.objects.create_user("r@gmf.co", "x", rol=RolUsuario.RECEPCIONISTA)
        self.client.force_login(recep)
        self.assertRedirects(self.client.get(reverse("rutinas")), reverse("inicio"))


class RutinasTests(TestCase):
    def setUp(self):
        self.ent = crear_entrenador()
        self.client.force_login(self.ent)
        self.press = Ejercicio.objects.create(nombre="Press banca", musculo="Pecho", maquina="Barra")

    def test_crear_rutina_crea_dias_y_va_al_constructor(self):
        r = self.client.post(reverse("rutinas"), {"nombre": "PPL", "semanas": "8", "dias_por_semana": "6",
                                                  "objetivo": "Fuerza"})
        rutina = Rutina.objects.get(nombre="PPL")
        self.assertRedirects(r, reverse("rutina_constructor", args=[rutina.pk]))
        self.assertEqual(rutina.estado, EstadoRutina.BORRADOR)
        self.assertEqual(rutina.dias.count(), 48)
        r = self.client.get(reverse("rutinas"))
        self.assertContains(r, "PPL")
        self.assertContains(r, "Borrador")
        self.assertNotContains(r, "En curso")  # el entrenador no "inicia" rutinas

    def test_crear_rutina_errores(self):
        r = self.client.post(reverse("rutinas"), {"nombre": "x" * 51, "semanas": "30", "dias_por_semana": "9"})
        self.assertEqual(r.status_code, 400)
        for campo in ("nombre", "semanas", "dias_por_semana"):
            self.assertIn(campo, r.context["errores"])
        self.assertTrue(r.context["modal_abierto"])

    def test_guardar_y_publicar_constructor(self):
        rutina = Rutina.objects.create(nombre="H", semanas=2, dias_por_semana=2, autor=self.ent)
        url = reverse("rutina_guardar", args=[rutina.pk])
        vacio = {"accion": "publicar", "semanas": [{"dias": [{"ejercicios": []}]}]}
        r = self.client.post(url, json.dumps(vacio), content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("al menos un ejercicio", r.json()["errores"][0])

        datos = estado_simple(self.press.id)
        datos["accion"] = "publicar"
        r = self.client.post(url, json.dumps(datos), content_type="application/json")
        self.assertTrue(r.json()["ok"])
        rutina.refresh_from_db()
        self.assertEqual(rutina.estado, EstadoRutina.PUBLICADA)
        self.assertEqual(rutina.nombre, "Hipertrofia volumen")
        self.assertEqual(rutina.detalle.count(), 2)
        self.assertEqual(SerieRutina.objects.count(), 6)
        self.assertEqual(DiaRutina.objects.get(rutina=rutina, semana=1, dia=1).nombre, "Pecho y tríceps")
        re = rutina.detalle.first()
        self.assertEqual(re.texto_resumen(), "3 series × 8–10 reps · 75 kg")
        r = self.client.get(reverse("rutina_constructor", args=[rutina.pk]))
        self.assertEqual(r.context["estado_rutina"]["semanas"][0]["dias"][0]["ejercicios"][0]["series"][2]["kg"], "75")

    def test_constructor_valida_series_y_ejercicios(self):
        rutina = Rutina.objects.create(nombre="H", semanas=1, autor=self.ent)
        datos = estado_simple(self.press.id, semanas=1)
        datos["semanas"][0]["dias"][0]["ejercicios"][0]["series"][0] = {"min": 12, "max": 8, "kg": "abc"}
        r = self.client.post(reverse("rutina_guardar", args=[rutina.pk]), json.dumps(datos),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(r.json()["errores"]), 2)
        # Un ejercicio inactivo no se puede agregar
        self.press.activo = False
        self.press.save()
        datos = estado_simple(self.press.id, semanas=1)
        r = self.client.post(reverse("rutina_guardar", args=[rutina.pk]), json.dumps(datos),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_solo_el_autor_ve_y_edita(self):
        otro = crear_entrenador("otro@gmf.co")
        rutina = Rutina.objects.create(nombre="Ajena", semanas=1, autor=otro)
        self.assertEqual(self.client.get(reverse("rutina_constructor", args=[rutina.pk])).status_code, 404)
        r = self.client.post(reverse("rutina_guardar", args=[rutina.pk]), "{}", content_type="application/json")
        self.assertEqual(r.status_code, 404)

    def test_duplicar_y_eliminar(self):
        rutina = Rutina.objects.create(nombre="Base", semanas=1, autor=self.ent)
        self.client.post(reverse("rutina_guardar", args=[rutina.pk]),
                         json.dumps(estado_simple(self.press.id, 1)), content_type="application/json")
        self.client.post(reverse("rutina_duplicar", args=[rutina.pk]))
        copia = Rutina.objects.get(copia_de=rutina)
        self.assertEqual(copia.detalle.count(), 1)
        self.assertEqual(SerieRutina.objects.filter(rutina_ejercicio__rutina=copia).count(), 3)
        self.client.post(reverse("rutina_eliminar", args=[copia.pk]))
        self.assertFalse(Rutina.objects.filter(pk=copia.pk).exists())

    def test_crear_ejercicio_personalizado(self):
        url = reverse("ejercicio_nuevo")
        r = self.client.post(url, {"nombre": "Press banca", "tipo_objetivo": "REPS"}, HTTP_ACCEPT="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()["errores"]), {"nombre", "equipo", "musculos"})
        r = self.client.post(url, {"nombre": "Sentadilla búlgara", "tipo_objetivo": "REPS", "equipo": "Mancuerna",
                                   "musculos": ["Cuádriceps", "Glúteos"], "video_url": "https://youtu.be/abc"},
                             HTTP_ACCEPT="application/json")
        self.assertTrue(r.json()["ok"])
        ej = Ejercicio.objects.get(nombre="Sentadilla búlgara")
        self.assertEqual((ej.autor, ej.musculo, ej.maquina), (self.ent, "Cuádriceps, Glúteos", "Mancuerna"))
        # Otro entrenador no lo ve en su biblioteca
        self.client.force_login(crear_entrenador("otro@gmf.co"))
        self.assertNotContains(self.client.get(reverse("ejercicios")), "Cuádriceps, Glúteos")


class ClientesEntrenadorTests(TestCase):
    def setUp(self):
        self.ent = crear_entrenador()
        self.client.force_login(self.ent)
        self.laura = crear_cliente()
        self.juan = crear_cliente("juan@gmf.co", "Juan")
        self.press = Ejercicio.objects.create(nombre="Press banca", musculo="Pecho")
        self.rutina = Rutina.objects.create(nombre="Hipertrofia volumen", semanas=12, dias_por_semana=4,
                                            autor=self.ent, estado=EstadoRutina.PUBLICADA, objetivo="Hipertrofia")
        self.otra = Rutina.objects.create(nombre="PPL", semanas=8, dias_por_semana=6, autor=self.ent,
                                          estado=EstadoRutina.PUBLICADA)
        hoy = timezone.localdate()
        self.asig = AsignacionRutina.objects.create(
            cliente=self.laura, entrenador=self.ent.entrenador, rutina=self.rutina,
            fecha_inicio=hoy - timedelta(weeks=3), fecha_fin=hoy + timedelta(weeks=9))
        # Juan tuvo una rutina conmigo, ya terminada: aparece "sin rutina"
        AsignacionRutina.objects.create(cliente=self.juan, entrenador=self.ent.entrenador, rutina=self.otra,
                                        fecha_inicio=hoy - timedelta(weeks=10), fecha_fin=hoy - timedelta(weeks=2),
                                        estado=EstadoAsignacion.FINALIZADA)
        ProgresoFisico.objects.create(cliente=self.laura, fecha=hoy - timedelta(days=30), peso=Decimal("64.2"))
        ProgresoFisico.objects.create(cliente=self.laura, fecha=hoy, peso=Decimal("62.4"))
        for n, (kg, reps) in enumerate([(Decimal("47.5"), 8), (Decimal("45"), 8)], start=1):
            ProgresoEjercicio.objects.create(cliente=self.laura, asignacion=self.asig, ejercicio=self.press,
                                             fecha=hoy, numero_serie=n, repeticiones_realizadas=reps, carga_kg=kg)
        ProgresoEjercicio.objects.create(cliente=self.laura, asignacion=self.asig, ejercicio=self.press,
                                         fecha=hoy - timedelta(weeks=3), numero_serie=1,
                                         repeticiones_realizadas=10, carga_kg=Decimal("40"))

    def test_lista_kpis_y_filtros(self):
        r = self.client.get(reverse("entrenador_clientes"))
        kpis = r.context["kpis"]
        self.assertEqual((kpis["activos"], kpis["sin_rutina"], kpis["entrenaron_hoy"], kpis["atencion"]), (1, 1, 1, 1))
        self.assertContains(r, "Laura Gómez")
        self.assertContains(r, "62,4 kg")
        self.assertContains(r, "−1,8 kg")
        self.assertContains(r, "S4/12")
        self.assertNotContains(r, "Juan Gómez")
        r = self.client.get(reverse("entrenador_clientes") + "?filtro=sin_rutina")
        self.assertContains(r, "Juan Gómez")
        self.assertContains(r, "Sin rutina")

    def test_detalle_e_historial(self):
        r = self.client.get(reverse("entrenador_cliente", args=[self.laura.pk]))
        self.assertEqual(r.status_code, 200)
        h = r.context["historial"]
        self.assertEqual((h["mejor"]["kg"], h["mejor"]["reps"]), (Decimal("47.5"), 8))
        self.assertEqual(h["rm"], Decimal("60.2"))
        self.assertEqual(h["progreso"], Decimal("7.5"))
        self.assertContains(r, "Semana 4 de 12")
        # Un cliente que no es mío: 404
        ajeno = crear_cliente("x@gmf.co")
        self.assertEqual(self.client.get(reverse("entrenador_cliente", args=[ajeno.pk])).status_code, 404)

    def test_asignar_reemplaza_y_notifica(self):
        url = reverse("entrenador_asignar", args=[self.laura.pk])
        lunes = timezone.localdate() + timedelta(days=7)
        r = self.client.post(url, {"rutina": self.otra.pk, "fecha_inicio": lunes.isoformat(),
                                   "semana_inicio": "2", "nota": "Calienta bien", "notificar": "on"})
        self.assertRedirects(r, reverse("entrenador_cliente", args=[self.laura.pk]))
        self.asig.refresh_from_db()
        self.assertEqual(self.asig.estado, EstadoAsignacion.CANCELADA)
        nueva = self.laura.rutina_actual
        self.assertEqual((nueva.rutina, nueva.semana_inicio, nueva.nota), (self.otra, 2, "Calienta bien"))
        self.assertEqual(nueva.fecha_fin, lunes + timedelta(weeks=7) - timedelta(days=1))
        self.assertTrue(Notificacion.objects.filter(usuario=self.laura.usuario, mensaje__contains="PPL").exists())
        self.assertEqual(self.laura.progresos_ejercicio.count(), 3)  # el historial se conserva

    def test_asignar_errores_y_solo_publicadas(self):
        borrador = Rutina.objects.create(nombre="B", semanas=2, autor=self.ent)
        r = self.client.post(reverse("entrenador_asignar", args=[self.laura.pk]),
                             {"rutina": borrador.pk, "fecha_inicio": "", "semana_inicio": "1"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.context["errores_asignar"]), {"rutina", "fecha_inicio"})
        self.assertTrue(r.context["modal_asignar_abierto"])

    def test_editar_cargas_marca_editado(self):
        serie = ProgresoEjercicio.objects.get(numero_serie=1, carga_kg=Decimal("47.5"))
        r = self.client.post(reverse("entrenador_cargas", args=[self.laura.pk]),
                             {f"kg_{serie.id}": "50", f"reps_{serie.id}": "8"})
        self.assertEqual(r.status_code, 302)
        serie.refresh_from_db()
        self.assertEqual(serie.carga_kg, Decimal("50"))
        self.assertTrue(serie.editado_por_entrenador)
        self.assertEqual(ProgresoEjercicio.objects.filter(editado_por_entrenador=True).count(), 1)

    def test_registrar_peso(self):
        self.client.post(reverse("entrenador_peso", args=[self.laura.pk]),
                         {"peso": "61,9", "fecha": timezone.localdate().isoformat()})
        self.laura.refresh_from_db()
        self.assertEqual(self.laura.peso, Decimal("61.9"))


class MensajesTests(TestCase):
    def setUp(self):
        self.ent = crear_entrenador()
        self.laura = crear_cliente()
        self.admin = Usuario.objects.create_user("admin@gmf.co", "x", first_name="Daniel", last_name="Martínez",
                                                 rol=RolUsuario.ADMINISTRADOR)
        rutina = Rutina.objects.create(nombre="R", semanas=4, autor=self.ent, estado=EstadoRutina.PUBLICADA)
        hoy = timezone.localdate()
        AsignacionRutina.objects.create(cliente=self.laura, entrenador=self.ent.entrenador, rutina=rutina,
                                        fecha_inicio=hoy, fecha_fin=hoy + timedelta(weeks=4))

    def test_pestanas_clientes_y_equipo(self):
        self.client.force_login(self.ent)
        r = self.client.get(reverse("mensajes") + "?pestana=clientes")
        self.assertContains(r, "Laura Gómez")
        self.assertNotContains(r, "Daniel Martínez")
        r = self.client.get(reverse("mensajes") + "?pestana=equipo")
        self.assertContains(r, "Daniel Martínez")
        self.assertContains(r, "Administrador")
        self.assertNotContains(r, "Laura Gómez")

    def test_enviar_leer_y_contador(self):
        self.client.force_login(self.laura.usuario)
        r = self.client.post(reverse("conversacion", args=[self.ent.id]), {"texto": "Hola profe"})
        self.assertRedirects(r, reverse("conversacion", args=[self.ent.id]))
        self.client.force_login(self.ent)
        r = self.client.get(reverse("entrenador_resumen"))
        self.assertContains(r, 'class="contador-lateral"')
        r = self.client.get(reverse("mensajes"))  # abre la conversación más reciente
        self.assertRedirects(r, reverse("conversacion", args=[self.laura.usuario.id]))
        r = self.client.get(reverse("conversacion", args=[self.laura.usuario.id]))
        self.assertContains(r, "Hola profe")
        self.assertFalse(Mensaje.objects.filter(leido=False).exists())

    def test_cliente_no_escribe_a_otro_cliente_y_texto_vacio(self):
        otro = crear_cliente("otro@gmf.co")
        self.client.force_login(self.laura.usuario)
        self.client.post(reverse("conversacion", args=[otro.usuario.id]), {"texto": "hola"})
        self.assertEqual(Mensaje.objects.count(), 0)
        r = self.client.post(reverse("conversacion", args=[self.ent.id]), {"texto": "   "})
        self.assertEqual(r.status_code, 400)
