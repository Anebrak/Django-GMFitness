/* =========================================
   Navegación entre páginas
   Las URLs vienen de Django (window.GMF_RUTAS, definido en base.html con {% url %}),
   así que no se escriben rutas a mano en este archivo.
   ========================================= */
const RUTAS = window.GMF_RUTAS || {};

const rutasNavegacion = {
  // Tarjetas del inicio
  "of-1": RUTAS.rutinas,
  "of-2": RUTAS.dietas,
  "of-3": RUTAS.cliente + "#mediciones",
  "of-4": RUTAS.cliente + "#objetivos",
  // Tarjetas del menú del cliente
  "menu-1": RUTAS.rutinas,
  "menu-2": RUTAS.dietas,
  "menu-3": RUTAS.cliente + "#mediciones",
  "menu-4": RUTAS.cliente + "#mensajes",
  // Botones del inicio (solo diseño: todavía no inician sesión ni cobran)
  "btn-gratis": RUTAS.cliente,
  "btn-premium": RUTAS.cliente,
  "ingreso-login": RUTAS.cliente,
};

function navegarA(ruta) {
  if (!ruta) return;
  const destino = new URL(ruta, window.location.href);

  // Misma página: solo se cambia de vista (si hay #vista), sin recargar
  if (destino.pathname === window.location.pathname) {
    const nombre = destino.hash.slice(1);
    const vista = nombre && document.querySelector(`[data-vista="${nombre}"]`);
    if (vista) vista.click();
    return;
  }
  window.location.href = destino.href;
}

function hacerNavegable(elemento, ruta) {
  elemento.setAttribute("role", "link");
  elemento.setAttribute("tabindex", "0");
  elemento.addEventListener("click", () => navegarA(ruta));
  elemento.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" || evento.key === " ") {
      evento.preventDefault();
      navegarA(ruta);
    }
  });
}

// En la página del cliente el botón "Pásate a Premium" abre un modal, no navega
const enPaginaCliente = window.location.pathname === new URL(RUTAS.cliente || "/", window.location.href).pathname;

Object.entries(rutasNavegacion).forEach(([id, ruta]) => {
  const elemento = document.getElementById(id);
  if (!elemento) return;
  if (enPaginaCliente && id === "btn-premium") return;
  hacerNavegable(elemento, ruta);
});

const logo = document.querySelector("header nav h1");
if (logo) hacerNavegable(logo, RUTAS.inicio);

const usuario = document.getElementById("usuario-bola");
if (usuario) hacerNavegable(usuario, RUTAS.cliente);

// Abrir la vista indicada en la URL (ej. /cliente/#mediciones)
const destinoInicial = window.location.hash.slice(1);
const vistaInicial = destinoInicial && document.querySelector(`[data-vista="${destinoInicial}"]`);
if (vistaInicial) vistaInicial.click();
