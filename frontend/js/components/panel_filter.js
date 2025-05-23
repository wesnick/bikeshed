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
    // Updated selectors for Bootstrap structure (e.g. models_list.html.j2)
    // Tabs are now .nav-link items within a .nav-pills container (often in a .btn-group)
    const tabs = panel.querySelectorAll('.nav-pills .nav-link');
    // Blocks are now .list-group-item items
    const blocks = panel.querySelectorAll('.list-group-item[data-category]');
    const searchInput = panel.querySelector('#model-search-input');

    if (!tabs.length || !blocks.length) return;

    const applyFilters = () => {
      const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
      // Active tab now has .active class in Bootstrap
      const activeTab = panel.querySelector('.nav-pills .nav-link.active');
      const targetCategory = (!activeTab || activeTab.hasAttribute('data-all')) ? null : activeTab.getAttribute('data-target');

      blocks.forEach(block => {
        const categories = block.getAttribute('data-category')?.split(' ') || [];
        const modelNameElement = block.querySelector('strong'); // Still expecting <strong> for name
        const modelName = modelNameElement ? modelNameElement.textContent.toLowerCase() : '';
        // Model ID is now in a .small.text-muted element
        const modelIdElement = block.querySelector('.small.text-muted'); 
        const modelId = modelIdElement ? modelIdElement.textContent.toLowerCase() : '';

        const categoryMatch = !targetCategory || categories.includes(targetCategory);
        const searchMatch = !searchTerm || modelName.includes(searchTerm) || modelId.includes(searchTerm);

        if (categoryMatch && searchMatch) {
          block.classList.remove('d-none'); // Use Bootstrap's 'd-none' for hidden
        } else {
          block.classList.add('d-none'); // Use Bootstrap's 'd-none' for hidden
        }
      });
    };

    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        e.preventDefault();
        // Check if the clicked tab is already active to prevent unnecessary processing
        if (tab.classList.contains('active')) {
            return;
        }

        tabs.forEach(t => t.classList.remove('active')); // Use 'active' for Bootstrap
        tab.classList.add('active');

        applyFilters();
      });
    });

    if (searchInput) {
      searchInput.addEventListener('input', () => {
        // console.log('updating search') // Kept console.log for debugging if needed, but commented out
        applyFilters();
      });
    }

    applyFilters();
  });
}

