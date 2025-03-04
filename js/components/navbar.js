/**
 * Navbar functionality
 */
export function initNavbar() {
  // Initialize navbar burger menu
  const navbarBurgers = document.querySelectorAll('.navbar-burger');
  navbarBurgers.forEach(burger => {
    burger.addEventListener('click', () => {
      const target = document.getElementById(burger.dataset.target);
      burger.classList.toggle('is-active');
      target.classList.toggle('is-active');
    });
  });
  
  // Initialize sidebar toggles
  document.getElementById('left-sidebar-toggle')?.addEventListener('click', () => toggleSidebar('left-sidebar'));
  document.getElementById('right-sidebar-toggle')?.addEventListener('click', () => toggleSidebar('right-drawer'));
}

export function toggleSidebar(sidebarId) {
  const sidebar = document.getElementById(sidebarId);
  sidebar.classList.toggle('collapsed');
}
