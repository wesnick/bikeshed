// Function to initialize dropdown functionality
export function initializeDropdowns(dropdowns) {
  dropdowns.forEach(dropdown => {
    // Remove any existing event listeners by cloning and replacing the trigger button
    const trigger = dropdown.querySelector('.dropdown-trigger button');
    if (!trigger) return;

    const newTrigger = trigger.cloneNode(true);
    trigger.parentNode.replaceChild(newTrigger, trigger);

    // Add click event listener to toggle dropdown
    newTrigger.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();

      // Close all other dropdowns
      document.querySelectorAll('.dropdown.is-active').forEach(activeDropdown => {
        if (activeDropdown !== dropdown) {
          activeDropdown.classList.remove('is-active');
        }
      });

      // Toggle current dropdown
      dropdown.classList.toggle('is-active');
    });
  });

  // Close dropdowns when clicking outside
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.dropdown')) {
      document.querySelectorAll('.dropdown.is-active').forEach(dropdown => {
        dropdown.classList.remove('is-active');
      });
    }
  });
}
