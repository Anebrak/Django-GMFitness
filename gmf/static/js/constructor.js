/* =========================================
   GMFitness - constructor de rutinas semana a semana
   Todo el tablero vive en el objeto `rutina` y se dibuja desde ahí.
   Cada cambio se guarda solo (POST JSON a /rutinas/<id>/guardar/, que valida y
   reemplaza días, ejercicios y series). Sin librerías: arrastrar = HTML5 drag & drop.
   ========================================= */

/* =========================================
   Datos
   ========================================= */
function leerJson(id, porDefecto) {
  const nodo = document.getElementById(id);
  return nodo ? JSON.parse(nodo.textContent) : porDefecto;
}

const config = document.getElementById("config-constructor").dataset;
const MAX_SEMANAS = Number(config.maxSemanas);
const MAX_DIAS = Number(config.maxDias);
const MAX_SERIES = Number(config.maxSeries);
const EQUIPOS_FILTRO = ["Todos", ...config.equipos.split("|")];

const rutina = leerJson("datos-rutina", { semanas: [] });
const catalogo = new Map(leerJson("datos-catalogo", []).map((e) => [e.id, e]));

const TIPOS_REPS = [
  ["RANGO", "Rango"],
  ["MAXIMAS", "Reps"],
  ["AMRAP", "AMRAP"],
];

/* =========================================
   Estado
   ========================================= */
let edicion = null; // { s, d, i (null = nuevo), borrador: {...} }
let renombrando = null; // { s, d }
let arrastre = null; // { s, d, i }
let filtroEquipo = "Todos";
let resaltado = 0; // resultado marcado en el buscador
let temporizador = null;
let cambiosSinGuardar = false;
let guardando = false;

/* =========================================
   Referencias al DOM
   ========================================= */
const tablero = document.getElementById("tablero");
const chipsSemanas = document.getElementById("chips-semanas");
const inputNombre = document.getElementById("nombre-rutina");
const resumenRutina = document.getElementById("resumen-rutina");
const estadoGuardado = document.getElementById("estado-guardado");
const etiquetaBorrador = document.getElementById("etiqueta-estado");
const etiquetaPublicada = document.getElementById("etiqueta-publicada");
const cajaErrores = document.getElementById("errores-constructor");
const btnVistaPrevia = document.getElementById("btn-vista-previa");
const csrf = document.querySelector("[name=csrfmiddlewaretoken]").value;

/* =========================================
   Utilidades
   ========================================= */
function esc(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function copia(objeto) {
  return JSON.parse(JSON.stringify(objeto));
}

function ejercicioDe(id) {
  return catalogo.get(Number(id)) || { nombre: "Ejercicio", tipo: "REPS", equipo: "", usos: 0 };
}

function esTiempo(item) {
  return ejercicioDe(item.ejercicio).tipo === "TIEMPO";
}

function textoKg(valor) {
  return String(valor).replace(".", ",");
}

function resumenEjercicio(item) {
  const n = item.series.length;
  const unidad = esTiempo(item) ? "s" : "reps";
  let texto = `${n} serie${n === 1 ? "" : "s"}`;
  const primera = item.series[0] || {};
  if (item.tipo_repeticiones === "AMRAP") texto += " × AMRAP";
  else if (item.tipo_repeticiones === "RANGO" && primera.min) texto += ` × ${primera.min}–${primera.max} ${unidad}`;
  else if (primera.min) texto += ` × ${primera.min} ${unidad}`;
  const cargas = item.series.map((s) => parseFloat(String(s.kg).replace(",", "."))).filter((k) => k > 0);
  if (cargas.length) texto += ` · ${textoKg(Math.max(...cargas))} kg`;
  if (item.tipo_esfuerzo === "RIR" && item.valor_esfuerzo !== null && item.valor_esfuerzo !== "") texto += ` · RIR ${item.valor_esfuerzo}`;
  if (item.tipo_esfuerzo === "ARM") texto += " · ARM";
  return texto;
}

function descansoDe(item) {
  const valor = item.series[0] && item.series[0].descanso;
  return valor || valor === 0 ? `${valor} s` : "";
}

function itemNuevo() {
  return { ejercicio: null, tipo_repeticiones: "RANGO", tipo_esfuerzo: "RIR", valor_esfuerzo: 2,
    series: [1, 2, 3].map(() => ({ min: 8, max: 12, kg: "", descanso: 90 })) };
}

function maxDias() {
  return Math.max(...rutina.semanas.map((s) => s.dias.length));
}

/* =========================================
   Dibujar
   ========================================= */
function dibujarChips() {
  chipsSemanas.innerHTML = rutina.semanas
    .map((s, i) => `<button type="button" class="chip chip-chico" data-ir-semana="${i}">S${i + 1}</button>`)
    .join("");
  marcarChipVisible();
}

function marcarChipVisible() {
  const ancho = 420; // columna de 400px + 20px de separación
  const actual = Math.min(Math.round(tablero.scrollLeft / ancho), rutina.semanas.length - 1);
  chipsSemanas.querySelectorAll(".chip").forEach((chip, i) => {
    chip.classList.toggle("activo", i === actual);
    chip.setAttribute("aria-current", i === actual ? "true" : "false");
  });
}

function dibujarResumen() {
  const n = rutina.semanas.length;
  resumenRutina.textContent = `${n} semana${n === 1 ? "" : "s"} · ${maxDias()} días/sem`;
}

function htmlFila(item, s, d, i) {
  const ej = ejercicioDe(item.ejercicio);
  const descanso = descansoDe(item);
  return `
    <li class="fila-ejercicio" draggable="true" data-s="${s}" data-d="${d}" data-i="${i}">
      <button type="button" class="asa solo-editar" data-accion="mover" aria-label="Mover ${esc(ej.nombre)}: usa las flechas arriba y abajo"><i class="fa-solid fa-grip-vertical"></i></button>
      <button type="button" class="abrir-ejercicio" data-accion="editar-ejercicio" aria-label="Editar ${esc(ej.nombre)}">
        <strong>${esc(ej.nombre)}</strong>
        <small>${esc(resumenEjercicio(item))}</small>
      </button>
      ${descanso ? `<span class="insignia-descanso" title="Descanso"><i class="fa-regular fa-clock" aria-hidden="true"></i> ${descanso}</span>` : ""}
    </li>`;
}

function htmlResultados() {
  const texto = (document.getElementById("editor-buscar")?.value || "").trim().toLowerCase();
  const lista = Array.from(catalogo.values())
    .filter((e) => e.elegible)
    .filter((e) => filtroEquipo === "Todos" || e.equipo === filtroEquipo)
    .filter((e) => !texto || e.nombre.toLowerCase().includes(texto) || e.musculos.join(" ").toLowerCase().includes(texto))
    .sort((a, b) => b.usos - a.usos || a.nombre.localeCompare(b.nombre, "es"))
    .slice(0, 30);
  resaltado = Math.min(resaltado, Math.max(lista.length - 1, 0));
  const opciones = lista.length
    ? lista.map((e, i) => `
        <li role="option" id="opcion-${e.id}" class="resultado${i === resaltado ? " resaltado" : ""}" aria-selected="${i === resaltado}" data-elegir="${e.id}">
          <span><strong>${esc(e.nombre)}</strong><small>${esc(e.equipo || "")}${e.musculos.length ? " · " + esc(e.musculos.join(", ")) : ""}</small></span>
          <span class="usos">${e.usos} ${e.usos === 1 ? "vez" : "veces"}</span>
        </li>`).join("")
    : `<li class="sin-resultados-buscador">No hay ejercicios con ese nombre.</li>`;
  return { html: opciones, ids: lista.map((e) => e.id) };
}

function htmlEditor() {
  const b = edicion.borrador;
  const tiempo = b.ejercicio && esTiempo(b);
  const ej = b.ejercicio ? ejercicioDe(b.ejercicio) : null;
  const tipo = tiempo ? "MAXIMAS" : b.tipo_repeticiones;
  const filas = b.series.map((serie, n) => `
      <tr>
        <th scope="row">${n + 1}</th>
        <td>${tipo === "AMRAP" ? '<span class="texto-gris">AMRAP</span>'
          : tipo === "RANGO"
            ? `<span class="par"><input data-campo="min" data-n="${n}" inputmode="numeric" value="${esc(serie.min ?? "")}" aria-label="Mínimo serie ${n + 1}">–<input data-campo="max" data-n="${n}" inputmode="numeric" value="${esc(serie.max ?? "")}" aria-label="Máximo serie ${n + 1}"></span>`
            : `<input data-campo="min" data-n="${n}" inputmode="numeric" value="${esc(serie.min ?? "")}" aria-label="${tiempo ? "Segundos" : "Repeticiones"} serie ${n + 1}">`}</td>
        <td><input data-campo="kg" data-n="${n}" inputmode="decimal" value="${esc(serie.kg ?? "")}" placeholder="—" aria-label="Kg serie ${n + 1}"></td>
        <td><input data-campo="descanso" data-n="${n}" inputmode="numeric" value="${esc(serie.descanso ?? "")}" placeholder="—" aria-label="Descanso en segundos serie ${n + 1}"></td>
        <td><button type="button" class="btn-quitar" data-accion="quitar-serie" data-n="${n}" aria-label="Quitar serie ${n + 1}"${b.series.length === 1 ? " disabled" : ""}><i class="fa-solid fa-xmark"></i></button></td>
      </tr>`).join("");
  const esfuerzos = [0, 1, 2, 3, 4, 5].map((v) => `<option value="RIR-${v}"${b.tipo_esfuerzo === "RIR" && Number(b.valor_esfuerzo) === v ? " selected" : ""}>RIR ${v}</option>`).join("");
  return `
    <li class="editor-ejercicio">
      <div class="buscador">
        <label for="editor-buscar" class="visually-hidden">Ejercicio</label>
        <i class="fa-solid fa-magnifying-glass" aria-hidden="true"></i>
        <input id="editor-buscar" autocomplete="off" placeholder="Busca un ejercicio" value="${esc(ej ? ej.nombre : "")}"
               role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="resultados-ejercicio">
        <div class="desplegable" id="desplegable-ejercicio" hidden>
          <div class="grupo-chips chips-equipo">
            ${EQUIPOS_FILTRO.map((e) => `<button type="button" class="chip chip-chico${filtroEquipo === e ? " activo" : ""}" data-equipo="${esc(e)}" aria-pressed="${filtroEquipo === e}">${esc(e)}</button>`).join("")}
          </div>
          <ul role="listbox" id="resultados-ejercicio" aria-label="Ejercicios"></ul>
          <button type="button" class="pie-crear" data-accion="crear-ejercicio"><i class="fa-solid fa-plus"></i> Crear ejercicio nuevo</button>
        </div>
      </div>
      <div class="editor-opciones">
        <label>Esfuerzo
          <select data-campo="esfuerzo">${esfuerzos}<option value="ARM"${b.tipo_esfuerzo === "ARM" ? " selected" : ""}>ARM</option></select>
        </label>
      </div>
      <table class="tabla-series">
        <thead><tr>
          <th scope="col">Serie</th>
          <th scope="col">${tiempo ? "Seg." : `<select data-campo="tipo" aria-label="Tipo de repeticiones">${TIPOS_REPS.map(([v, t]) => `<option value="${v}"${tipo === v ? " selected" : ""}>${t}</option>`).join("")}</select>`}</th>
          <th scope="col">kg</th>
          <th scope="col">Desc. (s)</th>
          <th scope="col"><span class="visually-hidden">Quitar</span></th>
        </tr></thead>
        <tbody>${filas}</tbody>
      </table>
      <p class="error-campo" id="error-editor" aria-live="polite"></p>
      <div class="botones-editor">
        <button type="button" class="boton-discontinuo boton-chico" data-accion="agregar-serie"${b.series.length >= MAX_SERIES ? " disabled" : ""}><i class="fa-solid fa-plus"></i> Serie</button>
        <button type="button" class="boton-secundario boton-chico" data-accion="cancelar-editor">Cancelar</button>
        <button type="button" class="boton-primario boton-chico" data-accion="guardar-editor">Guardar</button>
      </div>
    </li>`;
}

function htmlDia(dia, s, d) {
  const enEdicion = edicion && edicion.s === s && edicion.d === d;
  const filas = dia.ejercicios.map((item, i) => (enEdicion && edicion.i === i ? htmlEditor() : htmlFila(item, s, d, i))).join("");
  const nuevo = enEdicion && edicion.i === null ? htmlEditor() : "";
  const n = dia.ejercicios.length;
  const nombre = renombrando && renombrando.s === s && renombrando.d === d
    ? `<input class="input-nombre-dia" id="input-nombre-dia" maxlength="60" value="${esc(dia.nombre)}" placeholder="Ej. Pecho y tríceps" aria-label="Nombre del día ${d + 1}">`
    : `<button type="button" class="nombre-dia" data-accion="renombrar-dia" aria-label="Cambiar el nombre del día ${d + 1}">${dia.nombre ? esc(dia.nombre) : '<span class="texto-gris">Ponle nombre</span>'}</button>`;
  return `
    <article class="tarjeta-dia" data-s="${s}" data-d="${d}">
      <div class="cabeza-dia">
        <h3>Día ${d + 1} · ${nombre}</h3>
        <span class="texto-gris conteo">${n} ejercicio${n === 1 ? "" : "s"}</span>
        <button type="button" class="btn-quitar solo-editar" data-accion="eliminar-dia" aria-label="Eliminar el día ${d + 1} de la semana ${s + 1}"${rutina.semanas[s].dias.length === 1 ? " disabled" : ""}><i class="fa-solid fa-xmark"></i></button>
      </div>
      <ol class="lista-ejercicios" data-s="${s}" data-d="${d}">${filas}${nuevo}</ol>
      ${!n && !nuevo ? `<p class="dia-vacio"><i class="fa-solid fa-dumbbell" aria-hidden="true"></i> Aún no hay ejercicios en este día</p>` : ""}
      ${enEdicion ? "" : `<button type="button" class="boton-secundario boton-pill solo-editar" data-accion="agregar-ejercicio"><i class="fa-solid fa-plus"></i> Añadir ejercicio</button>`}
    </article>`;
}

function htmlSemana(semana, s) {
  const total = rutina.semanas.length;
  return `
    <section class="columna-semana" id="semana-${s + 1}" data-s="${s}" aria-label="Semana ${s + 1}">
      <div class="cabeza-semana">
        <h2>Semana ${s + 1}</h2>
        <div class="acciones-semana solo-editar">
          <button type="button" class="btn-solo-icono" data-accion="duplicar-semana" aria-label="Duplicar la semana ${s + 1} en la semana ${s + 2}" title="Duplicar en la semana ${s + 2}"${s + 1 >= MAX_SEMANAS ? " disabled" : ""}><i class="fa-solid fa-copy"></i></button>
          <div class="menu-opciones">
            <button type="button" class="btn-solo-icono" data-accion="menu-semana" aria-label="Opciones de la semana ${s + 1}" aria-haspopup="true" aria-expanded="false"><i class="fa-solid fa-ellipsis"></i></button>
            <div class="menu-desplegable" role="menu" hidden>
              <button type="button" role="menuitem" data-accion="mover-semana" data-dir="-1"${s === 0 ? " disabled" : ""}><i class="fa-solid fa-arrow-left"></i> Mover antes</button>
              <button type="button" role="menuitem" data-accion="mover-semana" data-dir="1"${s === total - 1 ? " disabled" : ""}><i class="fa-solid fa-arrow-right"></i> Mover después</button>
              <button type="button" role="menuitem" data-accion="vaciar-semana"><i class="fa-solid fa-eraser"></i> Vaciar ejercicios</button>
              <button type="button" role="menuitem" class="opcion-peligro" data-accion="borrar-semana"${total === 1 ? " disabled" : ""}><i class="fa-solid fa-trash"></i> Borrar semana</button>
            </div>
          </div>
        </div>
      </div>
      ${semana.dias.map((dia, d) => htmlDia(dia, s, d)).join("")}
      ${semana.dias.length < MAX_DIAS ? `<button type="button" class="boton-discontinuo solo-editar" data-accion="agregar-dia"><i class="fa-solid fa-plus"></i> Añadir día</button>` : ""}
    </section>`;
}

function dibujar() {
  const scroll = tablero.scrollLeft;
  tablero.innerHTML =
    rutina.semanas.map(htmlSemana).join("") +
    (rutina.semanas.length < MAX_SEMANAS
      ? `<button type="button" class="columna-nueva solo-editar" data-accion="agregar-semana"><i class="fa-solid fa-plus"></i> Añadir semana</button>`
      : "");
  tablero.scrollLeft = scroll;
  dibujarChips();
  dibujarResumen();
  if (edicion) prepararBuscador();
  const nombreDia = document.getElementById("input-nombre-dia");
  if (nombreDia) {
    nombreDia.focus();
    nombreDia.select();
  }
}

/* =========================================
   Editor de ejercicio
   ========================================= */
function prepararBuscador() {
  const input = document.getElementById("editor-buscar");
  if (!edicion.borrador.ejercicio) {
    mostrarResultados(true);
    input.focus();
  }
}

function mostrarResultados(abrir) {
  const desplegable = document.getElementById("desplegable-ejercicio");
  const input = document.getElementById("editor-buscar");
  if (!desplegable) return;
  desplegable.hidden = !abrir;
  input.setAttribute("aria-expanded", String(abrir));
  if (!abrir) return;
  const { html } = htmlResultados();
  document.getElementById("resultados-ejercicio").innerHTML = html;
  const marcado = desplegable.querySelector(".resaltado");
  input.setAttribute("aria-activedescendant", marcado ? marcado.id : "");
  if (marcado) marcado.scrollIntoView({ block: "nearest" });
}

function leerEditor() {
  // Copia lo escrito en la tabla al borrador (antes de redibujar)
  const editor = tablero.querySelector(".editor-ejercicio");
  if (!editor || !edicion) return;
  editor.querySelectorAll("tbody input[data-campo]").forEach((input) => {
    edicion.borrador.series[Number(input.dataset.n)][input.dataset.campo] = input.value.trim();
  });
  const esfuerzo = editor.querySelector("[data-campo=esfuerzo]").value;
  if (esfuerzo === "ARM") {
    edicion.borrador.tipo_esfuerzo = "ARM";
    edicion.borrador.valor_esfuerzo = null;
  } else {
    edicion.borrador.tipo_esfuerzo = "RIR";
    edicion.borrador.valor_esfuerzo = Number(esfuerzo.split("-")[1]);
  }
  const tipo = editor.querySelector("[data-campo=tipo]");
  if (tipo) edicion.borrador.tipo_repeticiones = tipo.value;
}

function elegirEjercicio(id) {
  leerEditor();
  const ej = ejercicioDe(id);
  edicion.borrador.ejercicio = Number(id);
  if (ej.tipo === "TIEMPO") {
    edicion.borrador.tipo_repeticiones = "MAXIMAS";
    edicion.borrador.series.forEach((s) => {
      if (!s.min || s.min < 10) s.min = 30;
      s.max = null;
    });
  }
  dibujar();
  const primero = tablero.querySelector(".editor-ejercicio tbody input");
  if (primero) primero.focus();
}

function validarBorrador(b) {
  if (!b.ejercicio) return "Elige un ejercicio de la lista.";
  const entero = (v) => /^\d+$/.test(String(v ?? "").trim());
  for (let n = 0; n < b.series.length; n += 1) {
    const s = b.series[n];
    if (b.tipo_repeticiones === "RANGO") {
      if (!entero(s.min) || !entero(s.max)) return `Serie ${n + 1}: escribe el rango (mínimo y máximo).`;
      if (Number(s.min) > Number(s.max)) return `Serie ${n + 1}: el máximo debe ser mayor o igual al mínimo.`;
    } else if (b.tipo_repeticiones === "MAXIMAS" && (!entero(s.min) || Number(s.min) < 1)) {
      return `Serie ${n + 1}: escribe ${esTiempo(b) ? "los segundos" : "las repeticiones"}.`;
    }
    if (s.kg !== "" && s.kg !== null && !/^\d+([.,]\d{1,2})?$/.test(String(s.kg).trim())) return `Serie ${n + 1}: carga no válida.`;
    if (s.descanso !== "" && s.descanso !== null && !entero(s.descanso)) return `Serie ${n + 1}: el descanso va en segundos.`;
  }
  return "";
}

function guardarEditor() {
  leerEditor();
  const b = edicion.borrador;
  const error = validarBorrador(b);
  if (error) {
    document.getElementById("error-editor").textContent = error;
    return;
  }
  b.series = b.series.map((s) => ({
    min: b.tipo_repeticiones === "AMRAP" ? null : Number(s.min),
    max: b.tipo_repeticiones === "RANGO" ? Number(s.max) : null,
    kg: s.kg === null ? "" : String(s.kg).replace(",", "."),
    descanso: s.descanso === "" || s.descanso === null ? null : Number(s.descanso),
  }));
  const dia = rutina.semanas[edicion.s].dias[edicion.d];
  if (edicion.i === null) dia.ejercicios.push(b);
  else dia.ejercicios[edicion.i] = b;
  edicion = null;
  dibujar();
  programarGuardado();
}

/* =========================================
   Guardar (autoguardado)
   ========================================= */
function mostrarEstado(texto, clase) {
  estadoGuardado.textContent = texto;
  estadoGuardado.className = clase;
}

function programarGuardado() {
  cambiosSinGuardar = true;
  mostrarEstado("Cambios sin guardar…", "texto-gris");
  clearTimeout(temporizador);
  temporizador = setTimeout(() => guardar("guardar"), 800);
}

async function guardar(accion) {
  if (guardando) {
    programarGuardado();
    return;
  }
  clearTimeout(temporizador);
  guardando = true;
  mostrarEstado("Guardando…", "texto-gris");
  const cuerpo = {
    accion,
    nombre: inputNombre.value.trim(),
    semanas: rutina.semanas.map((s) => ({ dias: s.dias })),
  };
  try {
    const respuesta = await fetch(config.urlGuardar, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(cuerpo),
    });
    const datos = await respuesta.json();
    if (!datos.ok) {
      cajaErrores.innerHTML = `<p><strong>No se pudo guardar:</strong></p><ul>${datos.errores.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>`;
      cajaErrores.hidden = false;
      mostrarEstado("Sin guardar", "texto-rojo");
      return;
    }
    cajaErrores.hidden = true;
    cambiosSinGuardar = false;
    rutina.estado = datos.estado;
    etiquetaBorrador.hidden = datos.estado === "PUBLICADA";
    etiquetaPublicada.hidden = datos.estado !== "PUBLICADA";
    document.title = `${datos.nombre} | GMFitness`;
    const textos = { publicar: "Publicada", borrador: "Borrador guardado" };
    mostrarEstado(`${textos[accion] || "Guardado"} ${datos.guardado}`, "texto-verde");
  } catch (error) {
    mostrarEstado("Sin conexión: no se guardó", "texto-rojo");
  } finally {
    guardando = false;
  }
}

/* =========================================
   Acciones del tablero
   ========================================= */
function posicion(elemento) {
  const caja = elemento.closest("[data-s]");
  if (!caja) return {};
  const dia = elemento.closest(".tarjeta-dia");
  const fila = elemento.closest(".fila-ejercicio");
  return {
    s: Number(caja.dataset.s),
    d: dia ? Number(dia.dataset.d) : null,
    i: fila ? Number(fila.dataset.i) : null,
  };
}

function cerrarMenusSemana(excepto) {
  tablero.querySelectorAll("[data-accion=menu-semana]").forEach((boton) => {
    if (boton === excepto) return;
    boton.setAttribute("aria-expanded", "false");
    boton.nextElementSibling.hidden = true;
  });
}

const acciones = {
  "agregar-ejercicio"(p) {
    if (edicion) leerEditor();
    edicion = { s: p.s, d: p.d, i: null, borrador: itemNuevo() };
    resaltado = 0;
    dibujar();
  },
  "editar-ejercicio"(p) {
    if (document.body.classList.contains("vista-previa")) return;
    edicion = { s: p.s, d: p.d, i: p.i, borrador: copia(rutina.semanas[p.s].dias[p.d].ejercicios[p.i]) };
    dibujar();
  },
  "cancelar-editor"() {
    edicion = null;
    dibujar();
  },
  "guardar-editor"() {
    guardarEditor();
  },
  "agregar-serie"() {
    leerEditor();
    const series = edicion.borrador.series;
    if (series.length < MAX_SERIES) series.push({ ...series[series.length - 1] });
    dibujar();
  },
  "quitar-serie"(p, boton) {
    leerEditor();
    edicion.borrador.series.splice(Number(boton.dataset.n), 1);
    dibujar();
  },
  "crear-ejercicio"() {
    leerEditor();
    abrirModalEjercicio(document.getElementById("editor-buscar").value.trim());
  },
  "renombrar-dia"(p) {
    renombrando = { s: p.s, d: p.d };
    dibujar();
  },
  "eliminar-dia"(p) {
    const dias = rutina.semanas[p.s].dias;
    if (dias[p.d].ejercicios.length && !window.confirm(`¿Eliminar el día ${p.d + 1} y sus ejercicios?`)) return;
    dias.splice(p.d, 1);
    edicion = null;
    dibujar();
    programarGuardado();
  },
  "agregar-dia"(p) {
    rutina.semanas[p.s].dias.push({ nombre: "", ejercicios: [] });
    dibujar();
    programarGuardado();
  },
  "duplicar-semana"(p) {
    const destino = p.s + 1;
    const original = copia(rutina.semanas[p.s]);
    if (rutina.semanas[destino]) {
      const tiene = rutina.semanas[destino].dias.some((d) => d.ejercicios.length);
      if (tiene && !window.confirm(`La semana ${destino + 1} ya tiene ejercicios. ¿Reemplazarla con una copia de la semana ${p.s + 1}?`)) return;
      rutina.semanas[destino] = original;
    } else {
      rutina.semanas.push(original);
    }
    edicion = null;
    dibujar();
    programarGuardado();
    document.getElementById(`semana-${destino + 1}`).scrollIntoView({ behavior: "smooth", inline: "start", block: "nearest" });
  },
  "agregar-semana"() {
    const ultima = rutina.semanas[rutina.semanas.length - 1];
    rutina.semanas.push({ dias: ultima.dias.map((d) => ({ nombre: d.nombre, ejercicios: [] })) });
    dibujar();
    programarGuardado();
    tablero.scrollTo({ left: tablero.scrollWidth, behavior: "smooth" });
  },
  "menu-semana"(p, boton) {
    const menu = boton.nextElementSibling;
    const abrir = menu.hidden;
    cerrarMenusSemana(boton);
    menu.hidden = !abrir;
    boton.setAttribute("aria-expanded", String(abrir));
    if (abrir) menu.querySelector("button:not([disabled])").focus();
  },
  "mover-semana"(p, boton) {
    const destino = p.s + Number(boton.dataset.dir);
    const [semana] = rutina.semanas.splice(p.s, 1);
    rutina.semanas.splice(destino, 0, semana);
    edicion = null;
    dibujar();
    programarGuardado();
  },
  "vaciar-semana"(p) {
    if (!window.confirm(`¿Quitar todos los ejercicios de la semana ${p.s + 1}?`)) return;
    rutina.semanas[p.s].dias.forEach((d) => (d.ejercicios = []));
    edicion = null;
    dibujar();
    programarGuardado();
  },
  "borrar-semana"(p) {
    if (!window.confirm(`¿Borrar la semana ${p.s + 1}? Las siguientes se corren una posición.`)) return;
    rutina.semanas.splice(p.s, 1);
    edicion = null;
    dibujar();
    programarGuardado();
  },
};

function moverEjercicio(origen, s, d, indice) {
  const lista = rutina.semanas[origen.s].dias[origen.d].ejercicios;
  const [item] = lista.splice(origen.i, 1);
  const destino = rutina.semanas[s].dias[d].ejercicios;
  if (origen.s === s && origen.d === d && origen.i < indice) indice -= 1;
  destino.splice(Math.max(0, Math.min(indice, destino.length)), 0, item);
}

function terminarRenombrar(guardarNombre) {
  const input = document.getElementById("input-nombre-dia");
  if (!renombrando || !input) return;
  if (guardarNombre) {
    rutina.semanas[renombrando.s].dias[renombrando.d].nombre = input.value.trim().slice(0, 60);
    programarGuardado();
  }
  renombrando = null;
  dibujar();
}

/* =========================================
   Eventos
   ========================================= */
tablero.addEventListener("click", (e) => {
  const elegir = e.target.closest("[data-elegir]");
  if (elegir) {
    elegirEjercicio(elegir.dataset.elegir);
    return;
  }
  const chipEquipo = e.target.closest("[data-equipo]");
  if (chipEquipo) {
    filtroEquipo = chipEquipo.dataset.equipo;
    tablero.querySelectorAll(".chips-equipo .chip").forEach((c) => {
      c.classList.toggle("activo", c === chipEquipo);
      c.setAttribute("aria-pressed", String(c === chipEquipo));
    });
    resaltado = 0;
    mostrarResultados(true);
    document.getElementById("editor-buscar").focus();
    return;
  }
  const boton = e.target.closest("[data-accion]");
  if (!boton || boton.disabled || !acciones[boton.dataset.accion]) return;
  e.stopPropagation();
  acciones[boton.dataset.accion](posicion(boton), boton);
});

tablero.addEventListener("input", (e) => {
  if (e.target.id === "editor-buscar") {
    resaltado = 0;
    mostrarResultados(true);
  }
});

tablero.addEventListener("focusin", (e) => {
  if (e.target.id === "editor-buscar") mostrarResultados(true);
});

tablero.addEventListener("change", (e) => {
  if (e.target.dataset.campo === "tipo") {
    leerEditor();
    dibujar();
  }
});

tablero.addEventListener("keydown", (e) => {
  // Buscador: flechas para moverse, Enter para elegir, Escape para cerrar
  if (e.target.id === "editor-buscar") {
    const ids = htmlResultados().ids;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      resaltado = (resaltado + (e.key === "ArrowDown" ? 1 : -1) + ids.length) % Math.max(ids.length, 1);
      mostrarResultados(true);
    } else if (e.key === "Enter" && ids.length) {
      e.preventDefault();
      elegirEjercicio(ids[resaltado]);
    } else if (e.key === "Escape") {
      e.stopPropagation();
      mostrarResultados(false);
    }
    return;
  }
  // Nombre del día
  if (e.target.id === "input-nombre-dia") {
    if (e.key === "Enter") terminarRenombrar(true);
    if (e.key === "Escape") terminarRenombrar(false);
    return;
  }
  // Asa: mover con el teclado
  if (e.target.dataset.accion === "mover" && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
    e.preventDefault();
    const p = posicion(e.target);
    const destino = p.i + (e.key === "ArrowDown" ? 2 : -1);
    if (destino < 0 || destino > rutina.semanas[p.s].dias[p.d].ejercicios.length) return;
    moverEjercicio(p, p.s, p.d, destino);
    dibujar();
    programarGuardado();
    const nueva = tablero.querySelector(`.fila-ejercicio[data-s="${p.s}"][data-d="${p.d}"][data-i="${p.i + (e.key === "ArrowDown" ? 1 : -1)}"] .asa`);
    if (nueva) nueva.focus();
  }
  // Enter en la tabla de series = Guardar
  if (e.key === "Enter" && e.target.closest(".tabla-series")) {
    e.preventDefault();
    guardarEditor();
  }
});

tablero.addEventListener("focusout", (e) => {
  if (e.target.id === "input-nombre-dia") setTimeout(() => terminarRenombrar(true), 0);
});

// Arrastrar y soltar (reordenar y mover entre días)
tablero.addEventListener("dragstart", (e) => {
  const fila = e.target.closest(".fila-ejercicio");
  if (!fila || edicion || document.body.classList.contains("vista-previa")) {
    e.preventDefault();
    return;
  }
  arrastre = posicion(fila);
  fila.classList.add("arrastrando");
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", "ejercicio");
});

tablero.addEventListener("dragover", (e) => {
  const lista = e.target.closest(".tarjeta-dia");
  if (!arrastre || !lista) return;
  e.preventDefault();
  tablero.querySelectorAll(".destino").forEach((n) => n.classList.remove("destino"));
  lista.classList.add("destino");
});

tablero.addEventListener("drop", (e) => {
  const tarjeta = e.target.closest(".tarjeta-dia");
  if (!arrastre || !tarjeta) return;
  e.preventDefault();
  const s = Number(tarjeta.dataset.s);
  const d = Number(tarjeta.dataset.d);
  // Posición: antes de la primera fila cuya mitad esté por debajo del puntero
  const filas = Array.from(tarjeta.querySelectorAll(".fila-ejercicio"));
  let indice = filas.length;
  for (let n = 0; n < filas.length; n += 1) {
    const caja = filas[n].getBoundingClientRect();
    if (e.clientY < caja.top + caja.height / 2) {
      indice = n;
      break;
    }
  }
  moverEjercicio(arrastre, s, d, indice);
  arrastre = null;
  dibujar();
  programarGuardado();
});

tablero.addEventListener("dragend", () => {
  arrastre = null;
  tablero.querySelectorAll(".arrastrando, .destino").forEach((n) => n.classList.remove("arrastrando", "destino"));
});

tablero.addEventListener("scroll", marcarChipVisible, { passive: true });

chipsSemanas.addEventListener("click", (e) => {
  const chip = e.target.closest("[data-ir-semana]");
  if (!chip) return;
  const columna = document.getElementById(`semana-${Number(chip.dataset.irSemana) + 1}`);
  tablero.scrollTo({ left: columna.offsetLeft - tablero.offsetLeft, behavior: "smooth" });
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".menu-opciones")) cerrarMenusSemana(null);
  if (!e.target.closest(".buscador")) mostrarResultados(false);
});

inputNombre.addEventListener("input", () => {
  if (inputNombre.value.trim()) programarGuardado();
});

document.getElementById("btn-guardar-borrador").addEventListener("click", () => guardar("borrador"));
document.getElementById("btn-publicar").addEventListener("click", () => guardar("publicar"));

btnVistaPrevia.addEventListener("click", () => {
  if (edicion) {
    edicion = null;
    dibujar();
  }
  const activa = document.body.classList.toggle("vista-previa");
  btnVistaPrevia.setAttribute("aria-pressed", String(activa));
  btnVistaPrevia.querySelector("span").textContent = activa ? "Seguir editando" : "Vista previa";
});

// Ejercicio creado en el modal: se agrega al catálogo y queda elegido en el editor
alCrearEjercicio = (ejercicio) => {
  catalogo.set(ejercicio.id, ejercicio);
  if (edicion) elegirEjercicio(ejercicio.id);
};

window.addEventListener("beforeunload", (e) => {
  if (cambiosSinGuardar) {
    e.preventDefault();
    e.returnValue = "";
  }
});

dibujar();
