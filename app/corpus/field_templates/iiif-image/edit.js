var IIIFViewers = {}

function contentWidthOf(el) { return el ? el.clientWidth : 0 }

async function renderIIIFImage(target) {
    target = elFromEventOrEl(target)
    let editor_id = target.id

    IIIFViewers[editor_id] = {
        editor: target,
        image_uri: getVal(target),
        dragon_div: getEl(target.dataset.image_viewer),
        dragon: null,
        image_width: 0,
        image_height: 0,
        currently_showcasing: false,
        showcase_button: getEl(target.dataset.showcase_button),
        showcase_button_icon: getEl(`${target.dataset.showcase_button}-icon`),
        resize_timer: null
    }

    if (IIIFViewers[editor_id].image_uri) {
        let iiif = IIIFViewers[editor_id]
        try {
            await fetch(iiif.image_uri + '/info.json')
                .then(image_info => image_info.json())
                .then(image_info => {
                    let width = (3 * contentWidthOf(target.parentElement)) / 4
                    iiif.image_width = image_info.width
                    iiif.image_height = image_info.height
                    let ratio = iiif.image_width / iiif.image_height
                    let height = parseInt(width / ratio)
                    let max_height = Math.round(window.innerHeight - 50)

                    if (height > max_height) {
                        height = max_height
                        ratio = iiif.image_height / iiif.image_width
                        width = parseInt(height / ratio)
                    }

                    // clear image viewer, add showcase button, and set height
                    clearEl(iiif.dragon_div)
                    showEl(iiif.showcase_button)
                    iiif.dragon_div.style.width = `${width}px`
                    iiif.dragon_div.style.height = `${height}px`

                    iiif.dragon = OpenSeadragon({
                        id: iiif.dragon_div.id,
                        prefixUrl: "/static/img/openseadragon/",
                        preserveViewport: false,
                        visibilityRatio: 1,
                        minZoomLevel: .25,
                        maxZoomLevel: 5,
                        defaultZoomLevel: 1,
                        homeFillsViewer: true,
                        sequenceMode: false,
                        showRotationControl: true,
                        tileSources: [iiif.image_uri + '/info.json']
                    })
                    iiif.dragon.selection({
                        prefixUrl: "/static/img/openseadragonselection/",
                        allowRotation: false,
                        restrictToImage: true,
                        onSelection: function (rect) {
                            let image_region = `${iiif.image_uri}/${rect.x},${rect.y},${rect.width},${rect.height}/${rect.width},/0/default.jpg`
                            window.open(image_region, '_blank').focus()
                        }
                    })
                })
        } catch (error) {
            iiif.dragon_div.innerHTML = `
                <div class="alert alert-danger">
                    Not a valid IIIF Image API URL (should be similar to <b>https://my-iiif-server.org/iiif/3/path-to-image.jpg</b>).
                </div>
            `
            iiif.image_width = 0
            iiif.image_height = 0
        }
    }
}

function refreshTooltip(el) {
    if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) return
    let existing = bootstrap.Tooltip.getInstance(el)
    if (existing) existing.dispose()
    bootstrap.Tooltip.getOrCreateInstance(el)
}

function showcaseIIIFImage(target) {
    target = elFromEventOrEl(target)
    let editor_id = target.dataset.editor
    let iiif = IIIFViewers[editor_id]
    let already_showcasing = iiif.currently_showcasing
    let widget_col = getEl('edit-widget-col')

    clearEl(widget_col)

    if (already_showcasing) {
        window.hide_widget_col(function() {
            returnIIIFImage(iiif)
        })
    } else {
        window.show_widget_col(function() {
            Object.keys(IIIFViewers).forEach(editor_id => {
                if (IIIFViewers[editor_id].currently_showcasing) {
                    returnIIIFImage(IIIFViewers[editor_id])
                }
            })

            // appendChild moves the node, so the detach/appendTo pair collapses into one call
            widget_col.appendChild(iiif.dragon_div)
            iiif.dragon_div.style.height = '100vh'
            iiif.dragon_div.style.width = ''
            iiif.dragon_div.style.position = 'sticky'
            iiif.dragon_div.style.top = 0
            iiif.currently_showcasing = true
            iiif.showcase_button.setAttribute('title', 'Return image to below')
            refreshTooltip(iiif.showcase_button)
            iiif.showcase_button_icon.classList.remove('fa-angle-double-right')
            iiif.showcase_button_icon.classList.add('fa-angle-double-left')
        })
    }
    Object.keys(IIIFViewers).forEach(editor_id => {
        resizeIIIFViewer(IIIFViewers[editor_id].editor)
    })
}

function returnIIIFImage(iiif) {
    iiif.editor.parentElement.insertAdjacentElement('afterend', iiif.dragon_div)
    iiif.dragon_div.style.position = ''
    iiif.dragon_div.style.top = ''
    iiif.showcase_button.setAttribute('title', 'Showcase image on right')
    refreshTooltip(iiif.showcase_button)
    iiif.showcase_button_icon.classList.remove('fa-angle-double-left')
    iiif.showcase_button_icon.classList.add('fa-angle-double-right')
    renderIIIFImage(iiif.editor)
}

function resizeIIIFViewer(target) {
    target = elFromEventOrEl(target)
    let iiif = IIIFViewers[target.id]
    if (!iiif) return

    clearTimeout(iiif.resize_timer)
    iiif.resize_timer = setTimeout(function() {
        if (!iiif.currently_showcasing) {
            let width = (3 * contentWidthOf(iiif.editor.parentElement)) / 4
            let ratio = iiif.image_width / iiif.image_height
            let height = parseInt(width / ratio)
            let max_height = Math.round(window.innerHeight - 50)

            if (height > max_height) {
                height = max_height
                ratio = iiif.image_height / iiif.image_width
                width = parseInt(height / ratio)
            }
            iiif.dragon_div.style.height = `${height}px`
            iiif.dragon_div.style.width = `${width}px`
        }
        setTimeout(function() {
            if (iiif.dragon) iiif.dragon.viewport.goHome()
        }, 1000)
    }, 1000)
}
