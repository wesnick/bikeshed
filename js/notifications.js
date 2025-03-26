// Notifications handling
document.addEventListener('DOMContentLoaded', function() {
  // Initialize the dropdown behavior
  initNotificationsDropdown();
  
  // Set up SSE listener for notification updates
  document.body.addEventListener('htmx:sseMessage', function(event) {
    if (event.detail.name === 'notifications.update') {
      // Refresh the notifications component
      htmx.trigger('#notifications-dropdown', 'refresh');
    }
  });
});

function initNotificationsDropdown() {
  // Find all dropdowns on the page
  const dropdowns = document.querySelectorAll('#notifications-dropdown');
  
  // For each dropdown
  dropdowns.forEach(dropdown => {
    // Get the trigger and menu elements
    const trigger = dropdown.querySelector('.dropdown-trigger');
    
    // Add click event to toggle dropdown
    if (trigger) {
      trigger.addEventListener('click', function(event) {
        event.stopPropagation();
        dropdown.classList.toggle('is-active');
      });
    }
  });
  
  // Close dropdowns when clicking outside
  document.addEventListener('click', function(event) {
    dropdowns.forEach(dropdown => {
      if (!dropdown.contains(event.target)) {
        dropdown.classList.remove('is-active');
      }
    });
  });
}

// Re-initialize dropdown when content is updated via HTMX
document.body.addEventListener('htmx:afterSwap', function(event) {
  if (event.detail.target.id === 'notifications-dropdown') {
    initNotificationsDropdown();
  }
});
