function renderXrefField(target) {
    if (target.hasOwnProperty('target')) target = target.target
    let id_prefix = target.getAttribute('data-id_prefix')
    let ux = getXrefControls(id_prefix)

    if (!ux.value_input.val().length) {
        setupXrefSearch(id_prefix)
    }
}

function switchXrefMethod(target) {
    if (target.hasOwnProperty('target')) target = target.target
    let id_prefix = target.getAttribute('data-id_prefix')
    let ux = getXrefControls(id_prefix)

    if (ux.action === 'search') {
        ux.create_div.empty()
        ux.create_div.addClass('d-none')
        ux.search_div.removeClass('d-none')
        setupXrefSearch(id_prefix)
    } else {
        let message_id = corpora.generate_unique_id()

        ux.search_div.empty()
        ux.search_div.addClass('d-none')
        ux.create_div.removeClass('d-none')
        ux.create_div.empty()
        ux.create_div.append(`
            <iframe id="${id_prefix}-creation-iframe"
                src="/corpus/${corpus.id}/${ux.xref_content_type.name}/?popup=y&created_message_token=${message_id}"
                class="w-100 content-creation-iframe" />
        `)
        corpus.event_callbacks[message_id] = function (xref) {
            setXrefValue(id_prefix, xref)
            delete corpus.event_callbacks[message_id]
        }
        setTimeout(function() {
            let iframe = $(`#${id_prefix}-creation-iframe`)
            iframe.css('height', `${iframe[0].contentWindow.document.body.scrollHeight + 20}px`)
        }, 1000)
    }
}

function setupXrefSearch(id_prefix) {
    let ux = getXrefControls(id_prefix)
    ux.search_div.empty()
    let search_table = new ContentTable({
        label: `${ux.xref_content_type.plural_name}`,
        container_id: ux.search_div[0].id,
        corpora: corpora,
        corpus: corpus,
        mode: 'select',
        min_height: 300,
        content_type: ux.xref_content_type.name,
        selection_callback: (xref) => {
            ux.search_div.empty()
            setXrefValue(id_prefix, xref)
        }
    })
}

function setXrefValue(id_prefix, xref) {
    let ux = getXrefControls(id_prefix)
    ux.value_input.val(xref.id)
    ux.display_div.removeClass('d-none')
    ux.display_link.attr('href', xref.uri)
    ux.display_link.html(xref.label)
    ux.search_div.empty()
    ux.search_div.addClass('d-none')
    ux.create_div.empty()
    ux.create_div.addClass('d-none')
    ux.action_div.addClass('d-none')
}

function resetXrefField(target) {
    if (target.hasOwnProperty('target')) target = target.target
    let ux = getXrefControls(target.getAttribute('data-id_prefix'))

    ux.value_input.val('')
    ux.display_div.addClass('d-none')
    ux.action_div.removeClass('d-none')
    ux.action_create_radio.attr('checked', false)
    ux.action_search_radio.attr('checked', true)
    switchXrefMethod(target)
}

function getXrefControls(id_prefix) {
    let controls = {
        display_div: $(`#${id_prefix}-display-div`),
        display_link: $(`#${id_prefix}-link`),
        action_div: $(`#${id_prefix}-action-div`),
        action: $(`[name="${id_prefix}-action-radio"]:checked`).val(),
        action_search_radio: $(`#${id_prefix}-search-action-radio`),
        action_create_radio: $(`#${id_prefix}-create-action-radio`),
        search_div: $(`#${id_prefix}-search-div`),
        create_div: $(`#${id_prefix}-create-div`),
        value_input: $(`#${id_prefix}-value`),
    }

    let field_name = controls.value_input.data('field_name')
    corpus.content_types[content_type].fields.forEach(f => {
        if (f.name === field_name) controls['xref_content_type'] = corpus.content_types[f.cross_reference_type]
    })

    return controls
}