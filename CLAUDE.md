# GMFitness — contexto del proyecto

## Qué es
Aplicación web para gimnasios que no tienen un sistema propio. Conecta a los clientes con
profesionales (entrenadores, nutricionistas y fisioterapeutas) para gestionar rutinas, dietas,
citas, progreso físico, membresías y pagos. Los clientes también pueden crear sus propias
rutinas y dietas.

- **Contexto:** proyecto académico.
- **Despliegue:** una instalación (y una base de datos) por gimnasio. `Sede` representa las
  sedes de ese gimnasio; no hay modelo `Gimnasio`.

## Stack
- Python + Django 6.1.2, python-dotenv, whitenoise (ver `requirements.txt`).
- Base de datos: SQLite (también en producción).
- Frontend: plantillas de Django (`gmf/templates/gmf/`) con Bootstrap y Font Awesome por CDN;
  CSS en `gmf/static/gmf/css/` y JS en `gmf/static/gmf/js/` (ver "Pantallas").
- Idioma: interfaz, modelos y comentarios en español. `LANGUAGE_CODE = 'es-co'`,
  `TIME_ZONE = 'America/Bogota'`.

## Estructura
```
config/          settings, urls raíz (solo reparten rutas), wsgi/asgi
docs/            diagrama de clases
gmf/             única app: models, admin, views, urls (namespace "gmf"), templates, static
.env             SECRET_KEY, DEBUG, ALLOWED_HOSTS (no se versiona)
```

## Comandos
```
python manage.py runserver
python manage.py makemigrations gmf
python manage.py migrate
python manage.py createsuperuser     # pide email, número de identidad, nombre y apellido
python manage.py check
```

## Modelo de datos
Fuente de verdad: el diagrama de clases **`docs/Diagrama de clases GMF v3.drawio`**
(se abre en app.diagrams.net). En el diagrama `[0..1]` indica un campo opcional. Si cambia el
modelo, se actualizan juntos el diagrama, `models.py`, `admin.py` y las migraciones.

### Decisiones tomadas (no cambiar sin consultarlo)
- **Usuario:** `gmf.Usuario` hereda de `AbstractUser` (`AUTH_USER_MODEL = 'gmf.Usuario'`).
  Se inicia sesión con el **email** (no hay `username`). Equivalencias con el diagrama:
  nombre → `first_name`, apellido → `last_name`, contraseña → `password` (cifrada por Django),
  activo → `is_active`, fechaRegistro → `date_joined`.
- `fecha_nacimiento` y `telefono` son opcionales. `sede` es opcional.
- **Roles:** campo `Usuario.rol`. Cliente, Entrenador, Nutricionista y Fisioterapeuta son
  **perfiles 1 a 1** (`OneToOneField` a Usuario, limitados por rol).
- **Administrador** y **Recepcionista** no tienen tabla: son Usuarios con `rol=ADMINISTRADOR`
  o `rol=RECEPCIONISTA` e `is_staff=True`.
- **Profesional** es un modelo abstracto (`PerfilProfesional`): no crea tabla.
- **Disponibilidad** pertenece solo al Fisioterapeuta. **Las citas son solo con fisioterapeuta.**
- **Membresías:** planes **Gratis** y **Premium**. Gratis no es una membresía: un cliente sin
  suscripción vigente está en Gratis (`Cliente.plan` devuelve `GRATIS` o `PREMIUM`).
  `Membresia` es el catálogo (solo tipo PREMIUM, duración MENSUAL o ANUAL); `Suscripcion` es la
  compra del cliente (si no se da `fecha_fin`, se calcula con la duración). Suscripción 1—* Pago,
  Pago 1—0..1 Factura. Los límites del plan Gratis (máx. 2 rutinas/dietas activas, editar 1 vez
  por semana...) **se programan en las vistas**, no en el modelo.
- **Rutinas y dietas:** son plantillas que crea **cualquier usuario** (`autor`), con
  `visibilidad` PRIVADA/PUBLICA y `copia_de` (se pueden duplicar con `duplicar()`).
  `Rutina` tiene `nivel` y `semanas`; `RutinaEjercicio` ubica cada ejercicio en una **semana y un
  día**, con tipo de repeticiones (MAXIMAS / RANGO / AMRAP, con `repeticiones_min`/`max`) y
  esfuerzo (RIR con valor 0-10, o ARM). `DietaAlimento` guarda gramos y tipo de comida.
- **Asignaciones:** `AsignacionRutina` / `AsignacionDieta` unen cliente + plantilla + fechas.
  El profesional es opcional: vacío = el cliente se la asignó a sí mismo.
- **Dietas del cliente:** además de las dietas plantilla, el cliente lleva un **diario de
  comidas** (`RegistroComida`: fecha, comida, alimento, gramos) y sus **metas diarias**
  (`MetaNutricional`, una por cliente). Tipos de comida: desayuno, almuerzo y cena.
- **Alimentos:** kcal y macros siempre **por cada 100 g**; `porcion_gramos` es la porción típica
  sugerida (con `porcion_nombre`, ej. "1 unidad") y el usuario escribe los gramos que comió.
  Tienen `categoria` (texto libre) e `imagen_url`. Ejercicio tiene `maquina` e `imagen_url`.
  Las imágenes se guardan como URL (no se suben archivos).
- **Medidas:** `Cliente` guarda peso, altura y % graso actuales (opcionales);
  `ProgresoFisico` guarda el historial (solo el peso es obligatorio). Al guardar la medición más
  reciente se actualiza el Cliente; los valores vacíos conservan el anterior.
  Unidades: peso en kg, **altura en cm** (175), medidas corporales en cm.
- **Objetivo:** peso inicial, peso meta y % graso meta. Solo uno activo por cliente; al crearlo
  se registra también un `ProgresoFisico` con el peso inicial.
- **MedidaCorporal:** historial por parte del cuerpo (cuello, hombros, pecho, brazo, cintura,
  cadera, muslo, pantorrilla), en cm.
- **Mensaje:** chat entre dos usuarios (remitente, destinatario). `Notificacion` es otra cosa:
  avisos del sistema (ej. recordatorio de cita).
- **ProgresoEjercicio:** registro de peso y repeticiones; series y asignación son opcionales
  (se puede registrar fuera de una rutina asignada).
- **Atributos derivados** del diagrama (`/numClientes`, `/kcalTotales`...) son `@property`.
- **Borrado:** CASCADE en partes (detalle de rutina/dieta, disponibilidad, progreso del
  cliente), PROTECT en dinero, historial y catálogos, SET_NULL en relaciones opcionales.
- **Convenciones:** modelos en singular, campos en `snake_case`, enumeraciones con
  `TextChoices`/`IntegerChoices`. IVA en la constante `TASA_IVA` de `models.py`.

## Pantallas (diseño)
Vienen del repositorio de diseño **GMFitness-diseno** y ya están integradas como plantillas de
Django, **solo en lo visual**: el JS guarda los datos en el navegador (localStorage) y todavía no
lee ni escribe en la base de datos.

| URL | Vista / plantilla | CSS y JS (`gmf/static/gmf/`) |
|---|---|---|
| `/` | `inicio` → `inicio.html` (landing, login y registro) | `css/estilos.css`, `js/botones.js` |
| `/cliente/` | `cliente` → `cliente.html` (menú, objetivos, mediciones, membresía, mensajes) | `css/cliente.css`, `js/cliente.js` |
| `/rutinas/` | `rutinas` → `rutinas.html` | `css/rutinas.css`, `js/rutinas.js` |
| `/dietas/` | `dietas` → `dietas.html` (diario de comidas y alimentos) | `css/dietas.css`, `js/dietas.js` |
| `/panel/` | `panel` → `panel.html` (empleados, clientes, sedes) | `css/panel.css`, `js/panel.js` |

- `base.html` carga Bootstrap 5.3.8 y Font Awesome 6.5.1 por CDN y define `window.GMF_RUTAS`
  con `{% url %}`; `js/navegacion.js` usa esas rutas (no escribir URLs a mano en el JS).
- `base_app.html` es la base de cliente, rutinas y dietas (encabezado + barra lateral).
  `panel.html` e `inicio.html` extienden `base.html` directamente.
- Las vistas internas se abren con `#vista` en la URL, ej. `/cliente/#mediciones`.
- `/panel/` es el panel propio del gimnasio; `/admin/` sigue siendo el admin de Django.

Pendiente:
- Conectar las pantallas a la base de datos (login/registro reales, rutinas, dietas,
  mediciones, mensajes, panel) y proteger las páginas internas y `/panel/` con login y rol.
- No hay pantallas para: citas con fisioterapeuta, vistas del profesional (crear/asignar
  rutinas y dietas), pagos y facturas.

## Forma de trabajar con Claude
- **Preguntar antes de asumir.** Antes de crear o modificar algo, consultar las decisiones
  con el usuario; no crear cosas y pedir correcciones después.
- Respaldar (`.bak`) los archivos existentes antes de reemplazarlos.
- Responder en español.
