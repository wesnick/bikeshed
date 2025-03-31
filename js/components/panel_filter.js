/**
 * Panel Filter Component
 *
 * Handles filtering of panel items based on data attributes.
 * Requires the following HTML structure:
 * - panel-tabs with data-all and data-target attributes
 * - panel-block items with data-category attributes
 */

export function initializePanelFilters(elements) {
  elements.forEach(panel => {
    const tabs = panel.querySelectorAll('.panel-tabs a');
    const blocks = panel.querySelectorAll('.panel-block[data-category]'); // Target only blocks with data-category
    const searchInput = panel.querySelector('#model-search-input'); // Get the search input

    // Skip if no tabs or blocks found, or if search input is missing for this specific panel type
    if (!tabs.length || !blocks.length) return;

    // Function to apply filters (both category and search)
    const applyFilters = () => {
      const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
      const activeTab = panel.querySelector('.panel-tabs a.is-active');
      // Default to null (show all) if no active tab or if 'data-all' is present
      const targetCategory = (!activeTab || activeTab.hasAttribute('data-all')) ? null : activeTab.getAttribute('data-target');

      blocks.forEach(block => {
        const categories = block.getAttribute('data-category')?.split(' ') || [];
        const modelNameElement = block.querySelector('strong'); // Assuming model name is in <strong>
        const modelName = modelNameElement ? modelNameElement.textContent.toLowerCase() : '';
        const modelIdElement = block.querySelector('.is-size-7'); // Assuming model ID is in .is-size-7
        const modelId = modelIdElement ? modelIdElement.textContent.toLowerCase() : '';


        const categoryMatch = !targetCategory || categories.includes(targetCategory);
        // Match if search term is empty OR if model name OR model id includes the term
        const searchMatch = !searchTerm || modelName.includes(searchTerm) || modelId.includes(searchTerm);

        if (categoryMatch && searchMatch) {
          block.classList.remove('is-hidden');
        } else {
          block.classList.add('is-hidden');
        }


        // if (categoryMatch && searchMatch) {
        //   block.classList.remove('is-hidden');
        // } else {
        //   block.classList.add('is-hidden');
        // }
      });
    };


    // Set up click handlers for tabs
    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        e.preventDefault();

        // Update active tab
        tabs.forEach(t => t.classList.remove('is-active'));
        tab.classList.add('is-active');

        // Apply filters based on the new active tab and current search term
        applyFilters();
      });
    });

    // Add event listener for the search input
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        console.log('updating')
        applyFilters(); // Re-apply filters when search input changes
      });
    }

    // Initialize filters on load
    applyFilters();

  });
}

