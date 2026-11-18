/* =========================================
   GMFitness - panel del entrenador
   Mis clientes y Detalle del cliente: modal "Asignar rutina", modal "Registrar peso"
   y edición del historial de cargas (con los indicadores recalculados en vivo).
   abrirModal / cerrarModal vienen de panel.js.
   ========================================= */

/* =========================================
   Referencias al DOM
   ========================================= */
const modalAsignar = document.getElementById("modal-asignar");
const formAsignar = document.getElementById("form-asignar");
const buscarRutina = document.getElementById("buscar-rutina");
const selectSemana = document.getElementById("asignar-semana");
const btnAsignar = document.getElementById("btn-asignar");
const avisoReemplazo = document.getElementById("aviso-reemplazo");

const modalPeso = document.getElementById("modal-peso");
const btnRegistrarPeso = document.getElementById("btn-registrar-peso");

const cajaCargas = document.getElementById("historial-cargas");
const formCargas = document.getElementById("form-cargas");
const btnEditarCargas = document.getElementById("btn-editar-cargas");
const btnCancelarCargas = document.getElementById("btn-cancelar-cargas");

/* =========================================
   Estado
   ========================================= */
let rutinaActual = ""; // id de la rutina vigente del cliente elegido
let textoActual = "";

/* =========================================
   Utilidades
   ========================================= */
function numero(texto) {
  const valor = parseFloat(String(texto).replace(",", "."));
  return Number.isFinite(valor) ? valor : null;
}

function formatoKg(valor) {
  return (Math.round(valor * 10) / 10).toLocaleString("es-CO", { maximumFractionDigits: 1 });
}

/* =========================================
   Modal "Asignar rutina"
   ========================================= */
function opcionesRutina() {
  return formAsignar ? Array.from(formAsignar.querySelectorAll(".opcion-rutina")) : [];
}

function rutinaElegida() {
  const radio = formAsignar.querySelector("input[name=rutina]:checked");
  return radio ? radio.closest(".opcion-rutina") : null;
}

function llenarSemanas(total) {
  const anterior = selectSemana.value || selectSemana.dataset.valor || "1";
  selectSemana.innerHTML = "";
  for (let n = 1; n <= total; n += 1) {
    const opcion = document.createElement("option");
    opcion.value = String(n);
    opcion.textContent = `Semana ${n}`;
    selectSemana.appendChild(opcion);
  }
  selectSemana.value = Number(anterior) <= total ? anterior : "1";
}

function actualizarAsignar() {
  const elegida = rutinaElegida();
  llenarSemanas(elegida ? Number(elegida.dataset.semanas) : 1);
  btnAsignar.disabled = !elegida;
  btnAsignar.textContent = elegida ? `Asignar «${elegida.dataset.titulo}»` : "Elige una rutina";
  // Aviso solo si se reemplaza una rutina distinta a la actual
  const reemplaza = Boolean(elegida && rutinaActual && elegida.dataset.id !== rutinaActual);
  avisoReemplazo.hidden = !reemplaza;
  if (reemplaza) document.getElementById("aviso-actual").textContent = textoActual;
}

function prepararAsignar(boton) {
  formAsignar.action = boton.dataset.url;
  rutinaActual = boton.dataset.actual || "";
  textoActual = boton.dataset.actualTexto || "";
  document.getElementById("asignar-nombre").textContent = boton.dataset.nombre;
  document.getElementById("asignar-iniciales").textContent = boton.dataset.iniciales;
  document.getElementById("asignar-nombre-corto").textContent = boton.dataset.nombreCorto;
  formAsignar.querySelectorAll(".nombre-aviso").forEach((n) => (n.textContent = boton.dataset.nombreCorto));
  opcionesRutina().forEach((opcion) => {
    opcion.querySelector("[data-marca-actual]").hidden = opcion.dataset.id !== rutinaActual;
  });
}

function abrirAsignar(boton) {
  prepararAsignar(boton);
  formAsignar.querySelectorAll("input[name=rutina]").forEach((r) => (r.checked = false));
  if (buscarRutina) buscarRutina.value = "";
  opcionesRutina().forEach((o) => (o.hidden = false));
  selectSemana.value = "1";
  actualizarAsignar();
  abrirModal(modalAsignar);
}

/* =========================================
   Historial de cargas
   ========================================= */
function seriesDeLaTabla() {
  // Lee las series (kg, reps) de cada fila, en el orden de la tabla (más reciente primero)
  return Array.from(document.querySelectorAll("#tabla-cargas [data-fila]")).map((fila) =>
    Array.from(fila.querySelectorAll(".celda-serie")).map((celda) => ({
      kg: numero(celda.querySelector(".input-kg").value),
      reps: numero(celda.querySelector(".input-reps").value),
    }))
  );
}

function recalcularIndicadores() {
  const filas = seriesDeLaTabla();
  const todas = filas.flat().filter((s) => s.kg !== null && s.reps !== null);
  if (!todas.length) return;

  // Mejor serie: mayor kg; si empatan, más repeticiones
  const mejor = todas.reduce((a, b) => (b.kg > a.kg || (b.kg === a.kg && b.reps > a.reps) ? b : a));
  document.getElementById("kpi-mejor").textContent = `${formatoKg(mejor.kg)} kg × ${mejor.reps}`;

  // 1RM estimado con Epley: kg × (1 + reps / 30)
  const rm = Math.max(...todas.map((s) => s.kg * (1 + s.reps / 30)));
  document.getElementById("kpi-rm").textContent = `${formatoKg(rm)} kg`;

  if (filas.length > 1) {
    const maxKg = (fila) => Math.max(...fila.filter((s) => s.kg !== null).map((s) => s.kg));
    const progreso = maxKg(filas[0]) - maxKg(filas[filas.length - 1]);
    const signo = progreso > 0 ? "+" : progreso < 0 ? "−" : "";
    document.getElementById("kpi-progreso").textContent = `${signo}${formatoKg(Math.abs(progreso))} kg`;
  }

  // Volumen de cada fila = Σ kg × reps
  document.querySelectorAll("#tabla-cargas [data-fila]").forEach((fila, i) => {
    const volumen = filas[i].reduce((total, s) => total + (s.kg || 0) * (s.reps || 0), 0);
    fila.querySelector("[data-volumen]").textContent = `${formatoKg(volumen)} kg`;
  });
}

function modoEdicion(activo) {
  cajaCargas.classList.toggle("modo-edicion", activo);
  cajaCargas.classList.toggle("modo-vista", !activo);
  formCargas.querySelectorAll(".celda-serie input").forEach((input) => {
    input.disabled = !activo;
    if (!activo) input.value = input.dataset.original; // Cancelar restaura los valores
  });
  if (!activo) recalcularIndicadores();
  if (activo) {
    const primero = formCargas.querySelector(".celda-serie input");
    if (primero) primero.focus();
  } else if (btnEditarCargas) {
    btnEditarCargas.focus();
  }
}

/* =========================================
   Eventos
   ========================================= */
document.querySelectorAll("[data-asignar]").forEach((boton) => {
  boton.addEventListener("click", () => abrirAsignar(boton));
});

if (formAsignar) {
  formAsignar.addEventListener("change", (e) => {
    if (e.target.name === "rutina") actualizarAsignar();
  });

  if (buscarRutina) {
    buscarRutina.addEventListener("input", () => {
      const texto = buscarRutina.value.trim().toLowerCase();
      opcionesRutina().forEach((opcion) => {
        opcion.hidden = Boolean(texto) && !opcion.dataset.nombre.includes(texto);
      });
    });
  }

  // Si Django volvió a abrir el modal con errores: tomar los datos del botón de la página
  if (modalAsignar.classList.contains("activo")) {
    const boton = document.querySelector("[data-asignar]");
    if (boton) prepararAsignar(boton);
    actualizarAsignar();
    selectSemana.value = selectSemana.dataset.valor;
  }
}

if (btnRegistrarPeso) {
  btnRegistrarPeso.addEventListener("click", () => abrirModal(modalPeso));
}

if (btnEditarCargas) {
  btnEditarCargas.addEventListener("click", () => modoEdicion(true));
  btnCancelarCargas.addEventListener("click", () => modoEdicion(false));
  formCargas.addEventListener("input", (e) => {
    if (e.target.matches(".celda-serie input")) recalcularIndicadores();
  });
}
