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
- Frontend: plantillas de Django en `gmf/templates/` (las del panel en `gmf/templates/panel/`),
  CSS en `gmf/static/css/` y JS en `gmf/static/js/` (ver "Pantallas").
- Idioma: interfaz, modelos y comentarios en español. `LANGUAGE_CODE = 'es-co'`,
  `TIME_ZONE = 'America/Bogota'`.

## Estructura
```
config/          settings, urls raíz (solo reparten rutas), wsgi/asgi
docs/            diagrama de clases
gmf/             única app: models, admin, views (sitio), views_panel (panel), urls, templates, static
.env             SECRET_KEY, DEBUG, ALLOWED_HOSTS (no se versiona)
```

## Comandos
```
python manage.py runserver
python manage.py makemigrations gmf
python manage.py migrate
python manage.py createsuperuser     # pide email, nombre, apellido y contraseña
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
- No hay número de identidad (se quitó: no se usa). `fecha_nacimiento`, `telefono` y `sede`
  son opcionales. `Cliente.sexo` es opcional: no se pide en el registro, se completa después.
- **Roles:** campo `Usuario.rol`. Cliente, Entrenador, Nutricionista y Fisioterapeuta son
  **perfiles 1 a 1** (`OneToOneField` a Usuario, limitados por rol).
- **Administrador** y **Recepcionista** no tienen tabla: son Usuarios con `rol=ADMINISTRADOR`
  o `rol=RECEPCIONISTA`. Los administradores tienen `is_staff` e `is_superuser` (entran al panel
  y a /admin/); los recepcionistas no. Administradores actuales: dmartinezs319@gmail.com y
  dmartinez@soy.sena.edu.co.
- **Profesional** es un modelo abstracto (`PerfilProfesional`): no crea tabla.
- **Disponibilidad** pertenece solo al Fisioterapeuta. **Las citas son solo con fisioterapeuta.**
- **Membresías:** planes **Gratis** y **Premium**. Gratis no es una membresía: un cliente sin
  suscripción vigente está en Gratis (`Cliente.plan` devuelve `GRATIS` o `PREMIUM`).
  `Membresia` es el catálogo (solo tipo PREMIUM, duración MENSUAL o ANUAL); `Suscripcion` es la
  compra del cliente (si no se da `fecha_fin`, se calcula con la duración). La migración 0003
  crea el **Premium mensual de $89.000** ("se paga mensualmente"); el precio se cambia en el panel (Membresías). Suscripción 1—* Pago,
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
- **Catálogos:** `Ejercicio` y `Alimento` tienen `activo` (migración 0004). Nada se borra desde
  el panel: usuarios, sedes, membresías, ejercicios y alimentos se **desactivan**. Los
  inactivos no deben ofrecerse en rutinas/dietas nuevas.
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

## Pantallas
**Se están rehaciendo desde cero** (las anteriores se borraron), una pantalla a la vez y
**conectadas a la base de datos** (login, registro y vistas que leen y guardan en los modelos).

Referencia obligatoria: el repositorio de diseño **GMFitness-diseno** (.zip), del que se toman:
- **Colores:** la paleta de `:root` (naranja `#fe6c05` como acento; azules `#0f111f`, `#1e223e`,
  `#262b4e`; blanco y gris `#9699ae` para texto; escalas 100-900 de cada color).
- **Estructura del código:** ids y clases en español con guiones (`barra-lateral`,
  `modal-overlay`, `boton-primario`); un CSS y un JS por página en `gmf/static/css|js/`;
  JS sin librerías organizado en bloques comentados (Utilidades, Datos, Estado, Referencias al
  DOM, Eventos); patrones de barra lateral, vistas y modales. Bootstrap y Font Awesome por CDN.

El diseño de cada pantalla es nuevo: se propone, el usuario lo revisa y se sigue con la siguiente.

Organización (la que dejó el usuario; seguirla):
- **Vistas como funciones** con la validación escrita en la vista (no se usa `forms.py`).
  Errores como `{"campo": ["mensaje"]}` y los valores escritos se devuelven a la plantilla.
- **URLs sin `app_name`**: `{% url 'inicio' %}`, `redirect("panel")`.
- Plantillas en `gmf/templates/` y estáticos en `gmf/static/css|js/` (sin subcarpeta `gmf/`).
- La paleta y los estilos comunes (encabezado, botones, mensajes) están una sola vez en
  `css/base.css`; cada página tiene su CSS (`inicio.css`, `cuenta.css`, `panel.css`). Igual con el
  JS: `js/base.js` (menú en celular, mensajes) y uno por página.
- Filtros de plantilla en `gmf/templatetags/gmf_extras.py`: `pesos` → "$89.000", `iniciales`,
  `dato` (leer un diccionario: `valores|dato:"email"`).
- Campos del sitio con `{% include "_campo.html" with nombre="email" etiqueta="Correo" ... %}`.

### Hechas
| URL | Qué hace | Archivos |
|---|---|---|
| `/` | Inicio: portada, lo que ofrecemos, planes (Gratis + membresías Premium activas), profesionales activos y sedes activas. Arriba a la derecha: Ingresar / Registrarse, o el usuario y Salir | `inicio.html`, `inicio.css` |
| `/ingresar/` | Login con correo y contraseña (vista `ingresar`) | `ingresar.html`, `cuenta.css`, `cuenta.js` |
| `/registro/` | Pide nombre, apellido, correo y contraseña; crea Usuario (rol CLIENTE) + Cliente e inicia sesión (vista `registro`) | `registro.html`, `cuenta.css`, `cuenta.js` |
| `/salir/` | Cierra sesión (solo POST, por seguridad) | botón en `base.html` |
| `/panel/...` | Panel de administración (ver abajo) | `views_panel.py`, `templates/panel/`, `panel.css`, `panel.js` |

Después de ingresar: el administrador va a `/panel/` (si no hay `?next=`); los demás al inicio.
En el encabezado, los administradores ven un botón "Panel". Para usuarios con sesión los botones Premium dicen "Pago en línea muy
pronto". Pruebas en `gmf/tests.py` (`python manage.py test gmf`).

### Panel de administración (`/panel/`)
Solo rol ADMINISTRADOR (decorador `solo_administradores` en `views_panel.py`; los demás vuelven
al inicio con un aviso). Barra lateral (se contrae y lo recuerda en el navegador) con:
Resumen · Empleados · Clientes · Sedes · Membresías · Ejercicios · Alimentos · Ver el sitio.

- **Resumen:** clientes activos, Premium, nuevos del mes, ingresos del mes (pagos aprobados),
  empleados activos, sedes activas, últimos clientes, equipo por rol y planes a la venta.
- **Secciones con tabla:** búsqueda, filtros (estado y uno propio: rol, plan, grupo muscular,
  categoría), paginación de 10 y una **ventana modal** para agregar/editar. El mismo POST a
  `/panel/<seccion>/` crea (sin `id`) o edita (con `id`); si hay errores la página se vuelve a
  dibujar con el modal abierto (status 400). Los campos de cada formulario se describen una vez
  (`CAMPOS_...` / `campos_empleado()`) y sirven para dibujar y para validar (`validar()`).
- **Desactivar/activar:** `POST /panel/<seccion>/<id>/estado/` (con `activar=1` para activar).
  Nadie puede desactivar su propia cuenta. Solo una membresía activa por tipo y duración.
- **Empleados:** rol fijo (se elige al crear: entrenador, nutricionista, fisioterapeuta,
  recepcionista o administrador); los profesionales necesitan especialidad.
- **Clientes:** el plan (Gratis/Premium) solo se ve; se activará con los pagos.
- **Contraseñas:** al crear un usuario o con el botón de llave se genera una **contraseña
  temporal** (`POST /panel/usuarios/<id>/clave/`), que se muestra **una sola vez** (va en la
  sesión y se borra al mostrarla).

### Siguientes
Panel del cliente, rutinas, dietas; citas, vistas del profesional, pagos y facturas (y desde
ahí activar Premium en el panel).

## Forma de trabajar con Claude
- **Preguntar antes de asumir.** Antes de crear o modificar algo, consultar las decisiones
  con el usuario; no crear cosas y pedir correcciones después.
- Respaldar (`.bak`) los archivos existentes antes de reemplazarlos.
- Responder en español.
