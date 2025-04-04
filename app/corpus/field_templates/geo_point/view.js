function renderGeoPoint(target) {
    let lat = target.getAttribute('data-latitude')
    let long = target.getAttribute('data-longitude')

    if (lat.length && long.length) {
        let coords = [parseFloat(lat), parseFloat(long)]
        let map = L.map(target.id).setView(coords, 13)

        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(map)

        let marker = L.marker(coords)
        marker.addTo(map)
    }

}