"""
Modelos de GMFitness.

Basados en el diagrama de clases "Diagrama de clases GMF v2".
Equivalencias con el diagrama:
- Usuario hereda de AbstractUser: nombre -> first_name, apellido -> last_name,
  contrasenaHash -> password (Django la cifra), activo -> is_active,
  fechaRegistro -> date_joined. Se inicia sesion con el email.
- Cliente, Entrenador, Nutricionista y Fisioterapeuta son perfiles 1 a 1 de Usuario.
- Administrador no tiene tabla: es un Usuario con rol ADMINISTRADOR e is_staff=True.
- Recepcionista tampoco tiene tabla: Usuario con rol RECEPCIONISTA (personal del gimnasio).
- Los atributos derivados del diagrama (/numClientes, /kcalTotales, /plan...) son @property.
- Unidades: peso en kg, altura y medidas corporales en cm, alimentos por cada 100 g.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

# Tasa de IVA usada por Factura.calcular_impuestos(). Ajustala si cambia.
TASA_IVA = Decimal("0.19")

POSITIVO = [MinValueValidator(Decimal("0"))]


# ============================================================
# Enumeraciones
# ============================================================

class Sexo(models.TextChoices):
    MASCULINO = "M", "Masculino"
    FEMENINO = "F", "Femenino"
    OTRO = "O", "Otro"


class RolUsuario(models.TextChoices):
    CLIENTE = "CLIENTE", "Cliente"
    ENTRENADOR = "ENTRENADOR", "Entrenador"
    NUTRICIONISTA = "NUTRICIONISTA", "Nutricionista"
    FISIOTERAPEUTA = "FISIOTERAPEUTA", "Fisioterapeuta"
    RECEPCIONISTA = "RECEPCIONISTA", "Recepcionista"
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"


class DiaSemana(models.IntegerChoices):
    # Mismos numeros que date.weekday() de Python
    LUNES = 0, "Lunes"
    MARTES = 1, "Martes"
    MIERCOLES = 2, "Miércoles"
    JUEVES = 3, "Jueves"
    VIERNES = 4, "Viernes"
    SABADO = 5, "Sábado"
    DOMINGO = 6, "Domingo"


class TipoMembresia(models.TextChoices):
    # El plan Gratis no es una membresía: un cliente sin suscripción activa está en Gratis.
    PREMIUM = "PREMIUM", "Premium"


class DuracionMembresia(models.TextChoices):
    MENSUAL = "MENSUAL", "Mensual"
    ANUAL = "ANUAL", "Anual"


DIAS_POR_DURACION = {
    DuracionMembresia.MENSUAL: 30,
    DuracionMembresia.ANUAL: 365,
}


class EstadoSuscripcion(models.TextChoices):
    ACTIVA = "ACTIVA", "Activa"
    VENCIDA = "VENCIDA", "Vencida"
    CANCELADA = "CANCELADA", "Cancelada"


class MetodoPago(models.TextChoices):
    EFECTIVO = "EFECTIVO", "Efectivo"
    TARJETA = "TARJETA", "Tarjeta"
    TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"
    PSE = "PSE", "PSE"


class EstadoPago(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    APROBADO = "APROBADO", "Aprobado"
    RECHAZADO = "RECHAZADO", "Rechazado"
    REEMBOLSADO = "REEMBOLSADO", "Reembolsado"


class EstadoFactura(models.TextChoices):
    EMITIDA = "EMITIDA", "Emitida"
    ANULADA = "ANULADA", "Anulada"


class EstadoAsignacion(models.TextChoices):
    ACTIVA = "ACTIVA", "Activa"
    PAUSADA = "PAUSADA", "Pausada"
    FINALIZADA = "FINALIZADA", "Finalizada"
    CANCELADA = "CANCELADA", "Cancelada"


class TipoComida(models.TextChoices):
    DESAYUNO = "DESAYUNO", "Desayuno"
    ALMUERZO = "ALMUERZO", "Almuerzo"
    CENA = "CENA", "Cena"


class EstadoCita(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    CANCELADA = "CANCELADA", "Cancelada"
    COMPLETADA = "COMPLETADA", "Completada"


class Visibilidad(models.TextChoices):
    PRIVADA = "PRIVADA", "Privada"
    PUBLICA = "PUBLICA", "Pública"


class NivelRutina(models.TextChoices):
    PRINCIPIANTE = "PRINCIPIANTE", "Principiante"
    INTERMEDIO = "INTERMEDIO", "Intermedio"
    AVANZADO = "AVANZADO", "Avanzado"


class TipoRepeticiones(models.TextChoices):
    MAXIMAS = "MAXIMAS", "Reps máximas"
    RANGO = "RANGO", "Rango de reps"
    AMRAP = "AMRAP", "AMRAP"


class TipoEsfuerzo(models.TextChoices):
    RIR = "RIR", "RIR"
    ARM = "ARM", "ARM"


class ParteCuerpo(models.TextChoices):
    CUELLO = "CUELLO", "Cuello"
    HOMBROS = "HOMBROS", "Hombros"
    PECHO = "PECHO", "Pecho"
    BRAZO = "BRAZO", "Brazo"
    CINTURA = "CINTURA", "Cintura"
    CADERA = "CADERA", "Cadera"
    MUSLO = "MUSLO", "Muslo"
    PANTORRILLA = "PANTORRILLA", "Pantorrilla"


def macros_de(alimento, gramos):
    """kcal y macros de una cantidad en gramos (los valores del alimento son por 100 g)."""
    f = Decimal(gramos) / Decimal(100)
    q = Decimal("0.01")
    return {
        "kcal": (alimento.kcal * f).quantize(q),
        "proteinas": (alimento.proteinas * f).quantize(q),
        "carbohidratos": (alimento.carbohidratos * f).quantize(q),
        "grasas": (alimento.grasas * f).quantize(q),
    }


def fechas_en_orden(nombre):
    """Restriccion de base de datos: fecha_fin no puede ser anterior a fecha_inicio."""
    return models.CheckConstraint(
        condition=Q(fecha_fin__gte=F("fecha_inicio")),
        name=f"{nombre}_fecha_fin_mayor_o_igual",
    )


# ============================================================
# Usuarios y roles
# ============================================================

class Sede(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200)
    ciudad = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField(blank=True)
    capacidad = models.PositiveIntegerField(null=True, blank=True, help_text="Número de personas.")
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "sedes"

    def __str__(self):
        return f"{self.nombre} ({self.ciudad})"


class UsuarioManager(BaseUserManager):
    """Manager para crear usuarios con email en lugar de username."""

    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email:
            raise ValueError("El email es obligatorio")
        usuario = self.model(email=self.normalize_email(email), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("rol", RolUsuario.ADMINISTRADOR)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("El superusuario necesita is_staff=True e is_superuser=True")
        return self._crear(email, password, **extra)


class Usuario(AbstractUser):
    username = None
    email = models.EmailField("email", unique=True)
    numero_identidad = models.CharField("número de identidad", max_length=20, unique=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    rol = models.CharField(max_length=20, choices=RolUsuario.choices, default=RolUsuario.CLIENTE)
    sede = models.ForeignKey(
        Sede, on_delete=models.SET_NULL, null=True, blank=True, related_name="usuarios"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["numero_identidad", "first_name", "last_name"]

    objects = UsuarioManager()

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def calcular_edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = timezone.localdate()
        nac = self.fecha_nacimiento
        return hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))


class Notificacion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="notificaciones")
    mensaje = models.CharField(max_length=500)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    class Meta:
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        ordering = ["-fecha_envio"]

    def __str__(self):
        return f"Para {self.usuario}: {self.mensaje[:40]}"

    def marcar_como_leida(self):
        self.leida = True
        self.save(update_fields=["leida"])


class Cliente(models.Model):
    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name="cliente",
        limit_choices_to={"rol": RolUsuario.CLIENTE},
    )
    sexo = models.CharField(max_length=1, choices=Sexo.choices)
    # Valores actuales: se actualizan solos al registrar un ProgresoFisico
    peso = models.DecimalField("peso (kg)", max_digits=5, decimal_places=2, null=True, blank=True, validators=POSITIVO)
    altura = models.DecimalField("altura (cm)", max_digits=4, decimal_places=1, null=True, blank=True, validators=POSITIVO)
    porcentaje_graso = models.DecimalField(
        "% graso", max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    def __str__(self):
        return str(self.usuario)

    def actualizar_medidas(self, progreso):
        """Copia los valores de la medicion mas reciente al cliente.
        Los que vengan vacios (altura, % graso) conservan el valor anterior."""
        self.peso = progreso.peso
        if progreso.altura is not None:
            self.altura = progreso.altura
        if progreso.porcentaje_graso is not None:
            self.porcentaje_graso = progreso.porcentaje_graso
        self.save(update_fields=["peso", "altura", "porcentaje_graso"])

    @property
    def plan(self):
        """'PREMIUM' si tiene una suscripcion vigente; si no, 'GRATIS'."""
        return "PREMIUM" if self.suscripcion_activa else "GRATIS"

    @property
    def objetivo_activo(self):
        return self.objetivos.filter(activo=True).first()

    def totales_del_dia(self, fecha):
        """Suma de kcal y macros del diario de comidas en una fecha."""
        totales = {"kcal": Decimal(0), "proteinas": Decimal(0), "carbohidratos": Decimal(0), "grasas": Decimal(0)}
        for registro in self.registros_comida.filter(fecha=fecha).select_related("alimento"):
            for clave, valor in registro.calcular_macros().items():
                totales[clave] += valor
        return totales

    @property
    def suscripcion_activa(self):
        hoy = timezone.localdate()
        return self.suscripciones.filter(
            estado=EstadoSuscripcion.ACTIVA, fecha_inicio__lte=hoy, fecha_fin__gte=hoy
        ).first()

    @property
    def rutina_actual(self):
        return self.asignaciones_rutina.filter(estado=EstadoAsignacion.ACTIVA).order_by("-fecha_inicio").first()

    @property
    def dieta_actual(self):
        return self.asignaciones_dieta.filter(estado=EstadoAsignacion.ACTIVA).order_by("-fecha_inicio").first()


class PerfilProfesional(models.Model):
    """Clase abstracta 'Profesional' del diagrama: no crea tabla propia."""

    especialidad = models.CharField(max_length=100)
    tarjeta_profesional = models.CharField(max_length=50, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.usuario)


class Entrenador(PerfilProfesional):
    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name="entrenador",
        limit_choices_to={"rol": RolUsuario.ENTRENADOR},
    )

    class Meta:
        verbose_name_plural = "entrenadores"

    @property
    def num_clientes(self):
        return self.asignaciones.filter(estado=EstadoAsignacion.ACTIVA).values("cliente").distinct().count()


class Nutricionista(PerfilProfesional):
    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name="nutricionista",
        limit_choices_to={"rol": RolUsuario.NUTRICIONISTA},
    )

    @property
    def num_clientes(self):
        return self.asignaciones.filter(estado=EstadoAsignacion.ACTIVA).values("cliente").distinct().count()


class Fisioterapeuta(PerfilProfesional):
    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name="fisioterapeuta",
        limit_choices_to={"rol": RolUsuario.FISIOTERAPEUTA},
    )

    @property
    def num_clientes(self):
        return self.citas.exclude(estado=EstadoCita.CANCELADA).values("cliente").distinct().count()


class Disponibilidad(models.Model):
    fisioterapeuta = models.ForeignKey(Fisioterapeuta, on_delete=models.CASCADE, related_name="disponibilidades")
    dia_semana = models.IntegerField(choices=DiaSemana.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        verbose_name_plural = "disponibilidades"
        ordering = ["dia_semana", "hora_inicio"]
        constraints = [
            models.CheckConstraint(
                condition=Q(hora_fin__gt=F("hora_inicio")), name="disponibilidad_hora_fin_mayor"
            )
        ]

    def __str__(self):
        return f"{self.get_dia_semana_display()} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}"

    def esta_disponible(self, inicio, fin):
        """True si el rango [inicio, fin] cae dentro de este bloque."""
        inicio, fin = timezone.localtime(inicio), timezone.localtime(fin)
        return (
            inicio.weekday() == self.dia_semana
            and inicio.date() == fin.date()
            and self.hora_inicio <= inicio.time()
            and fin.time() <= self.hora_fin
        )


# ============================================================
# Membresías, pagos y facturación
# ============================================================

class Membresia(models.Model):
    """Catalogo de planes que vende el gimnasio."""

    tipo = models.CharField(max_length=20, choices=TipoMembresia.choices)
    duracion = models.CharField(max_length=20, choices=DuracionMembresia.choices)
    precio = models.DecimalField(max_digits=12, decimal_places=2, validators=POSITIVO)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "membresía"

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.get_duracion_display()}"

    @property
    def dias_duracion(self):
        return DIAS_POR_DURACION[self.duracion]


class Suscripcion(models.Model):
    """Compra de una membresia por parte de un cliente."""

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="suscripciones")
    membresia = models.ForeignKey(Membresia, on_delete=models.PROTECT, related_name="suscripciones")
    fecha_inicio = models.DateField(default=timezone.localdate)
    fecha_fin = models.DateField(blank=True, help_text="Si se deja vacía se calcula con la duración de la membresía.")
    estado = models.CharField(max_length=20, choices=EstadoSuscripcion.choices, default=EstadoSuscripcion.ACTIVA)

    class Meta:
        verbose_name = "suscripción"
        verbose_name_plural = "suscripciones"
        constraints = [fechas_en_orden("suscripcion")]

    def __str__(self):
        return f"{self.cliente} - {self.membresia}"

    def _completar_fecha_fin(self):
        if not self.fecha_fin and self.fecha_inicio and self.membresia_id:
            self.fecha_fin = self.fecha_inicio + timedelta(days=self.membresia.dias_duracion)

    def clean(self):
        self._completar_fecha_fin()

    def save(self, *args, **kwargs):
        self._completar_fecha_fin()
        super().save(*args, **kwargs)

    def verificar_vigencia(self):
        hoy = timezone.localdate()
        return self.estado == EstadoSuscripcion.ACTIVA and self.fecha_inicio <= hoy <= self.fecha_fin

    def calcular_dias_restantes(self):
        return max((self.fecha_fin - timezone.localdate()).days, 0)


class Pago(models.Model):
    suscripcion = models.ForeignKey(Suscripcion, on_delete=models.PROTECT, related_name="pagos")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=POSITIVO)
    fecha = models.DateTimeField(default=timezone.now)
    metodo_pago = models.CharField(max_length=20, choices=MetodoPago.choices)
    referencia = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=20, choices=EstadoPago.choices, default=EstadoPago.PENDIENTE)

    def __str__(self):
        return f"Pago #{self.pk} - {self.monto} ({self.get_estado_display()})"

    def verificar_pago(self):
        return self.estado == EstadoPago.APROBADO

    def aplicar_descuento(self, porcentaje):
        """Descuenta un porcentaje (ej. 10 = 10%) al monto y lo devuelve."""
        self.monto = (self.monto * (Decimal(100) - Decimal(porcentaje)) / Decimal(100)).quantize(Decimal("0.01"))
        return self.monto


class Factura(models.Model):
    num_factura = models.BigAutoField("número de factura", primary_key=True)
    pago = models.OneToOneField(Pago, on_delete=models.PROTECT, related_name="factura")
    detalle_factura = models.CharField(max_length=300)
    fecha_factura = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, validators=POSITIVO)
    impuestos = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=POSITIVO)
    total = models.DecimalField(max_digits=12, decimal_places=2, validators=POSITIVO)
    estado = models.CharField(max_length=20, choices=EstadoFactura.choices, default=EstadoFactura.EMITIDA)

    def __str__(self):
        return f"Factura {self.num_factura}"

    def calcular_impuestos(self):
        self.impuestos = (self.subtotal * TASA_IVA).quantize(Decimal("0.01"))
        self.total = self.subtotal + self.impuestos
        return self.impuestos

    def anular_factura(self):
        self.estado = EstadoFactura.ANULADA
        self.save(update_fields=["estado"])


# ============================================================
# Progreso
# ============================================================

class ProgresoFisico(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="progresos_fisicos")
    fecha = models.DateField(default=timezone.localdate)
    peso = models.DecimalField("peso (kg)", max_digits=5, decimal_places=2, validators=POSITIVO)
    altura = models.DecimalField("altura (cm)", max_digits=4, decimal_places=1, null=True, blank=True, validators=POSITIVO)
    porcentaje_graso = models.DecimalField(
        "% graso", max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        verbose_name = "progreso físico"
        verbose_name_plural = "progresos físicos"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.cliente} - {self.fecha}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Si es la medicion mas reciente, actualiza los valores actuales del cliente
        ultima = self.cliente.progresos_fisicos.order_by("-fecha", "-id").first()
        if ultima and ultima.pk == self.pk:
            self.cliente.actualizar_medidas(self)

    def calcular_imc(self):
        """IMC = peso / altura(m)^2. Si la medicion no trae altura usa la actual del cliente."""
        altura_cm = self.altura or self.cliente.altura
        if not altura_cm:
            return None
        metros = altura_cm / Decimal(100)
        return (self.peso / (metros * metros)).quantize(Decimal("0.01"))

    def calcular_evolucion(self, anterior):
        """Diferencia de peso respecto a una medicion anterior (negativo = bajo de peso)."""
        return self.peso - anterior.peso


# ============================================================
# Entrenamiento
# ============================================================

class Ejercicio(models.Model):
    nombre = models.CharField(max_length=150)
    musculo = models.CharField("grupo muscular", max_length=100)
    maquina = models.CharField("máquina / equipo", max_length=100, blank=True)
    imagen_url = models.URLField("URL de la imagen", blank=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.musculo})"


class Rutina(models.Model):
    """Plantilla de rutina. La crea cualquier usuario (cliente o profesional)."""

    nombre = models.CharField(max_length=150)
    objetivo = models.CharField(max_length=200, blank=True)
    descripcion = models.TextField(blank=True)
    nivel = models.CharField(max_length=20, choices=NivelRutina.choices, blank=True)
    semanas = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1), MaxValueValidator(24)])
    visibilidad = models.CharField(max_length=10, choices=Visibilidad.choices, default=Visibilidad.PRIVADA)
    autor = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="rutinas_creadas")
    copia_de = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="copias"
    )
    ejercicios = models.ManyToManyField(Ejercicio, through="RutinaEjercicio", related_name="rutinas")

    def __str__(self):
        return self.nombre

    @property
    def dias_por_semana(self):
        """Mayor numero de dias que tiene alguna semana de la rutina."""
        return self.detalle.aggregate(m=models.Max("dia"))["m"] or 0

    def duplicar(self, nuevo_autor):
        copia = Rutina.objects.create(
            nombre=f"{self.nombre} (copia)", objetivo=self.objetivo, descripcion=self.descripcion,
            nivel=self.nivel, semanas=self.semanas,
            visibilidad=Visibilidad.PRIVADA, autor=nuevo_autor, copia_de=self,
        )
        for re in self.detalle.all():
            re.pk = None
            re.rutina = copia
            re.save()
        return copia


class RutinaEjercicio(models.Model):
    """Un ejercicio dentro de una semana y un dia de la rutina."""

    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE, related_name="detalle")
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.PROTECT)
    semana = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(24)])
    dia = models.PositiveSmallIntegerField("día", default=1, validators=[MinValueValidator(1), MaxValueValidator(7)])
    orden = models.PositiveSmallIntegerField(default=1)
    series = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(20)])
    tipo_repeticiones = models.CharField(max_length=10, choices=TipoRepeticiones.choices, default=TipoRepeticiones.RANGO)
    repeticiones_min = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Reps (máximas) o inicio del rango. Vacío en AMRAP."
    )
    repeticiones_max = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Solo para rango.")
    tipo_esfuerzo = models.CharField(max_length=5, choices=TipoEsfuerzo.choices, default=TipoEsfuerzo.RIR)
    valor_esfuerzo = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10)], help_text="Valor RIR (0-10). Vacío en ARM."
    )
    descanso_segundos = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "ejercicio de la rutina"
        verbose_name_plural = "ejercicios de la rutina"
        ordering = ["rutina", "semana", "dia", "orden"]

    def __str__(self):
        return f"S{self.semana} D{self.dia} - {self.ejercicio.nombre} {self.series}x{self.texto_repeticiones()}"

    def texto_repeticiones(self):
        if self.tipo_repeticiones == TipoRepeticiones.RANGO:
            return f"{self.repeticiones_min}-{self.repeticiones_max}"
        if self.tipo_repeticiones == TipoRepeticiones.AMRAP:
            return "AMRAP"
        return f"{self.repeticiones_min} máx."

    def clean(self):
        errores = {}
        if self.rutina_id and self.semana and self.semana > self.rutina.semanas:
            errores["semana"] = f"La rutina solo tiene {self.rutina.semanas} semanas."
        tipo = self.tipo_repeticiones
        if tipo == TipoRepeticiones.RANGO:
            if not self.repeticiones_min or not self.repeticiones_max:
                errores["repeticiones_max"] = "Un rango necesita repeticiones mínimas y máximas."
            elif self.repeticiones_min > self.repeticiones_max:
                errores["repeticiones_max"] = "El máximo debe ser mayor o igual al mínimo."
        elif tipo == TipoRepeticiones.MAXIMAS and not self.repeticiones_min:
            errores["repeticiones_min"] = "Indica las repeticiones."
        if self.tipo_esfuerzo == TipoEsfuerzo.RIR and self.valor_esfuerzo is None:
            errores["valor_esfuerzo"] = "Indica el valor RIR."
        if errores:
            raise ValidationError(errores)


class AsignacionRutina(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="asignaciones_rutina")
    entrenador = models.ForeignKey(
        Entrenador, on_delete=models.SET_NULL, null=True, blank=True, related_name="asignaciones",
        help_text="Vacío si el cliente se asignó la rutina a sí mismo.",
    )
    rutina = models.ForeignKey(Rutina, on_delete=models.PROTECT, related_name="asignaciones")
    fecha_asignacion = models.DateField(auto_now_add=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=20, choices=EstadoAsignacion.choices, default=EstadoAsignacion.ACTIVA)

    class Meta:
        verbose_name = "asignación de rutina"
        verbose_name_plural = "asignaciones de rutina"
        constraints = [fechas_en_orden("asignacion_rutina")]

    def __str__(self):
        return f"{self.rutina} -> {self.cliente}"

    def verificar_vigencia(self):
        hoy = timezone.localdate()
        return self.estado == EstadoAsignacion.ACTIVA and self.fecha_inicio <= hoy <= self.fecha_fin


class ProgresoEjercicio(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="progresos_ejercicio")
    asignacion = models.ForeignKey(
        AsignacionRutina, on_delete=models.PROTECT, null=True, blank=True, related_name="registros",
        help_text="Vacío si el registro no es parte de una rutina asignada.",
    )
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.PROTECT, related_name="registros")
    fecha = models.DateField(default=timezone.localdate)
    series_realizadas = models.PositiveSmallIntegerField(null=True, blank=True)
    repeticiones_realizadas = models.PositiveSmallIntegerField()
    carga_kg = models.DecimalField("peso (kg)", max_digits=6, decimal_places=2, default=0, validators=POSITIVO)
    intensidad = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, validators=POSITIVO)

    class Meta:
        verbose_name = "progreso de ejercicio"
        verbose_name_plural = "progresos de ejercicio"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.cliente} - {self.ejercicio.nombre} ({self.fecha})"

    def clean(self):
        if self.asignacion_id and self.cliente_id and self.asignacion.cliente_id != self.cliente_id:
            raise ValidationError("La asignación no pertenece a este cliente.")

    def calcular_volumen(self):
        return (self.series_realizadas or 1) * self.repeticiones_realizadas * self.carga_kg


# ============================================================
# Nutrición
# ============================================================

class Alimento(models.Model):
    """Los valores nutricionales (kcal y macros) son siempre por cada 100 g."""

    codigo_barras = models.CharField("código de barras", max_length=20, unique=True, null=True, blank=True)
    nombre = models.CharField(max_length=150)
    categoria = models.CharField("categoría", max_length=50, blank=True)
    porcion_gramos = models.DecimalField(
        "porción típica (g)", max_digits=6, decimal_places=1, default=100,
        help_text="Cantidad sugerida; el usuario puede escribir otra al registrar.",
    )
    porcion_nombre = models.CharField("nombre de la porción", max_length=50, blank=True, help_text='Ej: "1 unidad".')
    imagen_url = models.URLField("URL de la imagen", blank=True)
    proteinas = models.DecimalField(max_digits=6, decimal_places=2, validators=POSITIVO)
    grasas = models.DecimalField(max_digits=6, decimal_places=2, validators=POSITIVO)
    carbohidratos = models.DecimalField(max_digits=6, decimal_places=2, validators=POSITIVO)
    kcal = models.DecimalField(max_digits=7, decimal_places=2, validators=POSITIVO)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Dieta(models.Model):
    """Plantilla de dieta. La crea cualquier usuario (cliente o profesional)."""

    nombre = models.CharField(max_length=150)
    objetivo = models.CharField(max_length=200, blank=True)
    descripcion = models.TextField(blank=True)
    visibilidad = models.CharField(max_length=10, choices=Visibilidad.choices, default=Visibilidad.PRIVADA)
    autor = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="dietas_creadas")
    copia_de = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="copias"
    )
    alimentos = models.ManyToManyField(Alimento, through="DietaAlimento", related_name="dietas")

    def __str__(self):
        return self.nombre

    def calcular_totales(self):
        totales = {"kcal": Decimal(0), "proteinas": Decimal(0), "carbohidratos": Decimal(0), "grasas": Decimal(0)}
        for da in self.detalle.select_related("alimento"):
            for clave, valor in da.calcular_macros().items():
                totales[clave] += valor
        return totales

    @property
    def kcal_totales(self):
        return self.calcular_totales()["kcal"]

    @property
    def proteinas_totales(self):
        return self.calcular_totales()["proteinas"]

    @property
    def carbohidratos_totales(self):
        return self.calcular_totales()["carbohidratos"]

    @property
    def grasas_totales(self):
        return self.calcular_totales()["grasas"]

    def duplicar(self, nuevo_autor):
        copia = Dieta.objects.create(
            nombre=f"{self.nombre} (copia)", objetivo=self.objetivo, descripcion=self.descripcion,
            visibilidad=Visibilidad.PRIVADA, autor=nuevo_autor, copia_de=self,
        )
        for da in self.detalle.all():
            da.pk = None
            da.dieta = copia
            da.save()
        return copia


class DietaAlimento(models.Model):
    dieta = models.ForeignKey(Dieta, on_delete=models.CASCADE, related_name="detalle")
    alimento = models.ForeignKey(Alimento, on_delete=models.PROTECT)
    cantidad_gramos = models.DecimalField(max_digits=6, decimal_places=1, validators=POSITIVO)
    comida = models.CharField(max_length=20, choices=TipoComida.choices)

    class Meta:
        verbose_name = "alimento de la dieta"
        verbose_name_plural = "alimentos de la dieta"

    def __str__(self):
        return f"{self.get_comida_display()}: {self.alimento} {self.cantidad_gramos} g"

    def calcular_kcal(self):
        return macros_de(self.alimento, self.cantidad_gramos)["kcal"]

    def calcular_macros(self):
        return macros_de(self.alimento, self.cantidad_gramos)


class AsignacionDieta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="asignaciones_dieta")
    nutricionista = models.ForeignKey(
        Nutricionista, on_delete=models.SET_NULL, null=True, blank=True, related_name="asignaciones",
        help_text="Vacío si el cliente se asignó la dieta a sí mismo.",
    )
    dieta = models.ForeignKey(Dieta, on_delete=models.PROTECT, related_name="asignaciones")
    fecha_asignacion = models.DateField(auto_now_add=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=20, choices=EstadoAsignacion.choices, default=EstadoAsignacion.ACTIVA)

    class Meta:
        verbose_name = "asignación de dieta"
        verbose_name_plural = "asignaciones de dieta"
        constraints = [fechas_en_orden("asignacion_dieta")]

    def __str__(self):
        return f"{self.dieta} -> {self.cliente}"

    def verificar_vigencia(self):
        hoy = timezone.localdate()
        return self.estado == EstadoAsignacion.ACTIVA and self.fecha_inicio <= hoy <= self.fecha_fin

    def calcular_calorias_diarias(self):
        return self.dieta.kcal_totales


# ============================================================
# Citas
# ============================================================

class Cita(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="citas")
    fisioterapeuta = models.ForeignKey(Fisioterapeuta, on_delete=models.PROTECT, related_name="citas")
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=EstadoCita.choices, default=EstadoCita.PENDIENTE)
    motivo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha_inicio"]
        constraints = [
            models.CheckConstraint(condition=Q(fecha_fin__gt=F("fecha_inicio")), name="cita_fecha_fin_mayor")
        ]

    def __str__(self):
        return f"{self.cliente} con {self.fisioterapeuta} - {timezone.localtime(self.fecha_inicio):%Y-%m-%d %H:%M}"

    def verificar_disponibilidad(self):
        """True si el fisioterapeuta atiende en ese horario y no tiene otra cita cruzada."""
        dentro_de_horario = any(
            d.esta_disponible(self.fecha_inicio, self.fecha_fin)
            for d in self.fisioterapeuta.disponibilidades.all()
        )
        cruzadas = (
            Cita.objects.filter(
                fisioterapeuta=self.fisioterapeuta,
                fecha_inicio__lt=self.fecha_fin,
                fecha_fin__gt=self.fecha_inicio,
            )
            .exclude(estado=EstadoCita.CANCELADA)
            .exclude(pk=self.pk)
        )
        return dentro_de_horario and not cruzadas.exists()

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fisioterapeuta_id:
            if self.fecha_fin <= self.fecha_inicio:
                raise ValidationError("La hora de fin debe ser posterior a la de inicio.")
            if self.estado != EstadoCita.CANCELADA and not self.verificar_disponibilidad():
                raise ValidationError("El fisioterapeuta no está disponible en ese horario.")

    def cancelar_cita(self):
        self.estado = EstadoCita.CANCELADA
        self.save(update_fields=["estado"])

    def enviar_recordatorio(self):
        inicio = timezone.localtime(self.fecha_inicio)
        return Notificacion.objects.create(
            usuario=self.cliente.usuario,
            mensaje=f"Recordatorio: cita con {self.fisioterapeuta} el {inicio:%d/%m/%Y a las %H:%M}.",
        )


# ============================================================
# Objetivos y medidas corporales del cliente
# ============================================================

class Objetivo(models.Model):
    """Meta del cliente. Solo uno está activo; los anteriores quedan como historial."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="objetivos")
    fecha = models.DateField(default=timezone.localdate)
    peso_inicial = models.DecimalField("peso inicial (kg)", max_digits=5, decimal_places=2, validators=POSITIVO)
    peso_meta = models.DecimalField("peso objetivo (kg)", max_digits=5, decimal_places=2, validators=POSITIVO)
    porcentaje_graso_meta = models.DecimalField(
        "% graso objetivo", max_digits=4, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["cliente"], condition=Q(activo=True), name="un_objetivo_activo_por_cliente"
            )
        ]

    def __str__(self):
        return f"{self.cliente}: {self.peso_inicial} -> {self.peso_meta} kg"

    def save(self, *args, **kwargs):
        nuevo = self.pk is None
        if self.activo:
            # Al activar este objetivo se desactivan los demás del cliente
            Objetivo.objects.filter(cliente=self.cliente, activo=True).exclude(pk=self.pk).update(activo=False)
        super().save(*args, **kwargs)
        if nuevo:
            # El peso inicial también queda como medición para la gráfica de progreso
            ProgresoFisico.objects.create(cliente=self.cliente, fecha=self.fecha, peso=self.peso_inicial)

    def calcular_avance(self):
        """Porcentaje del camino recorrido hacia el peso objetivo (0-100)."""
        actual = self.cliente.peso
        total = self.peso_meta - self.peso_inicial
        if actual is None or total == 0:
            return None
        avance = (actual - self.peso_inicial) / total * 100
        return max(Decimal(0), min(Decimal(100), avance)).quantize(Decimal("0.1"))


class MedidaCorporal(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="medidas_corporales")
    parte = models.CharField(max_length=20, choices=ParteCuerpo.choices)
    fecha = models.DateField(default=timezone.localdate)
    valor_cm = models.DecimalField("medida (cm)", max_digits=5, decimal_places=1, validators=POSITIVO)

    class Meta:
        verbose_name = "medida corporal"
        verbose_name_plural = "medidas corporales"
        ordering = ["parte", "-fecha", "-id"]

    def __str__(self):
        return f"{self.cliente} - {self.get_parte_display()}: {self.valor_cm} cm ({self.fecha})"


# ============================================================
# Mensajes entre usuarios
# ============================================================

class Mensaje(models.Model):
    remitente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="mensajes_enviados")
    destinatario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="mensajes_recibidos")
    texto = models.TextField()
    fecha_envio = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField("leído", default=False)

    class Meta:
        ordering = ["fecha_envio"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(remitente=F("destinatario")), name="mensaje_remitente_distinto_destinatario"
            )
        ]

    def __str__(self):
        return f"{self.remitente} -> {self.destinatario}: {self.texto[:40]}"

    def marcar_como_leido(self):
        self.leido = True
        self.save(update_fields=["leido"])

    @classmethod
    def conversacion(cls, usuario_a, usuario_b):
        """Todos los mensajes entre dos usuarios, en orden."""
        return cls.objects.filter(
            Q(remitente=usuario_a, destinatario=usuario_b) | Q(remitente=usuario_b, destinatario=usuario_a)
        )


# ============================================================
# Diario de comidas y metas nutricionales del cliente
# ============================================================

class RegistroComida(models.Model):
    """Lo que el cliente comió en una fecha y comida (diario de comidas)."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="registros_comida")
    fecha = models.DateField(default=timezone.localdate)
    comida = models.CharField(max_length=20, choices=TipoComida.choices)
    alimento = models.ForeignKey(Alimento, on_delete=models.PROTECT, related_name="registros")
    cantidad_gramos = models.DecimalField("cantidad (g)", max_digits=6, decimal_places=1, validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "registro de comida"
        verbose_name_plural = "registros de comida"
        ordering = ["-fecha", "comida", "id"]

    def __str__(self):
        return f"{self.cliente} - {self.fecha} {self.get_comida_display()}: {self.alimento} {self.cantidad_gramos} g"

    def calcular_macros(self):
        return macros_de(self.alimento, self.cantidad_gramos)


class MetaNutricional(models.Model):
    """Metas diarias del cliente. Una por cliente; se edita cuando quiera."""

    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name="meta_nutricional")
    kcal = models.PositiveIntegerField("calorías (kcal)", default=2000)
    proteinas = models.PositiveIntegerField("proteínas (g)", default=120)
    carbohidratos = models.PositiveIntegerField("carbohidratos (g)", default=220)
    grasas = models.PositiveIntegerField("grasas (g)", default=65)

    class Meta:
        verbose_name = "meta nutricional"
        verbose_name_plural = "metas nutricionales"

    def __str__(self):
        return f"Metas de {self.cliente}: {self.kcal} kcal"

    def calcular_cumplimiento(self, fecha):
        """Porcentaje alcanzado de cada meta en una fecha."""
        totales = self.cliente.totales_del_dia(fecha)
        metas = {"kcal": self.kcal, "proteinas": self.proteinas, "carbohidratos": self.carbohidratos, "grasas": self.grasas}
        return {
            clave: (totales[clave] / meta * 100).quantize(Decimal("0.1")) if meta else None
            for clave, meta in metas.items()
        }
