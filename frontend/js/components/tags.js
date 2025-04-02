import htmx from 'htmx.org';

export function initializeTagAutocomplete(container) {
  const entityId = container.dataset.entityId;
  if (!entityId) {
    console.error("Tag component container missing data-entity-id");
    return;
  }

  const dropdown = container.querySelector('.tag-autocomplete-dropdown');
  const input = container.querySelector('.tag-autocomplete-input');
  const resultsContainer = container.querySelector('.dropdown-content');
  const form = container.querySelector(`#entity-tag-form-${entityId}`);
  const tagIdInput = form.querySelector('input[name="tag_id"]');
  const actionInput = form.querySelector('input[name="action"]');

  if (!dropdown || !input || !resultsContainer || !form || !tagIdInput || !actionInput) {
    console.error(`Required elements not found within tag component for entity ${entityId}`);
    return;
  }

  // --- Dropdown Visibility ---
  input.addEventListener('focus', () => {
    // Don't activate immediately, let HTMX load initial results if configured
    // dropdown.classList.add('is-active');
  });

  input.addEventListener('blur', () => {
    // Delay hiding to allow click on dropdown items
    setTimeout(() => {
      if (!dropdown.contains(document.activeElement)) {
        dropdown.classList.remove('is-active');
      }
    }, 200);
  });

  // Activate dropdown when HTMX loads content into results
  resultsContainer.addEventListener('htmx:afterSwap', () => {
    dropdown.classList.add('is-active');
  });
  // Deactivate dropdown if HTMX request fails or returns empty
  resultsContainer.addEventListener('htmx:beforeSwap', (event) => {
    if (event.detail.xhr.status !== 200 || !event.detail.serverResponse || event.detail.serverResponse.trim() === '') {
      // Optionally check if the response indicates "no results" vs an error
      dropdown.classList.remove('is-active');
    }
  });


  // --- Selecting a Tag ---
  resultsContainer.addEventListener('click', (event) => {
    const target = event.target.closest('.tag-suggestion');
    if (target) {
      event.preventDefault();
      const tagId = target.dataset.tagId;
      const tagName = target.dataset.tagName; // Or target.textContent.trim();

      console.log(`Tag selected: ID=${tagId}, Name=${tagName}`);

      // Populate hidden form fields
      tagIdInput.value = tagId;
      actionInput.value = 'add';

      // Trigger form submission via HTMX
      htmx.trigger(form, 'submit');

      // Clear input and hide dropdown
      input.value = '';
      dropdown.classList.remove('is-active');
      resultsContainer.innerHTML = '<div class="dropdown-item">Start typing to search...</div>'; // Reset results
    }
  });

}
