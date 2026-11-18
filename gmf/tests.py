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
