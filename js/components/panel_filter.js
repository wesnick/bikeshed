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
    const blocks = panel.querySelectorAll('.panel-block');

    // Skip if no tabs or blocks found
    if (!tabs.length || !blocks.length) return;

    // Set up click handlers for tabs
    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        e.preventDefault();

        // Update active tab
        tabs.forEach(t => t.classList.remove('is-active'));
        tab.classList.add('is-active');

        // Filter blocks based on data attributes
        if (tab.hasAttribute('data-all')) {
          // Show all blocks
          blocks.forEach(block => block.style.display = '');
        } else {
          const targetCategory = tab.getAttribute('data-target');
          blocks.forEach(block => {
            const categories = block.getAttribute('data-category')?.split(' ') || [];
            if (categories.includes(targetCategory)) {
              block.classList.remove('is-hidden');
            }
          });
        }
      });
    });

    // Initialize with the active tab
    const activeTab = panel.querySelector('.panel-tabs a.is-active');
    if (activeTab) {
      activeTab.click();
    }
  });
}

