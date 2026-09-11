document.addEventListener("DOMContentLoaded", function() {
    // Mobile Sidebar Logic
    const sidebar = document.getElementById('mobileSidebar');
    const overlay = document.querySelector('.overlay');
    
    window.toggleSidebar = function() {
        if(sidebar && overlay) {
            sidebar.classList.toggle('active');
            overlay.classList.toggle('active');
        }
    };

    // Mobile Search Logic
    const searchBar = document.getElementById('mobSearchBar');
    window.toggleSearch = function() {
        if(searchBar) {
            searchBar.style.display = searchBar.style.display === 'block' ? 'none' : 'block';
        }
    };
});