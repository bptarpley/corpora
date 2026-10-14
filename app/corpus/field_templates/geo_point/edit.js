var GeoPointMarkers = {}
var LatLongTimer = null

function renderGeoPointMap(target) {
    target = elFromEventOrEl(target)
    let id_prefix = target.dataset.id_prefix
    let lat_input = getEl(`${id_prefix}-lat`)
    let long_input = getEl(`${id_prefix}-long`)
    let map_div = getEl(`${id_prefix}-map`)
    let map = L.map(map_div.id)
    let value_control = getEl(`${id_prefix}-value`)

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        noWrap: true,
        maxZoom: 19,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        referrerPolicy: 'strict-origin-when-cross-origin'
    }).addTo(map)

    if (getVal(lat_input) && getVal(long_input)) {
        let coords = setGeoPointMarker(lat_input, long_input, target, map)
    } else
        map.locate({setView: true})

    map.on('click', function(e) {
        setVal(lat_input, e.latlng.lat)
        setVal(long_input, e.latlng.lng)
        let coords = setGeoPointMarker(lat_input, long_input, target, map, false)
        setVal(lat_input, coords[0])
        setVal(long_input, coords[1])
        setVal(value_control, JSON.stringify([coords[1], coords[0]]))
    })

    let actions = ['change', 'paste', 'keyup']
    actions.forEach(occasion => {
        [lat_input, long_input].forEach(input => {
            onEl(input, occasion, () => {
                clearTimeout(LatLongTimer)
                LatLongTimer = setTimeout(function() {
                    let coords = setGeoPointMarker(lat_input, long_input, target, map)
                    setVal(value_control, JSON.stringify([coords[1], coords[0]]))
                }, 1000)
            })
        })
    })
}

function setGeoPointMarker(lat_input, long_input, target, map, setView=true) {
    let lat = parseFloat(getVal(lat_input))
    let long = parseFloat(getVal(long_input))

    while (lat < -90) lat += 180
    while (lat > 90) lat -= 180
    while (long < -180) long += 360
    while (long > 180) long -= 360

    let coords = [lat, long]

    let last_marker_id = target.dataset.marker
    if (last_marker_id) {
        map.removeLayer(GeoPointMarkers[last_marker_id])
        delete GeoPointMarkers[last_marker_id]
    }
    let marker = L.marker(coords)
    marker.addTo(map)
    GeoPointMarkers[marker._leaflet_id] = marker
    target.dataset.marker = marker._leaflet_id
    if (setView) map.setView(coords, 13)
    return coords
}
