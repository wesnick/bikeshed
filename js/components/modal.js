export function closeModal() {
  const modal = document.getElementById('modal-container');
  if (modal) {
    modal.classList.remove('is-active');
    // Clear content to prevent brief flash of old content
    const modalContent = modal.querySelector('.modal-content');
    if (modalContent) {
      modalContent.innerHTML = '';
    }
  }
  document.documentElement.classList.remove('is-clipped'); // Remove clipping from HTML tag
}

export function initializeModal() {
  // Add event listeners for closing the modal
  const modalContainer = document.getElementById('modal-container');
  if (modalContainer) {
    const modalBackground = modalContainer.querySelector('.modal-background');
    const modalCloseButton = modalContainer.querySelector('.modal-close');

    if (modalBackground) {
      modalBackground.addEventListener('click', closeModal);
    }
    if (modalCloseButton) {
      modalCloseButton.addEventListener('click', closeModal);
    }
  }

  // Add listener for SSE-triggered close
  document.body.addEventListener('modal.close', closeModal);
}
