/**
 * Panel Filter Component
 * 
 * Handles filtering of panel items based on data attributes.
 * Requires the following HTML structure:
 * - panel-tabs with data-all and data-target attributes
 * - panel-block items with data-category attributes
 */

function initializePanelFilters() {
  document.querySelectorAll('.panel').forEach(panel => {
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
            block.style.display = categories.includes(targetCategory) ? '' : 'none';
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

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializePanelFilters);

// Re-initialize when HTMX content is loaded
document.body.addEventListener('htmx:afterSettle', function(event) {
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.panel')) {
    initializePanelFilters();
  }
});
