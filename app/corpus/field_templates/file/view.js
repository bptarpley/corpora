function renderFile(target) {
    let file_url = target.getAttribute('data-relative-path')
    if (!file_url) file_url = corpora.file_url(target.getAttribute('data-uri'))
    target.setAttribute('href', file_url)
}
