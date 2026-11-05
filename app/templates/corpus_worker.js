{% load static %}
importScripts('{% static 'js/ReconnectingEventSource.min.js' %}')

let clients = []
let eventSource = null

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

    // A refused stream stays closed until a page connects, since the scholar may have logged back in by then
    if (!eventSource) openEventSource()
}

function openEventSource() {
    // Retries wait a random time up to max_retry_time, so a longer window stops every browser from reconnecting at
    // once after an outage (the default of 3 seconds keeps a full nginx full).
    eventSource = new ReconnectingEventSource('/events/{{ corpus_id }}/', {max_retry_time: 30000})

    // Dispatch events to each client
    eventSource.addEventListener('event', (event) => {
        console.log('Message from EventSource:', event.data)
        // Relay the message to all connected clients
        clients.forEach(client => {
            client.postMessage(event.data)
        })
    })

    // The server refused this stream (session ended, access revoked, corpus deleted). Retrying can't change that,
    // and ReconnectingEventSource would otherwise keep trying for as long as a tab stays open.
    eventSource.addEventListener('stream-error', (event) => {
        console.warn('EventSource refused:', event.data)
        eventSource.close()
        eventSource = null
    })

    eventSource.onerror = (error) => {
        console.error('EventSource error:', error)
    }
}
