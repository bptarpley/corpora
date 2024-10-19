function renderHTMLField(target) {
    tinymce.init(
        {
            selector: `#${target.id}`,
            width: '100%',
            min_height: '200px',
            plugins: 'autoresize link image media code table',
            menubar: 'edit insert media view format table tools help',
            image_advtab: true
        }
    )
}

function gatherHTMLFieldValue(target) {
    return tinymce.get(target.id).getContent()
}
