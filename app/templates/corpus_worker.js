{% load static %}
importScripts('{% static 'js/ReconnectingEventSource.min.js' %}')

let clients = []

onconnect = (event) => {
    const port = event.ports[0]
    console.log("connecting to {{ corpus_id }}")

    // Store the port for each connected client
    clients.push(port)

    // Handle incoming messages from clients
    port.onmessage = (e) => {
        // At this time, no use for this functionality, but leaving a stub here
        console.log('Message received from client:', e.data)
    }

    // Remove the port when the client disconnects
    port.start()
    port.addEventListener('close', () => {
        clients = clients.filter(client => client !== port)
    })
}

// Initialize the EventSource
const eventSource = new ReconnectingEventSource('/events/{{ corpus_id }}/')

// Dispatch events to each client
eventSource.addEventListener('event', (event) => {
    console.log('Message from EventSource:', event.data)
    // Relay the message to all connected clients
    clients.forEach(client => {
        client.postMessage(event.data)
    })
})

eventSource.onerror = (error) => {
    console.error('EventSource error:', error)
}
