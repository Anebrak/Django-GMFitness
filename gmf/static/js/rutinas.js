/* =========================================
   GMFitness - Mis rutinas
   Modal "Nueva rutina" (paso 1), menú ⋯ de cada tarjeta y confirmar eliminar.
   Crear, duplicar y eliminar los hace Django (formularios POST).
   abrirModal / cerrarModal vienen de panel.js.
   ========================================= */

/* =========================================
   Referencias al DOM
   ========================================= */
const modalRutina = document.getElementById("modal-rutina");
const formRutina = document.getElementById("form-rutina");
const btnCrearRutina = document.getElementById("btn-crear-rutina");
const btnSiguiente = document.getElementById("btn-siguiente");
const inputNombre = document.getElementById("rutina-nombre");
const selectSemanas = document.getElementById("rutina-semanas");
const contadorNombre = document.getElementById("contador-nombre");

const modalEliminar = document.getElementById("modal-eliminar");
const formEliminar = document.getElementById("form-eliminar");

/* =========================================
   Utilidades
   ========================================= */
function actualizarSiguiente() {
  contadorNombre.textContent = inputNombre.value.length;
  btnSiguiente.disabled = !inputNombre.value.trim() || !selectSemanas.value;
}

function cerrarMenus(excepto) {
  document.querySelectorAll("[data-menu]").forEach((boton) => {
    if (boton === excepto) return;
    boton.setAttribute("aria-expanded", "false");
    boton.nextElementSibling.hidden = true;
  });
}

function abrirNuevaRutina() {
  formRutina.reset();
  // Por defecto: 4 días por semana
  const cuatro = formRutina.querySelector("input[name=dias_por_semana][value='4']");
  if (cuatro) cuatro.checked = true;
  formRutina.querySelectorAll(".error-campo").forEach((p) => p.remove());
  formRutina.querySelectorAll(".con-error").forEach((g) => g.classList.remove("con-error"));
  actualizarSiguiente();
  abrirModal(modalRutina);
}

/* =========================================
   Eventos
   ========================================= */
btnCrearRutina.addEventListener("click", abrirNuevaRutina);
inputNombre.addEventListener("input", actualizarSiguiente);
selectSemanas.addEventListener("change", actualizarSiguiente);
actualizarSiguiente();

// ?nueva=1 (desde "Crear una rutina nueva" en Asignar o el Resumen) abre el modal
if (new URLSearchParams(window.location.search).get("nueva") === "1" && !modalRutina.classList.contains("activo")) {
  abrirNuevaRutina();
}

// Menú ⋯ de cada tarjeta
document.querySelectorAll("[data-menu]").forEach((boton) => {
  boton.addEventListener("click", (e) => {
    e.stopPropagation();
    const menu = boton.nextElementSibling;
    const abrir = menu.hidden;
    cerrarMenus(boton);
    menu.hidden = !abrir;
    boton.setAttribute("aria-expanded", String(abrir));
    if (abrir) menu.querySelector("a, button").focus();
  });
});
document.addEventListener("click", () => cerrarMenus(null));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") cerrarMenus(null);
});

// Eliminar: confirmar en un modal
document.querySelectorAll("[data-eliminar]").forEach((boton) => {
  boton.addEventListener("click", () => {
    formEliminar.action = boton.dataset.eliminar;
    document.getElementById("nombre-eliminar").textContent = boton.dataset.nombre;
    abrirModal(modalEliminar);
  });
});
