/* =========================================
   GMFitness - comportamiento común (todas las páginas)
   ========================================= */

/* =========================================
   Referencias al DOM
   ========================================= */
const btnMenu = document.getElementById("btn-menu");
const menuSecciones = document.getElementById("menu-secciones");
const mensajes = document.querySelectorAll(".mensaje");

/* =========================================
   Utilidades
   ========================================= */
function ocultarMensaje(mensaje) {
  mensaje.classList.add("oculto");
  setTimeout(() => mensaje.remove(), 300);
}

/* =========================================
   Eventos
   ========================================= */

// Menú de secciones en celular
if (btnMenu && menuSecciones) {
  btnMenu.addEventListener("click", () => {
    const abierto = menuSecciones.classList.toggle("abierto");
    btnMenu.setAttribute("aria-expanded", String(abierto));
  });

  // Al elegir una sección se cierra el menú
  menuSecciones.addEventListener("click", (evento) => {
    if (evento.target.closest("a")) {
      menuSecciones.classList.remove("abierto");
      btnMenu.setAttribute("aria-expanded", "false");
    }
  });
}

// Mensajes: se cierran con la X o solos a los 6 segundos
mensajes.forEach((mensaje) => {
  mensaje.querySelector(".mensaje-cerrar").addEventListener("click", () => ocultarMensaje(mensaje));
  setTimeout(() => ocultarMensaje(mensaje), 6000);
});
