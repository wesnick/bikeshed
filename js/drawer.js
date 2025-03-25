// Drawer functionality
export function initializeDrawer() {
  const drawer = document.getElementById('right-drawer');
  const dashboard = document.getElementById('dashboard').closest('.column');
  const sideBySlideBtn = document.getElementById('drawer-side-by-side');
  const overlayBtn = document.getElementById('drawer-overlay');
  const closeBtn = document.getElementById('drawer-close');

  // Side-by-side mode
  sideBySlideBtn.addEventListener('click', () => {
    // Reset any existing classes
    drawer.classList.remove('drawer-closed', 'drawer-overlay');
    drawer.classList.add('drawer-side-by-side');
    
    // Adjust main content area
    dashboard.classList.remove('is-7');
    dashboard.classList.add('is-6');
    
    // Show close button, hide open buttons
    closeBtn.classList.remove('is-hidden');
    sideBySlideBtn.classList.add('is-hidden');
    overlayBtn.classList.add('is-hidden');
    
    // Trigger an event that the drawer has been opened
    document.body.dispatchEvent(new CustomEvent('drawer:opened', { 
      detail: { mode: 'side-by-side' } 
    }));
  });

  // Overlay mode
  overlayBtn.addEventListener('click', () => {
    // Reset any existing classes
    drawer.classList.remove('drawer-closed', 'drawer-side-by-side');
    drawer.classList.add('drawer-overlay', 'is-5');
    
    // Keep main content area the same size
    dashboard.classList.remove('is-6');
    dashboard.classList.add('is-7');
    
    // Show close button, hide open buttons
    closeBtn.classList.remove('is-hidden');
    sideBySlideBtn.classList.add('is-hidden');
    overlayBtn.classList.add('is-hidden');
    
    // Trigger an event that the drawer has been opened
    document.body.dispatchEvent(new CustomEvent('drawer:opened', { 
      detail: { mode: 'overlay' } 
    }));
  });

  // Close drawer
  closeBtn.addEventListener('click', () => {
    // Reset drawer classes
    drawer.classList.remove('drawer-side-by-side', 'drawer-overlay', 'is-5');
    drawer.classList.add('drawer-closed');
    
    // Reset main content area
    dashboard.classList.remove('is-6');
    dashboard.classList.add('is-7');
    
    // Hide close button, show open buttons
    closeBtn.classList.add('is-hidden');
    sideBySlideBtn.classList.remove('is-hidden');
    overlayBtn.classList.remove('is-hidden');
    
    // Trigger an event that the drawer has been closed
    document.body.dispatchEvent(new CustomEvent('drawer:closed'));
  });

  // Initialize drawer as closed
  drawer.classList.add('drawer-closed');
}

// Function to programmatically open the drawer
export function openDrawer(mode = 'side-by-side') {
  const button = mode === 'overlay' 
    ? document.getElementById('drawer-overlay')
    : document.getElementById('drawer-side-by-side');
    
  if (button) {
    button.click();
  }
}

// Function to programmatically close the drawer
export function closeDrawer() {
  const button = document.getElementById('drawer-close');
  if (button) {
    button.click();
  }
}
