function renderFile(target) {
    let file_url = target.getAttribute('data-relative-path')
    if (!file_url) {
        let file_uri = target.getAttribute('data-uri')
        let is_image = target.getAttribute('data-is-image') === 'True'

        file_url = corpora.file_url(file_uri)

        if (is_image) {
            let width = parseInt(target.getAttribute('data-width'))
            let height = parseInt(target.getAttribute('data-height'))
            let size_spec = '200,'
            if (width > height) size_spec = ',200'

            target.innerHTML = `
                <img src="${corpora.image_url(file_uri)}full/${size_spec}/0/default.png" alt="${target.innerText}" />
            `
        }
    }
    target.setAttribute('href', file_url)
}
