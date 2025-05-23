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
    // Show dropdown on focus if input has content or to show "start typing"
    // For this example, we'll let htmx:afterSwap handle showing after results are loaded.
    // If you want to show it immediately on focus (e.g., with "start typing message"), you can add:
    // resultsContainer.classList.add('show');
  });

  input.addEventListener('blur', () => {
    // Delay hiding to allow click on dropdown items
    setTimeout(() => {
      // Check if the focus is still within the dropdown container or on the input itself
      if (!dropdown.contains(document.activeElement) && document.activeElement !== input) {
        resultsContainer.classList.remove('show');
      }
    }, 200); 
  });

  // Activate dropdown when HTMX loads content into results
  resultsContainer.addEventListener('htmx:afterSwap', () => {
    if (resultsContainer.innerHTML.trim() !== '') { // Only show if there's content
        resultsContainer.classList.add('show');
    } else {
        resultsContainer.classList.remove('show');
    }
  });
  // Deactivate dropdown if HTMX request fails or returns empty content before swapping
  resultsContainer.addEventListener('htmx:beforeSwap', (event) => {
    if (event.detail.xhr.status !== 200 || !event.detail.serverResponse || event.detail.serverResponse.trim() === '') {
      resultsContainer.classList.remove('show');
      // Prevent HTMX from swapping empty content which might clear "Start typing..." prematurely
      // if (event.detail.serverResponse.trim() === '') {
      //   event.preventDefault(); // This might be too aggressive, depends on desired behavior
      // }
    }
  });


  // --- Selecting a Tag ---
  resultsContainer.addEventListener('click', (event) => {
    const target = event.target.closest('.tag-suggestion'); // Ensure suggestions have this class
    if (target) {
      event.preventDefault();
      const tagId = target.dataset.tagId;
      const tagName = target.dataset.tagName; 

      console.log(`Tag selected: ID=${tagId}, Name=${tagName}`);

      tagIdInput.value = tagId;
      actionInput.value = 'add';

      htmx.trigger(form, 'submit');

      input.value = ''; // Clear input
      resultsContainer.classList.remove('show'); // Hide dropdown
      // Reset results container content to initial state.
      // This should match the initial content in tag_entity.html.j2 for the results container.
      resultsContainer.innerHTML = '<span class="dropdown-item-text">Start typing to search...</span>';
    }
  });

}
