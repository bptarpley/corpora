function renderFileField(target) {
    target = elFromEventOrEl(target)
    let file_link = getEl(target.dataset.file_link)
    let file_link_div = getEl(target.dataset.file_link_div)
    let value_control = getEl(target.dataset.value_control)

    if (target.dataset.value) {
        let file_uri = `${target.dataset.parent_uri}/file/${target.dataset.key}`
        file_link.setAttribute('href', `${corpora.file_url(file_uri)}`)
        setVal(value_control, '/' + target.dataset.value.split('/').slice(7).join('/'))
        hideEl(target)
    } else {
        let pond = FilePond.create(target, {
            allowMultiple: false,
            chunkUploads: true,
            chunkSize: 5000000,
            credits: false,
            server: {
                url: '/fp',
                process: '/process/',
                patch: '/patch/',
                revert: '/revert/',
                fetch: '/fetch/?target=',
                headers: {'X-CSRFToken': target.dataset.csrf}
            }
        })

        pond.on('processfile', (error, file) => {
            if (!error) {
                setVal(value_control, file.serverId)
            }
        })

        pond.on('removefile', () => setVal(value_control, ''))

        hideEl(file_link_div)
    }
}

function resetFileField(target) {
    target = elFromEventOrEl(target)
    let editor = getEl(target.dataset.editor)
    let value_control = getEl(target.dataset.value_control)

    setVal(value_control, '')
    editor.dataset.value = ''
    showEl(editor)
    renderFileField(editor)
}
