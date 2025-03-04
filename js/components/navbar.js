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
}

export function toggleSidebar(sidebarId) {
  const sidebar = document.getElementById(sidebarId);
  sidebar.classList.toggle('collapsed');
}
