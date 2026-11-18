/* =========================================
   GMFitness - Mensajes
   Baja el chat al último mensaje, ajusta el alto del cuadro de texto
   y envía con Enter (Shift+Enter = salto de línea). El envío lo hace Django (POST).
   ========================================= */

/* =========================================
   Referencias al DOM
   ========================================= */
const chatMensajes = document.getElementById("chat-mensajes");
const formMensaje = document.getElementById("form-mensaje");
const textoMensaje = document.getElementById("texto-mensaje");

/* =========================================
   Utilidades
   ========================================= */
function ajustarAlto() {
  textoMensaje.style.height = "auto";
  textoMensaje.style.height = `${Math.min(textoMensaje.scrollHeight, 160)}px`;
}

/* =========================================
   Eventos
   ========================================= */
if (chatMensajes) chatMensajes.scrollTop = chatMensajes.scrollHeight;

if (textoMensaje) {
  ajustarAlto();
  textoMensaje.addEventListener("input", ajustarAlto);
  textoMensaje.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (textoMensaje.value.trim()) formMensaje.requestSubmit();
    }
  });
  // En escritorio el cursor queda listo para escribir
  if (window.innerWidth > 860) textoMensaje.focus();
}
