from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .models import (
    Alimento, AsignacionDieta, AsignacionRutina, Cita, Cliente, Dieta, DietaAlimento,
    Disponibilidad, Ejercicio, Entrenador, Factura, Fisioterapeuta, MedidaCorporal, Mensaje,
    Membresia, MetaNutricional, Notificacion, Nutricionista, Objetivo, Pago, ProgresoEjercicio,
    ProgresoFisico, RegistroComida, Rutina, RutinaEjercicio, Sede, Suscripcion, Usuario,
    DiaRutina, SerieRutina,
)

# Busqueda reutilizable para los modelos que cuelgan de un Usuario
BUSCAR_USUARIO = ["usuario__first_name", "usuario__last_name", "usuario__email"]
BUSCAR_CLIENTE = [
    "cliente__usuario__first_name", "cliente__usuario__last_name",
    "cliente__usuario__email",
]


# ============================================================
# Usuarios y roles
# ============================================================

class UsuarioCreationForm(BaseUserCreationForm):
    class Meta:
        model = Usuario
        fields = ("email", "first_name", "last_name", "rol")


class UsuarioChangeForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    add_form = UsuarioCreationForm
    form = UsuarioChangeForm
    model = Usuario

    list_display = ["email", "first_name", "last_name", "rol", "sede", "is_active"]
    list_filter = ["rol", "sede", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name", "telefono"]
    ordering = ["email"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": (
            "first_name", "last_name", "fecha_nacimiento", "telefono",
        )}),
        ("Gimnasio", {"fields": ("rol", "sede")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "first_name", "last_name", "rol",
                "password1", "password2",
            ),
        }),
    )


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ["nombre", "ciudad", "direccion", "telefono", "correo", "capacidad", "activa"]
    search_fields = ["nombre", "ciudad", "correo"]
    list_filter = ["activa", "ciudad"]
    list_editable = ["activa"]


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ["usuario", "mensaje", "fecha_envio", "leida"]
    list_filter = ["leida", "fecha_envio"]
    search_fields = BUSCAR_USUARIO + ["mensaje"]
    autocomplete_fields = ["usuario"]


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ["remitente", "destinatario", "texto", "fecha_envio", "leido"]
    list_filter = ["leido", "fecha_envio"]
    search_fields = [
        "texto", "remitente__email", "remitente__first_name", "destinatario__email", "destinatario__first_name",
    ]
    autocomplete_fields = ["remitente", "destinatario"]
    date_hierarchy = "fecha_envio"


class ProgresoFisicoInline(admin.TabularInline):
    model = ProgresoFisico
    extra = 0
    fields = ["fecha", "peso", "altura", "porcentaje_graso"]


class ObjetivoInline(admin.TabularInline):
    model = Objetivo
    extra = 0
    fields = ["fecha", "peso_inicial", "peso_meta", "porcentaje_graso_meta", "activo"]


class MetaNutricionalInline(admin.StackedInline):
    model = MetaNutricional
    extra = 0


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["usuario", "plan", "sexo", "peso", "altura", "porcentaje_graso"]
    list_filter = ["sexo"]
    search_fields = BUSCAR_USUARIO
    autocomplete_fields = ["usuario"]
    readonly_fields = ["peso", "altura", "porcentaje_graso"]
    inlines = [ObjetivoInline, ProgresoFisicoInline, MetaNutricionalInline]

    @admin.display(description="Plan")
    def plan(self, obj):
        return "Premium" if obj.plan == "PREMIUM" else "Gratis"


class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ["usuario", "especialidad", "tarjeta_profesional", "num_clientes"]
    search_fields = BUSCAR_USUARIO + ["especialidad"]
    autocomplete_fields = ["usuario"]

    @admin.display(description="Clientes activos")
    def num_clientes(self, obj):
        return obj.num_clientes


@admin.register(Entrenador)
class EntrenadorAdmin(ProfesionalAdmin):
    pass


@admin.register(Nutricionista)
class NutricionistaAdmin(ProfesionalAdmin):
    pass


class DisponibilidadInline(admin.TabularInline):
    model = Disponibilidad
    extra = 1


@admin.register(Fisioterapeuta)
class FisioterapeutaAdmin(ProfesionalAdmin):
    inlines = [DisponibilidadInline]


# ============================================================
# Membresías, pagos y facturación
# ============================================================

@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ["__str__", "tipo", "duracion", "precio", "activa"]
    list_filter = ["tipo", "duracion", "activa"]
    list_editable = ["activa"]
    search_fields = ["tipo", "descripcion"]


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0
    fields = ["fecha", "monto", "metodo_pago", "referencia", "estado"]
    show_change_link = True


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ["cliente", "membresia", "fecha_inicio", "fecha_fin", "estado", "dias_restantes"]
    list_filter = ["estado", "membresia__tipo"]
    search_fields = BUSCAR_CLIENTE
    autocomplete_fields = ["cliente"]
    date_hierarchy = "fecha_inicio"
    inlines = [PagoInline]

    @admin.display(description="Días restantes")
    def dias_restantes(self, obj):
        return obj.calcular_dias_restantes()


class FacturaInline(admin.StackedInline):
    model = Factura
    extra = 0
    readonly_fields = ["num_factura", "fecha_factura"]


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ["id", "suscripcion", "monto", "fecha", "metodo_pago", "estado"]
    list_filter = ["estado", "metodo_pago", "fecha"]
    list_editable = ["estado"]
    search_fields = ["referencia"] + [f"suscripcion__{c}" for c in BUSCAR_CLIENTE]
    autocomplete_fields = ["suscripcion"]
    date_hierarchy = "fecha"
    inlines = [FacturaInline]


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ["num_factura", "pago", "fecha_factura", "subtotal", "impuestos", "total", "estado"]
    list_filter = ["estado", "fecha_factura"]
    search_fields = ["num_factura", "detalle_factura"]
    autocomplete_fields = ["pago"]
    readonly_fields = ["fecha_factura"]


# ============================================================
# Progreso
# ============================================================

@admin.register(ProgresoFisico)
class ProgresoFisicoAdmin(admin.ModelAdmin):
    list_display = ["cliente", "fecha", "peso", "altura", "porcentaje_graso", "imc"]
    list_filter = ["fecha"]
    search_fields = BUSCAR_CLIENTE
    autocomplete_fields = ["cliente"]
    date_hierarchy = "fecha"

    @admin.display(description="IMC")
    def imc(self, obj):
        return obj.calcular_imc()


@admin.register(Objetivo)
class ObjetivoAdmin(admin.ModelAdmin):
    list_display = ["cliente", "fecha", "peso_inicial", "peso_meta", "porcentaje_graso_meta", "activo", "avance"]
    list_filter = ["activo", "fecha"]
    search_fields = BUSCAR_CLIENTE
    autocomplete_fields = ["cliente"]

    @admin.display(description="Avance (%)")
    def avance(self, obj):
        return obj.calcular_avance()


@admin.register(MedidaCorporal)
class MedidaCorporalAdmin(admin.ModelAdmin):
    list_display = ["cliente", "parte", "fecha", "valor_cm"]
    list_filter = ["parte", "fecha"]
    search_fields = BUSCAR_CLIENTE
    autocomplete_fields = ["cliente"]
    date_hierarchy = "fecha"


@admin.register(ProgresoEjercicio)
class ProgresoEjercicioAdmin(admin.ModelAdmin):
    list_display = [
        "cliente", "ejercicio", "fecha", "numero_serie", "series_realizadas",
        "repeticiones_realizadas", "carga_kg", "volumen", "editado_por_entrenador",
    ]
    list_filter = ["fecha", "editado_por_entrenador", "ejercicio__musculo"]
    search_fields = BUSCAR_CLIENTE + ["ejercicio__nombre"]
    autocomplete_fields = ["cliente", "asignacion", "ejercicio"]
    date_hierarchy = "fecha"

    @admin.display(description="Volumen (kg)")
    def volumen(self, obj):
        return obj.calcular_volumen()


# ============================================================
# Entrenamiento
# ============================================================

@admin.register(Ejercicio)
class EjercicioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "musculo", "maquina", "tipo_objetivo", "autor", "activo"]
    list_filter = ["activo", "tipo_objetivo", "maquina"]
    search_fields = ["nombre", "musculo", "maquina"]
    autocomplete_fields = ["autor"]


class RutinaEjercicioInline(admin.TabularInline):
    model = RutinaEjercicio
    extra = 1
    autocomplete_fields = ["ejercicio"]
    fields = [
        "semana", "dia", "orden", "ejercicio", "series", "tipo_repeticiones",
        "repeticiones_min", "repeticiones_max", "tipo_esfuerzo", "valor_esfuerzo", "descanso_segundos",
    ]


class DiaRutinaInline(admin.TabularInline):
    model = DiaRutina
    extra = 0
    fields = ["semana", "dia", "nombre"]


@admin.register(Rutina)
class RutinaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "autor", "estado", "nivel", "semanas", "dias_por_semana", "visibilidad", "copia_de"]
    list_filter = ["estado", "visibilidad", "nivel", "autor__rol"]
    search_fields = ["nombre", "objetivo", "autor__email", "autor__first_name", "autor__last_name"]
    autocomplete_fields = ["autor", "copia_de"]
    inlines = [DiaRutinaInline, RutinaEjercicioInline]


class SerieRutinaInline(admin.TabularInline):
    model = SerieRutina
    extra = 0
    fields = ["numero", "repeticiones_min", "repeticiones_max", "carga_kg", "descanso_segundos"]


@admin.register(RutinaEjercicio)
class RutinaEjercicioAdmin(admin.ModelAdmin):
    """Para ver y corregir las series de un ejercicio de la rutina."""
    list_display = ["rutina", "semana", "dia", "orden", "ejercicio", "series"]
    list_filter = ["rutina"]
    search_fields = ["rutina__nombre", "ejercicio__nombre"]
    autocomplete_fields = ["rutina", "ejercicio"]
    inlines = [SerieRutinaInline]


@admin.register(AsignacionRutina)
class AsignacionRutinaAdmin(admin.ModelAdmin):
    list_display = ["rutina", "cliente", "entrenador", "fecha_inicio", "fecha_fin", "semana_inicio", "estado"]
    list_filter = ["estado", "entrenador"]
    list_editable = ["estado"]
    search_fields = BUSCAR_CLIENTE + ["rutina__nombre"]
    autocomplete_fields = ["cliente", "entrenador", "rutina"]
    date_hierarchy = "fecha_inicio"


# ============================================================
# Nutrición
# ============================================================

@admin.register(Alimento)
class AlimentoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "categoria", "activo", "kcal", "proteinas", "carbohidratos", "grasas", "porcion_gramos", "porcion_nombre"]
    list_filter = ["activo", "categoria"]
    search_fields = ["nombre", "categoria", "codigo_barras"]


class DietaAlimentoInline(admin.TabularInline):
    model = DietaAlimento
    extra = 1
    autocomplete_fields = ["alimento"]


@admin.register(Dieta)
class DietaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "autor", "visibilidad", "objetivo", "kcal"]
    list_filter = ["visibilidad", "autor__rol"]
    search_fields = ["nombre", "objetivo", "autor__email", "autor__first_name", "autor__last_name"]
    autocomplete_fields = ["autor", "copia_de"]
    inlines = [DietaAlimentoInline]

    @admin.display(description="Kcal totales")
    def kcal(self, obj):
        return obj.kcal_totales


@admin.register(RegistroComida)
class RegistroComidaAdmin(admin.ModelAdmin):
    list_display = ["cliente", "fecha", "comida", "alimento", "cantidad_gramos", "kcal"]
    list_filter = ["comida", "fecha"]
    search_fields = BUSCAR_CLIENTE + ["alimento__nombre"]
    autocomplete_fields = ["cliente", "alimento"]
    date_hierarchy = "fecha"

    @admin.display(description="Kcal")
    def kcal(self, obj):
        return obj.calcular_macros()["kcal"]


@admin.register(MetaNutricional)
class MetaNutricionalAdmin(admin.ModelAdmin):
    list_display = ["cliente", "kcal", "proteinas", "carbohidratos", "grasas"]
    search_fields = BUSCAR_CLIENTE
    autocomplete_fields = ["cliente"]


@admin.register(AsignacionDieta)
class AsignacionDietaAdmin(admin.ModelAdmin):
    list_display = ["dieta", "cliente", "nutricionista", "fecha_inicio", "fecha_fin", "estado"]
    list_filter = ["estado", "nutricionista"]
    list_editable = ["estado"]
    search_fields = BUSCAR_CLIENTE + ["dieta__nombre"]
    autocomplete_fields = ["cliente", "nutricionista", "dieta"]
    date_hierarchy = "fecha_inicio"


# ============================================================
# Citas
# ============================================================

@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ["cliente", "fisioterapeuta", "fecha_inicio", "fecha_fin", "motivo", "estado"]
    list_filter = ["estado", "fisioterapeuta"]
    list_editable = ["estado"]
    search_fields = BUSCAR_CLIENTE + ["motivo"]
    autocomplete_fields = ["cliente", "fisioterapeuta"]
    date_hierarchy = "fecha_inicio"
    actions = ["enviar_recordatorios"]

    @admin.action(description="Enviar recordatorio a los clientes seleccionados")
    def enviar_recordatorios(self, request, queryset):
        for cita in queryset:
            cita.enviar_recordatorio()
        self.message_user(request, f"Recordatorios enviados: {queryset.count()}")
