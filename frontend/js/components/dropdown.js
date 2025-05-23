// Function to initialize dropdown functionality
export function initializeDropdowns(dropdowns) {
  // This custom dropdown handling logic was written for Bulma's `is-active` class.
  // Bootstrap 5.3 handles dropdowns via its own JavaScript components,
  // typically activated by `data-bs-toggle="dropdown"` attributes in the HTML.
  // HTML templates have been updated to use Bootstrap's data attributes.
  // Therefore, this custom script is likely redundant or may conflict.
  // Commenting out the original logic.
  // If specific dropdowns still need custom programmatic control,
  // they should be handled using Bootstrap's Dropdown JavaScript API:
  // e.g., `new bootstrap.Dropdown(triggerElement).toggle();`

  /*
  dropdowns.forEach(dropdown => {
    // Original Bulma-specific trigger query:
    // const trigger = dropdown.querySelector('.dropdown-trigger button');
    
    // Bootstrap equivalent might be:
    const trigger = dropdown.querySelector('[data-bs-toggle="dropdown"]');
    if (!trigger) return;

    // Remove any existing event listeners by cloning and replacing the trigger button
    // This approach to event listener removal might still be valid if needed.
    const newTrigger = trigger.cloneNode(true);
    if (trigger.parentNode) {
        trigger.parentNode.replaceChild(newTrigger, trigger);
    } else {
        // Fallback if trigger has no parent (should not happen for valid HTML)
        console.warn("Dropdown trigger's parentNode is null", trigger);
        return;
    }
    

    // Add click event listener to toggle dropdown
    newTrigger.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();

      // Example of programmatic toggle with Bootstrap:
      // const associatedMenu = dropdown.querySelector('.dropdown-menu');
      // if (associatedMenu) {
      //   const bsDropdown = bootstrap.Dropdown.getOrCreateInstance(newTrigger);
      //   bsDropdown.toggle();
      // }

      // Closing other dropdowns would also need to use Bootstrap's API or class `show` on `.dropdown-menu`.
    });
  });

  // Close dropdowns when clicking outside - Bootstrap's JS handles this automatically for its dropdowns.
  // This custom outside click handler might conflict or be redundant.
  document.addEventListener('click', function (e) {
    // if (!e.target.closest('.dropdown')) {
    //   document.querySelectorAll('.dropdown .dropdown-menu.show').forEach(openMenu => {
    //      bootstrap.Dropdown.getInstance(openMenu.previousElementSibling)?.hide();
    //   });
    // }
  });
  */
}
