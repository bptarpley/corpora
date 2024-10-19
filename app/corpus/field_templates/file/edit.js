function renderFileField(target) {
    if (target.hasOwnProperty('target')) target = target.target
    target = $(target)
    let file_link = $(`#${target.data('file_link')}`)
    let file_link_div = $(`#${target.data('file_link_div')}`)
    let value_control = $(`#${target.data('value_control')}`)

    if (target.data('value')) {
        let file_uri = `${target.data('parent_uri')}/file/${target.data('key')}`
        file_link.attr('href', `${corpora.file_url(file_uri)}`)
        value_control.val('/' + target.data('value').split('/').slice(7).join('/'))
        target.addClass('d-none')
    } else {
        let pond = FilePond.create(target[0], {
            allowMultiple: false,
            chunkUploads: true,
            chunkSize: 500000,
            credits: false,
            server: {
                url: '/fp',
                process: '/process/',
                patch: '/patch/',
                revert: '/revert/',
                fetch: '/fetch/?target=',
                headers: {'X-CSRFToken': target.data('csrf')}
            }
        })

        pond.on('processfile', (error, file) => {
            if(!error) {
                value_control.val(file.serverId)
            }
        })

        pond.on('removefile', () => value_control.val(''))

        file_link_div.addClass('d-none')
    }
}

function resetFileField(target) {
    if (target.hasOwnProperty('target')) target = target.target
    target = $(target)
    let editor = $(`#${target.data('editor')}`)
    let value_control = $(`#${target.data('value_control')}`)

    value_control.val('')
    editor.data('value', '')
    editor.removeClass('d-none')
    renderFileField(editor[0])
}