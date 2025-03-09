import Bulma from "@vizuaalog/bulmajs";

/**
 * Handles server shutdown events from SSE
 */
document.addEventListener('DOMContentLoaded', function() {

    document.body.addEventListener('htmx:sseClose', function (e) {
        const reason = e.detail.type
        switch (reason) {
            // case "nodeMissing":
            //     // Parent node is missing and therefore connection was closed
            // ...
            // case "nodeReplaced":
            //     // Parent node replacement caused closing of connection
            // ...
            case "message":
             // connection was closed due to reception of message sse-close
             console.log('Server shutdown detected');


            // Use Bulma's native notification
            Bulma('#notification-area').notification({
                color: 'warning',
                body: "The server is restarting. The page may not reconnect automatically. <button class=\"reload-page\">Reload</button>",

            }).show();

            // // Add event listener to the reload button
            // notificationContent.querySelector('.reload-page').addEventListener('click', function() {
            //     window.location.reload();
            // });

            // Set a timer to attempt auto-reload after 2 seconds
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
    })


    // Listen for the custom SSE event
    document.body.addEventListener('htmx:sseMessage', function(event) {
        // Check if this is a server_shutdown event
        if (event.detail.event === 'server_shutdown') {
            console.log('Server shutdown detected');

        }
    });
});
