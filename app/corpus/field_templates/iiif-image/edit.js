var IIIFViewers = {}

async function renderIIIFImage(target) {
    if (target.hasOwnProperty('target')) target = target.target
    let editor_id = target.id
    target = $(target)

    IIIFViewers[editor_id] = {
        editor: target,
        image_uri: target.val(),
        dragon_div: $(`#${target.data('image_viewer')}`),
        dragon: null,
        image_width: 0,
        image_height: 0,
        currently_showcasing: false,
        showcase_button: $(`#${target.data('showcase_button')}`),
        showcase_button_icon: $(`#${target.data('showcase_button')}-icon`),
        resize_timer: null
    }

    if (IIIFViewers[editor_id].image_uri) {
        let iiif = IIIFViewers[editor_id]
        try {
            await fetch(iiif.image_uri + '/info.json')
                .then(image_info => image_info.json())
                .then(image_info => {
                    let width = (3 * target.parent().width()) / 4
                    iiif.image_width = image_info.width
                    iiif.image_height = image_info.height
                    let ratio = iiif.image_width / iiif.image_height
                    let height = parseInt(width / ratio)
                    let max_height = Math.round($(window).height() - 50)

                    if (height > max_height) {
                        height = max_height
                        ratio = iiif.image_height / iiif.image_width
                        width = parseInt(height / ratio)
                    }

                    // clear image viewer, add showcase button, and set height
                    iiif.dragon_div.empty()
                    iiif.showcase_button.removeClass('d-none')
                    iiif.dragon_div.css('width', `${width}px`)
                    iiif.dragon_div.css('height', `${height}px`)

                    iiif.dragon = OpenSeadragon({
                        id: iiif.dragon_div[0].id,
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
            iiif.dragon_div.empty()
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

function showcaseIIIFImage(target) {
    if (target.hasOwnProperty('currentTarget')) target = target.currentTarget
    let editor_id = $(target).data('editor')
    let iiif = IIIFViewers[editor_id]
    let already_showcasing = iiif.currently_showcasing
    let widget_col = $('#edit-widget-col')

    widget_col.empty()

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

            iiif.dragon_div = iiif.dragon_div.detach()
            iiif.dragon_div.appendTo(widget_col)
            iiif.dragon_div.css('height', `100vh`)
            iiif.dragon_div.css('width', '')
            iiif.dragon_div.css('position', 'sticky')
            iiif.dragon_div.css('top', 0)
            iiif.currently_showcasing = true
            iiif.showcase_button.attr('title', 'Return image to below')
            iiif.showcase_button.tooltip('dispose')
            iiif.showcase_button.tooltip()
            iiif.showcase_button_icon.removeClass('fa-angle-double-right')
            iiif.showcase_button_icon.addClass('fa-angle-double-left')
        })
    }
    Object.keys(IIIFViewers).forEach(editor_id => {
        resizeIIIFViewer(IIIFViewers[editor_id].editor[0])
    })
}

function returnIIIFImage(iiif) {
    iiif.dragon_div = iiif.dragon_div.detach()
    iiif.editor.parent().after(iiif.dragon_div)
    iiif.dragon_div.css('position', '')
    iiif.dragon_div.css('top', '')
    iiif.showcase_button.attr('title', 'Showcase image on right')
    iiif.showcase_button.tooltip('dispose')
    iiif.showcase_button.tooltip()
    iiif.showcase_button_icon.removeClass('fa-angle-double-left')
    iiif.showcase_button_icon.addClass('fa-angle-double-right')
    renderIIIFImage(iiif.editor[0])
}

function resizeIIIFViewer(target) {
    if (target.hasOwnProperty('target')) target = target.target
    let iiif = IIIFViewers[target.id]

    clearTimeout(iiif.resize_timer)
    iiif.resize_timer = setTimeout(function() {
        if (!iiif.currently_showcasing) {
            let width = (3 * iiif.editor.parent().width()) / 4
            let ratio = iiif.image_width / iiif.image_height
            let height = parseInt(width / ratio)
            let max_height = Math.round($(window).height() - 50)

            if (height > max_height) {
                height = max_height
                ratio = iiif.image_height / iiif.image_width
                width = parseInt(height / ratio)
            }
            iiif.dragon_div.css('height', `${height}px`)
            iiif.dragon_div.css('width', `${width}px`)
        }
        setTimeout(function() {
            iiif.dragon.viewport.goHome()
        }, 1000)
    }, 1000)
}