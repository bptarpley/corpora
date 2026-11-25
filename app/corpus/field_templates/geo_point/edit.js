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

    // setGeoPointMarker returns null for coordinates it can't use, in which case
    // the saved value is left alone
    function setValueFromCoords(coords) {
        if (coords) setVal(value_control, JSON.stringify([coords[1], coords[0]]))
    }

    if (getVal(lat_input) && getVal(long_input)) {
        // also normalizes a stored out-of-range longitude, so the inputs and the
        // value that gets saved always agree
        setValueFromCoords(setGeoPointMarker(lat_input, long_input, target, map))
    } else
        map.locate({setView: true})

    map.on('click', function(e) {
        // Leaflet reports longitudes past +/-180 once the map has been panned
        // across the antimeridian; setGeoPointMarker wraps them
        setVal(lat_input, e.latlng.lat)
        setVal(long_input, e.latlng.lng)
        setValueFromCoords(setGeoPointMarker(lat_input, long_input, target, map, false))
    })

    let actions = ['change', 'paste', 'keyup']
    actions.forEach(occasion => {
        [lat_input, long_input].forEach(input => {
            onEl(input, occasion, () => {
                clearTimeout(LatLongTimer)
                LatLongTimer = setTimeout(function() {
                    setValueFromCoords(setGeoPointMarker(lat_input, long_input, target, map))
                }, 1000)
            })
        })
    })
}

/*
 * Reads the lat/long inputs, places the marker and returns [lat, long], or null
 * when the inputs don't hold a usable point (the offending input is then marked
 * invalid and the marker left where it was).
 *
 * Longitude wraps: -269.42 and 90.58 are the same meridian, so an out-of-range
 * longitude is converted and written back to its input, keeping what's shown in
 * step with what's saved. Latitude does not wrap -- 100 is not -80, just
 * invalid -- so it's rejected rather than converted.
 */
function setGeoPointMarker(lat_input, long_input, target, map, setView=true) {
    let lat = parseFloat(getVal(lat_input))
    let long = parseFloat(getVal(long_input))

    let lat_ok = Number.isFinite(lat) && lat >= -90 && lat <= 90
    let long_ok = Number.isFinite(long)
    lat_input.classList.toggle('is-invalid', !lat_ok)
    long_input.classList.toggle('is-invalid', !long_ok)
    if (!lat_ok || !long_ok) return null

    if (long < -180 || long > 180) {
        // modular rather than a loop of += 360: past ~1e16 that subtraction is
        // lost to float precision and a loop never terminates
        long = ((((long + 180) % 360) + 360) % 360) - 180
        setVal(long_input, long)
    }

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
