function renderIIIFImage(target) {
    let image_uri = target.getAttribute('data-iiif_uri')
    let dragon = null
    let selection = null

    fetch(image_uri + '/info.json')
        .then(image_info => image_info.json())
        .then(image_info => {
            let width = target.parentElement.clientWidth
            let image_width = image_info.width
            let image_height = image_info.height
            let ratio = image_width / image_height
            let height = parseInt(width / ratio)

            target.setAttribute('style', `width: 100%; height: ${height}px;`)
            dragon = OpenSeadragon({
                id:                 target.id,
                prefixUrl:          "/static/img/openseadragon/",
                preserveViewport:   false,
                visibilityRatio:    1,
                minZoomLevel:       .25,
                maxZoomLevel:       5,
                defaultZoomLevel:   1,
                homeFillsViewer:    true,
                wrapHorizontal:     true,
                wrapVertical:       true,
                sequenceMode:       false,
                showRotationControl: true,
                tileSources:   [image_uri + '/info.json']
            })
            selection = dragon.selection({
                prefixUrl: "/static/img/openseadragonselection/",
                allowRotation: false,
                restrictToImage: true,
                onSelection: function(rect) {
                    let image_region = `${image_uri}/${rect.x},${rect.y},${rect.width},${rect.height}/${rect.width},/0/default.jpg`
                    window.open(image_region, '_blank').focus()
                }
            })
        })
}