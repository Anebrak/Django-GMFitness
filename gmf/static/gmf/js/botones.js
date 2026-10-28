function abrirModalId(idModal) {
  const modal = document.getElementById(idModal);
  modal.classList.add('activo');
  modal.setAttribute('aria-hidden', 'false');
}

function cerrarModalId(idModal) {
  const modal = document.getElementById(idModal);
  modal.classList.remove('activo');
  modal.setAttribute('aria-hidden', 'true');
}

function configurarModal(idModal, idAbrir, idCerrar) {
  const modal = document.getElementById(idModal);
  const abrir = document.getElementById(idAbrir);
  const cerrar = document.getElementById(idCerrar);

  abrir.addEventListener('click', () => abrirModalId(idModal));
  cerrar.addEventListener('click', () => cerrarModalId(idModal));

  // Cerrar al hacer clic fuera de la caja
  modal.addEventListener('click', (e) => {
    if (e.target === modal) cerrarModalId(idModal);
  });

  // Cerrar con Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') cerrarModalId(idModal);
  });
}

configurarModal('modal-login', 'abrir-login', 'cerrar-login');
configurarModal('modal-register', 'abrir-register', 'cerrar-register');

// Enlaces "Haz clic aquí": pasan de un modal al otro
document.querySelectorAll('[data-cambiar-modal]').forEach((enlace) => {
  enlace.addEventListener('click', (e) => {
    e.preventDefault();
    const destino = enlace.dataset.cambiarModal;
    cerrarModalId(destino === 'modal-login' ? 'modal-register' : 'modal-login');
    abrirModalId(destino);
  });
});
