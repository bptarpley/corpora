function renderXrefField(target) {
    target = elFromEventOrEl(target)
    let id_prefix = target.getAttribute('data-id_prefix')
    let ux = getXrefControls(id_prefix)

    if (!getVal(ux.value_input).length) {
        setupXrefSearch(id_prefix)
    }
}

function switchXrefMethod(target) {
    target = elFromEventOrEl(target)
    let id_prefix = target.getAttribute('data-id_prefix')
    let ux = getXrefControls(id_prefix)

    if (ux.action === 'search') {
        clearEl(ux.create_div)
        hideEl(ux.create_div)
        showEl(ux.search_div)
        setupXrefSearch(id_prefix)
    } else {
        let message_id = corpora.generate_unique_id()

        clearEl(ux.search_div)
        hideEl(ux.search_div)
        showEl(ux.create_div)
        clearEl(ux.create_div)
        appendToEl(ux.create_div, `
            <iframe id="${id_prefix}-creation-iframe"
                src="/corpus/${corpus.id}/${ux.xref_content_type.name}/?popup=y&created_message_token=${message_id}"
                class="w-100 content-creation-iframe" />
        `)
        corpus.event_callbacks[message_id] = function (xref) {
            setXrefValue(id_prefix, xref)
            delete corpus.event_callbacks[message_id]
        }
        setTimeout(function() {
            let iframe = getEl(`${id_prefix}-creation-iframe`)
            if (iframe) iframe.style.height = `${iframe.contentWindow.document.body.scrollHeight + 20}px`
        }, 1000)
    }
}

function setupXrefSearch(id_prefix) {
    let ux = getXrefControls(id_prefix)
    let give_search_focus = !!ux.search_div.closest('.multi-cross_reference-col')

    clearEl(ux.search_div)

    let search_table = new ContentTable({
        label: `${ux.xref_content_type.plural_name}`,
        container_id: ux.search_div.id,
        corpora: corpora,
        corpus: corpus,
        mode: 'select',
        min_height: 300,
        give_search_focus: give_search_focus,
        content_type: ux.xref_content_type.name,
        selection_callback: (xref) => {
            clearEl(ux.search_div)
            setXrefValue(id_prefix, xref)
        }
    })
}

function setXrefValue(id_prefix, xref) {
    let ux = getXrefControls(id_prefix)
    setVal(ux.value_input, xref.id)
    showEl(ux.display_div)
    ux.display_link.setAttribute('href', xref.uri)
    ux.display_link.innerHTML = xref.label
    clearEl(ux.search_div)
    hideEl(ux.search_div)
    clearEl(ux.create_div)
    hideEl(ux.create_div)
    hideEl(ux.action_div)
}

function resetXrefField(target) {
    target = elFromEventOrEl(target)
    let ux = getXrefControls(target.getAttribute('data-id_prefix'))

    setVal(ux.value_input, '')
    hideEl(ux.display_div)
    showEl(ux.action_div)
    setChecked(ux.action_create_radio, false)
    setChecked(ux.action_search_radio, true)
    switchXrefMethod(target)
}

function getXrefControls(id_prefix) {
    let checked_action = getElWithQuery(`[name="${id_prefix}-action-radio"]:checked`)
    let controls = {
        display_div: getEl(`${id_prefix}-display-div`),
        display_link: getEl(`${id_prefix}-link`),
        action_div: getEl(`${id_prefix}-action-div`),
        action: checked_action ? checked_action.value : undefined,
        action_search_radio: getEl(`${id_prefix}-search-action-radio`),
        action_create_radio: getEl(`${id_prefix}-create-action-radio`),
        search_div: getEl(`${id_prefix}-search-div`),
        create_div: getEl(`${id_prefix}-create-div`),
        value_input: getEl(`${id_prefix}-value`),
    }

    let field_name = controls.value_input.dataset.field_name
    corpus.content_types[content_type].fields.forEach(f => {
        if (f.name === field_name) controls['xref_content_type'] = corpus.content_types[f.cross_reference_type]
    })

    return controls
}
