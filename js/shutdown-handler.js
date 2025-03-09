/**
 * Handles server shutdown events from SSE
 */
document.addEventListener('DOMContentLoaded', function() {
    // Create a container for notifications if it doesn't exist
    let notificationContainer = document.getElementById('notification-container');
    if (!notificationContainer) {
        notificationContainer = document.createElement('div');
        notificationContainer.id = 'notification-container';
        notificationContainer.style.position = 'fixed';
        notificationContainer.style.top = '1rem';
        notificationContainer.style.right = '1rem';
        notificationContainer.style.zIndex = '9999';
        document.body.appendChild(notificationContainer);
    }

    // Listen for the custom SSE event
    document.body.addEventListener('htmx:sseMessage', function(event) {
        // Check if this is a server_shutdown event
        if (event.detail.event === 'server_shutdown') {
            console.log('Server shutdown detected');
            
            // Create notification content with reload button
            const notificationContent = document.createElement('div');
            notificationContent.innerHTML = `
                <strong>Server Shutting Down</strong>
                <p>The server is restarting. The page may not reconnect automatically.</p>
                <div class="buttons mt-3">
                    <button class="button is-info reload-page">
                        <span class="icon">
                            <i class="fas fa-sync-alt"></i>
                        </span>
                        <span>Reload Page</span>
                    </button>
                </div>
            `;
            
            // Use Bulma's native notification
            const notification = Bulma.create('notification', {
                isDismissable: true,
                color: 'warning',
                body: notificationContent,
                parent: notificationContainer,
                closeOnClick: false
            });
            
            // Add event listener to the reload button
            notificationContent.querySelector('.reload-page').addEventListener('click', function() {
                window.location.reload();
            });
            
            // Set a timer to attempt auto-reload after 5 seconds
            setTimeout(() => {
                // Check if server is back online before reloading
                fetch(window.location.href, { method: 'HEAD' })
                    .then(response => {
                        if (response.ok) {
                            console.log('Server is back online, reloading page');
                            window.location.reload();
                        } else {
                            console.log('Server still unavailable');
                        }
                    })
                    .catch(error => {
                        console.log('Server still unavailable, not reloading yet');
                    });
            }, 5000);
        }
    });
});
