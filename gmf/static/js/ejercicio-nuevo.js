/* =========================================
   GMFitness - modal "Crear ejercicio nuevo"
   Se usa en Ejercicios (POST normal) y en el constructor de rutinas
   (data-modo="fetch": se envía por JSON y constructor.js recibe el ejercicio creado).
   abrirModal / cerrarModal vienen de panel.js.
   ========================================= */

/* =========================================
   Referencias al DOM
   ========================================= */
const modalEjercicio = document.getElementById("modal-ejercicio");
const formEjercicio = document.getElementById("form-ejercicio");
const ejNombre = document.getElementById("ej-nombre");
const ejBorrarNombre = document.getElementById("ej-borrar-nombre");
const ejCrear = document.getElementById("ej-crear");
const ejEstado = document.getElementById("ej-estado");
const ejContadorMusculos = document.getElementById("ej-contador-musculos");
const btnNuevoEjercicio = document.getElementById("btn-nuevo-ejercicio");

/* =========================================
   Estado
   ========================================= */
// constructor.js pone aquí la función que recibe el ejercicio creado
let alCrearEjercicio = null;

/* =========================================
   Utilidades
   ========================================= */
function faltantesEjercicio() {
  const faltan = [];
  if (!ejNombre.value.trim()) faltan.push("nombre");
  if (!formEjercicio.querySelector("input[name=tipo_objetivo]:checked")) faltan.push("tipo de objetivo");
  if (!formEjercicio.querySelector("input[name=equipo]:checked")) faltan.push("equipo");
  if (!formEjercicio.querySelector("input[name=musculos]:checked")) faltan.push("grupo muscular");
  return faltan;
}

function actualizarEjercicio() {
  const faltan = faltantesEjercicio();
  ejContadorMusculos.textContent = formEjercicio.querySelectorAll("input[name=musculos]:checked").length;
  ejCrear.disabled = faltan.length > 0;
  ejEstado.className = faltan.length ? "texto-naranja-claro" : "texto-gris";
  ejEstado.textContent = faltan.length
    ? `Falta: ${faltan.join(", ")}.`
    : formEjercicio.dataset.modo === "fetch"
      ? "Se guardará en tu biblioteca y se añadirá al día actual."
      : "Se guardará en tu biblioteca.";
}

function mostrarErroresEjercicio(errores) {
  formEjercicio.querySelectorAll("[data-error]").forEach((p) => {
    const lista = errores[p.dataset.error] || [];
    p.textContent = lista.join(" ");
    p.closest(".grupo-campo").classList.toggle("con-error", lista.length > 0);
  });
}

function abrirModalEjercicio(nombreInicial) {
  formEjercicio.reset();
  mostrarErroresEjercicio({});
  if (nombreInicial) ejNombre.value = nombreInicial;
  actualizarEjercicio();
  abrirModal(modalEjercicio);
}

/* =========================================
   Eventos
   ========================================= */
formEjercicio.addEventListener("input", actualizarEjercicio);
formEjercicio.addEventListener("change", actualizarEjercicio);

ejBorrarNombre.addEventListener("click", () => {
  ejNombre.value = "";
  ejNombre.focus();
  actualizarEjercicio();
});

if (btnNuevoEjercicio) btnNuevoEjercicio.addEventListener("click", () => abrirModalEjercicio());

formEjercicio.addEventListener("submit", async (e) => {
  if (formEjercicio.dataset.modo !== "fetch") return; // POST normal
  e.preventDefault();
  ejCrear.disabled = true;
  try {
    const respuesta = await fetch(formEjercicio.action, {
      method: "POST",
      body: new FormData(formEjercicio),
      headers: { Accept: "application/json" },
    });
    const datos = await respuesta.json();
    if (!datos.ok) {
      mostrarErroresEjercicio(datos.errores || {});
      actualizarEjercicio();
      return;
    }
    cerrarModal(modalEjercicio);
    if (alCrearEjercicio) alCrearEjercicio(datos.ejercicio);
  } catch (error) {
    ejEstado.className = "texto-rojo";
    ejEstado.textContent = "No se pudo guardar. Revisa tu conexión e inténtalo de nuevo.";
    ejCrear.disabled = false;
  }
});

actualizarEjercicio();
