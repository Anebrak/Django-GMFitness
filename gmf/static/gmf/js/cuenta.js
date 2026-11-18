/* =========================================
   GMFitness - páginas de cuenta (ingresar y registro)
   La validación real la hace Django; esto solo ayuda mientras se escribe.
   ========================================= */

/* =========================================
   Referencias al DOM
   ========================================= */
const botonesVerClave = document.querySelectorAll(".btn-ver-clave");
const clave1 = document.getElementById("id_password1");
const clave2 = document.getElementById("id_password2");
const avisoCoincidencia = document.getElementById("aviso-coincidencia");

/* =========================================
   Eventos
   ========================================= */

// Mostrar u ocultar la contraseña
botonesVerClave.forEach((boton) => {
  boton.addEventListener("click", () => {
    const input = boton.parentElement.querySelector("input");
    const mostrar = input.type === "password";
    input.type = mostrar ? "text" : "password";
    boton.setAttribute("aria-label", mostrar ? "Ocultar contraseña" : "Mostrar contraseña");
    boton.querySelector("i").className = mostrar ? "fa-solid fa-eye-slash" : "fa-solid fa-eye";
  });
});

// Registro: avisar si las contraseñas no coinciden
function revisarCoincidencia() {
  if (!clave2.value) {
    avisoCoincidencia.textContent = "";
    return;
  }
  avisoCoincidencia.textContent = clave1.value === clave2.value ? "" : "Las contraseñas no coinciden.";
}

if (clave1 && clave2 && avisoCoincidencia) {
  clave1.addEventListener("input", revisarCoincidencia);
  clave2.addEventListener("input", revisarCoincidencia);
}
