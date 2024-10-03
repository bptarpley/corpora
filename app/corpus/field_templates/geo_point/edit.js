var GeoPointMarkers = {}
var LatLongTimer = null

function renderGeoPointMap(target) {
    if (target.hasOwnProperty('target')) target = target.target
    target = $(target)
    let id_prefix = target.data('id_prefix')
    let lat_input = $(`#${id_prefix}-lat`)
    let long_input = $(`#${id_prefix}-long`)
    let map_div = $(`#${id_prefix}-map`)
    let map = L.map(map_div[0].id)
    let value_control = $(`#${id_prefix}-value`)

    //let width = (3 * map_div.parent().width()) / 4
    //map_div.css('width', width)

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        noWrap: true,
        maxZoom: 19,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map)

    if (lat_input.val() && long_input.val()) {
        let coords = setGeoPointMarker(lat_input, long_input, target, map)
        map.setView(coords, 13)
    } else
        map.locate({setView: true})

    map.on('click', function(e) {
        lat_input.val(e.latlng.lat)
        long_input.val(e.latlng.lng)
        let coords = setGeoPointMarker(lat_input, long_input, target, map)
        lat_input.val(coords[0])
        long_input.val(coords[1])
        value_control.val(JSON.stringify([coords[1], coords[0]]))
    })

    $(`#${id_prefix}-lat, #${id_prefix}-long`).on('change paste keyup', function() {
        clearTimeout(LatLongTimer)
        LatLongTimer = setTimeout(function() {
            setGeoPointMarker(lat_input, long_input, target, map)
        }, 1000)
    });
}

function setGeoPointMarker(lat_input, long_input, target, map) {
    let lat = parseFloat(lat_input.val())
    let long = parseFloat(long_input.val())
    let reset_view = false

    while (lat < -90) {
        lat += 180;
        reset_view = true
    }
    while (lat > 90) {
        lat -= 180;
        reset_view = true
    }
    while (long < -180) {
        long += 360;
        reset_view = true
    }
    while (long > 180) {
        long -= 360;
        reset_view = true
    }

    let coords = [lat, long]

    let last_marker_id = target.data('marker')
    if (last_marker_id) {
        map.removeLayer(GeoPointMarkers[last_marker_id])
        delete GeoPointMarkers[last_marker_id]
    }
    let marker = L.marker(coords)
    marker.addTo(map)
    GeoPointMarkers[marker._leaflet_id] = marker
    target.data('marker', marker._leaflet_id)
    if (reset_view) map.setView(coords, 13)
    return coords
}

// geo_point_input.val(`${long_input.val()},${lat_input.val()}`)