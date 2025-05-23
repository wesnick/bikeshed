export function closeModal() {
  const modalElement = document.getElementById('modal-container');
  if (modalElement) {
    const bootstrapModal = bootstrap.Modal.getInstance(modalElement);
    if (bootstrapModal) {
      bootstrapModal.hide();
    }

    // Optional: Clear content after modal is hidden to prevent flash of old content.
    // Bootstrap's hide is asynchronous (due to transitions).
    // Listen for the 'hidden.bs.modal' event to clear content after transition.
    modalElement.addEventListener('hidden.bs.modal', function onModalHidden() {
      const modalBody = modalElement.querySelector('.modal-body'); // Assuming content is in modal-body
      if (modalBody) { // Or target .modal-content if the entire content is replaced
        modalBody.innerHTML = ''; 
      } else {
        // Fallback to .modal-content if .modal-body is not found or specific structure is unknown
        const modalContent = modalElement.querySelector('.modal-content');
        if (modalContent) {
            modalContent.innerHTML = ''; // This will clear header/footer too if they are part of loaded content
        }
      }
      // Remove this event listener to prevent it from firing multiple times
      modalElement.removeEventListener('hidden.bs.modal', onModalHidden);
    }, { once: true }); // Ensure the listener is called only once per hide event
  }
  // Bootstrap handles body scrolling (e.g., removing 'modal-open' from body),
  // so manually removing 'is-clipped' from documentElement is no longer needed.
}

export function initializeModal() {
  const modalContainer = document.getElementById('modal-container');
  
  // Bootstrap's modal handles backdrop clicks and [data-bs-dismiss="modal"] automatically.
  // The explicit event listeners for .modal-background and .modal-close (Bulma classes)
  // are no longer needed if the Bootstrap HTML structure is correctly used.
  // The main `index.html.j2` modal structure was updated for Bootstrap.
  // Specific close buttons within HTMX-loaded content should use `data-bs-dismiss="modal"`.

  // Ensure a Bootstrap modal instance is created for the modal container if not already.
  // This allows programmatic control via `bootstrap.Modal.getInstance(modalContainer)`.
  if (modalContainer) {
    bootstrap.Modal.getOrCreateInstance(modalContainer);
  }
  
  // Add listener for SSE-triggered close. This remains relevant.
  document.body.addEventListener('modal.close', closeModal);
}
