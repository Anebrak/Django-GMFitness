/* =========================================
   GMFitness - panel de administración
   Barra lateral, filtros, modales de agregar/editar y confirmaciones.
   Guardar, activar y desactivar los hace Django (formularios POST).
   ========================================= */

/* =========================================
   Referencias al DOM
   ========================================= */
const barraLateral = document.getElementById("barra-lateral");
const btnToggle = document.getElementById("btn-toggle");
const formHerramientas = document.getElementById("herramientas");

const modalForm = document.getElementById("modal-form");
const formulario = document.getElementById("formulario");
const tituloForm = document.getElementById("titulo-form");
const campoId = document.getElementById("campo-id");
const btnAgregar = document.getElementById("btn-agregar");

const modalConfirmar = document.getElementById("modal-confirmar");
const formConfirmar = document.getElementById("form-confirmar");
const tituloConfirmar = document.getElementById("titulo-confirmar");
const textoConfirmar = document.getElementById("texto-confirmar");
const btnConfirmar = document.getElementById("btn-confirmar");

const btnCopiarClave = document.getElementById("btn-copiar-clave");

/* =========================================
   Datos
   ========================================= */
// Registros de la página actual (los pone Django con json_script)
function leerJson(id, porDefecto) {
  const nodo = document.getElementById(id);
  return nodo ? JSON.parse(nodo.textContent) : porDefecto;
}

const registros = leerJson("datos-registros", []);
const rolesProfesional = leerJson("roles-profesional", []);

/* =========================================
   Estado
   ========================================= */
let ultimoFoco = null; // para devolver el foco al cerrar un modal

/* =========================================
   Utilidades
   ========================================= */
function guardarPreferencia(clave, valor) {
  try {
    localStorage.setItem(clave, valor);
  } catch (e) {
    /* sin almacenamiento: no se recuerda, no pasa nada */
  }
}

function abrirModal(modal) {
  ultimoFoco = document.activeElement;
  modal.classList.add("activo");
  modal.setAttribute("aria-hidden", "false");
  const primero = modal.querySelector(
    "input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea, button.boton-primario"
  );
  if (primero) setTimeout(() => primero.focus(), 50);
}

function cerrarModal(modal) {
  modal.classList.remove("activo");
  modal.setAttribute("aria-hidden", "true");
  if (ultimoFoco) ultimoFoco.focus();
}

function grupoDe(nombre) {
  const input = formulario.elements[nombre];
  return input ? input.closest(".grupo-campo") : null;
}

// Muestra los campos de especialidad solo para entrenador, nutricionista y fisioterapeuta
function mostrarCamposProfesional(rol) {
  const esProfesional = rolesProfesional.includes(rol);
  formulario.querySelectorAll("[data-solo-profesional]").forEach((grupo) => {
    grupo.hidden = !esProfesional;
  });
}

function limpiarErrores() {
  formulario.querySelectorAll(".error-campo").forEach((p) => p.remove());
  formulario.querySelectorAll(".con-error").forEach((g) => g.classList.remove("con-error"));
}

function llenarFormulario(registro) {
  formulario.reset();
  limpiarErrores();
  Array.from(formulario.elements).forEach((input) => {
    if (!input.name || input.type === "hidden" || input.type === "submit" || input.type === "button") return;
    const valor = registro ? registro[input.name] : undefined;
    if (input.type === "checkbox") {
      // Al agregar, los interruptores de "activo" empiezan encendidos
      input.checked = registro ? Boolean(valor) : true;
    } else {
      input.value = valor === undefined || valor === null ? "" : String(valor);
    }
  });
}

/* =========================================
   Formulario: agregar y editar
   ========================================= */
function abrirAgregar() {
  llenarFormulario(null);
  campoId.value = "";
  tituloForm.textContent = tituloForm.dataset.agregar;
  formulario.querySelectorAll("[data-solo-crear]").forEach((grupo) => (grupo.hidden = false));
  const rol = formulario.elements.rol;
  if (rol) {
    rol.disabled = false;
    mostrarCamposProfesional(rol.value);
  }
  abrirModal(modalForm);
}

function abrirEditar(id) {
  const registro = registros.find((r) => String(r.id) === String(id));
  if (!registro) return;
  llenarFormulario(registro);
  campoId.value = registro.id;
  tituloForm.textContent = tituloForm.dataset.editar;
  // El rol no se cambia al editar
  formulario.querySelectorAll("[data-solo-crear]").forEach((grupo) => (grupo.hidden = true));
  if (formulario.elements.rol) {
    formulario.elements.rol.disabled = true;
    mostrarCamposProfesional(registro.rol);
  }
  abrirModal(modalForm);
}

/* =========================================
   Eventos
   ========================================= */

// Barra lateral: abrir / contraer (se recuerda en este navegador)
btnToggle.addEventListener("click", () => {
  const abierta = barraLateral.classList.toggle("expandida");
  btnToggle.setAttribute("aria-expanded", String(abierta));
  if (window.innerWidth > 768) guardarPreferencia("gmf-barra", abierta ? "abierta" : "contraida");
});
btnToggle.setAttribute("aria-expanded", String(barraLateral.classList.contains("expandida")));

// En celular, tocar fuera de la barra abierta la cierra
document.addEventListener("click", (evento) => {
  if (window.innerWidth > 768 || !barraLateral.classList.contains("expandida")) return;
  if (!barraLateral.contains(evento.target)) {
    barraLateral.classList.remove("expandida");
    btnToggle.setAttribute("aria-expanded", "false");
  }
});

// Filtros: al cambiar una lista se aplica sin botón (la búsqueda se envía con Enter)
if (formHerramientas) {
  formHerramientas.querySelectorAll(".filtro").forEach((select) => {
    select.addEventListener("change", () => formHerramientas.submit());
  });
}

// Agregar y editar
if (btnAgregar) btnAgregar.addEventListener("click", abrirAgregar);

document.querySelectorAll("[data-editar]").forEach((boton) => {
  boton.addEventListener("click", () => abrirEditar(boton.dataset.editar));
});

if (formulario && formulario.elements.rol) {
  formulario.elements.rol.addEventListener("change", (e) => mostrarCamposProfesional(e.target.value));
  // Si Django volvió a abrir el modal con errores, mostrar los campos que correspondan
  const editando = registros.find((r) => String(r.id) === campoId.value);
  if (editando) {
    formulario.elements.rol.disabled = true;
    mostrarCamposProfesional(editando.rol);
  } else {
    mostrarCamposProfesional(formulario.elements.rol.value);
  }
}

// Confirmaciones (desactivar, nueva contraseña)
document.querySelectorAll("[data-confirmar]").forEach((boton) => {
  boton.addEventListener("click", () => {
    formConfirmar.action = boton.dataset.url;
    tituloConfirmar.textContent = boton.dataset.titulo;
    textoConfirmar.textContent = boton.dataset.texto;
    btnConfirmar.textContent = boton.dataset.boton || "Confirmar";
    btnConfirmar.classList.toggle("boton-peligro", boton.hasAttribute("data-peligro"));
    abrirModal(modalConfirmar);
  });
});

// Cerrar modales: botón ×, Cancelar, clic fuera o Escape
document.querySelectorAll(".modal-overlay").forEach((modal) => {
  modal.querySelectorAll("[data-cerrar-modal]").forEach((boton) => {
    boton.addEventListener("click", () => cerrarModal(modal));
  });
  modal.addEventListener("click", (e) => {
    if (e.target === modal) cerrarModal(modal);
  });
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  document.querySelectorAll(".modal-overlay.activo").forEach(cerrarModal);
});

// Copiar la contraseña temporal
if (btnCopiarClave) {
  btnCopiarClave.addEventListener("click", async () => {
    const clave = document.getElementById("texto-clave").textContent.trim();
    try {
      await navigator.clipboard.writeText(clave);
      btnCopiarClave.innerHTML = '<i class="fa-solid fa-check"></i>';
    } catch (e) {
      // Sin permiso de portapapeles: se selecciona el texto para copiarlo a mano
      const rango = document.createRange();
      rango.selectNodeContents(document.getElementById("texto-clave"));
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(rango);
    }
  });
}
