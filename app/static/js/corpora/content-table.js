class ContentTable {
    constructor(config={}) {
        this.table_id = 'table_id' in config ? config.table_id : null
        this.container_id = 'container_id' in config ? config.container_id : null
        this.corpora = 'corpora' in config ? config.corpora : null
        this.corpus = 'corpus' in config ? config.corpus : null
        this.content_type = 'content_type' in config ? config.content_type : null
        this.job_manager = 'job_manager' in config ? config.job_manager : null
        this.mode = 'mode' in config ? config.mode : 'edit'
        this.selection_callback = 'selection_callback' in config ? config.selection_callback : null
        this.give_search_focus = 'give_search_focus' in config ? config.give_search_focus : false
        this.search = 'search' in config ? config.search : {
            'page-size': 10,
        }
        this.search_timer = null
        this.on_load = 'on_load' in config ? config.on_load : null
        this.min_height = 'min_height' in config ? config.min_height : 100
        this.content_populated = false
        this.meta = null
        this.pages_loaded = new Set()
        this.pages_to_load = []
        this.total_pages = null
        this.currently_loading_pages = false
        this.overlapping_results = true
        this.loading_accelerated = false
        this.content_view = null
        this.content_view_id = null
        if ('content_view' in config && 'content_view_id' in config) {
            this.content_view = config.content_view
            this.content_view_id = config.content_view_id
            this.search['content_view'] = config.content_view
        }
        this.id_suffix = 0
        this.selected_content = {
            all: false,
            ids: []
        }

        if (this.container_id && this.corpora && this.corpus && this.content_type) {
            this.container = getEl(this.container_id)

            // local aliases purely for brevity in the markup below -- handlers use
            // `this` directly now that they are all arrow functions.
            let corpus_id = this.corpus.id
            let corpus = this.corpus
            let ct = this.corpus.content_types[this.content_type]
            let role = this.corpus.scholar_role
            let search = this.search
            this.label = 'label' in config ? config.label : ct.plural_name

            // ensure component ids will be unique
            while (getEl(`ct-${ct.name}${this.id_suffix}-table-body`)) this.id_suffix += 1
            let sfx = this.id_suffix

            // ensure multiselection form and deletion confirmation modal exist
            if (!getEl('multiselect-form') && this.mode === 'edit') {
                appendToEl(this.container, `
                    <form id="multiselect-form" method="post" action="/not/set">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${this.corpora.csrf_token}">
                        <input id="multiselect-content-ids" name="content-ids" type="hidden" value="">
                    </form>
                `)
            }
            if (!getEl('deletion-confirmation-modal') && this.mode === 'edit') {
                prependToEl(document.body, `
                    <div class="modal fade" id="deletion-confirmation-modal" tabindex="-1" role="dialog" aria-labelledby="deletion-confirmation-modal-label" aria-hidden="true">
                        <div class="modal-dialog">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title" id="deletion-confirmation-modal-label">Confirm Deletion</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close">
                                    </button>
                                </div>
                                <div class="modal-body">
                                    <div id="deletion-confirmation-modal-message" class="alert alert-danger"></div>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                    <button type="button" class="btn btn-primary" id="deletion-confirmation-button">Delete</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `)
                // CONTENT DELETION BUTTON
                onEl(getEl('deletion-confirmation-button'), 'click', () => {
                    let multi_form = getEl('multiselect-form')
                    appendToEl(multi_form, `
                        <input type='hidden' name='deletion-confirmed' value='y'/>
                    `)
                    multi_form.setAttribute('action', corpus.uri + '/')
                    multi_form.submit()
                })
            }

            let edit_action = ``
            if (this.mode === 'edit') {
                if (this.content_view) {
                    if (this.corpora.scholar_has_privilege('Editor', role)) {
                        edit_action = `
                            <button role="button" id="ct-${ct.name}${sfx}-refresh-view-button" class="btn btn-primary rounded me-2">Refresh View</button>
                            <button role="button" id="ct-${ct.name}${sfx}-delete-view-button" class="btn btn-primary rounded">Delete View</button>
                        `
                    }
                } else if (this.corpora.scholar_has_privilege('Contributor', role)) {
                    edit_action = `<a role="button" id="ct-${ct.name}${sfx}-new-button" href="/corpus/${corpus_id}/${ct.name}/" class="btn btn-primary rounded">Create</a>`
                }
            }

            appendToEl(this.container, `
                <div ${this.table_id ? `id="${this.table_id}" ` : ``}class="row corpora-content-table" data-content-type="${ct.name}">
                    <div class="col-12">
                        <a name="${ct.plural_name}"></a>
                        <div class="alert alert-info mt-4">
                            <h4>${this.label}</h4>
                            <div class="d-flex w-100 justify-content-between align-items-center text-nowrap my-2">
                                <span id="ct-${ct.name}${sfx}-total-badge" class="badge bg-secondary p-2 me-2">
                                    Total: 0
                                </span>
                                <div class="input-group me-2">
                                    <div class="input-group-prepend">
                                        <button id="ct-${ct.name}${sfx}-search-type-selection" class="btn btn-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false" style="border-top-right-radius: 0; border-bottom-right-radius: 0">Text Search</button>
                                        <div id="ct-${ct.name}${sfx}-search-type-menu" class="dropdown-menu">
                                            <span class="p-2">Select a specific field from the dropdown to the right in order to choose a different search type.</span>
                                        </div>
                                        <input type="hidden" id="ct-${ct.name}${sfx}-search-type-value" value="default" />
                                    </div>
                                    <input type="text" class="form-control" id="ct-${ct.name}${sfx}-search-box" placeholder="Search" style="border: solid 1px #091540;" />
                                    <div class="input-group-append">
                                        <button id="ct-${ct.name}${sfx}-search-setting-selection" class="btn btn-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false" style="border-top-left-radius: 0; border-bottom-left-radius: 0;">All Fields</button>
                                        <div id="ct-${ct.name}${sfx}-search-settings-menu" class="dropdown-menu">
                                            <a class="dropdown-item ct-${ct.name}${sfx}-search-setting" data-field_name="default" data-field_type="all" id="ct-${ct.name}${sfx}-search-setting-default" href="#">All Fields</a>
                                        </div>
                                        <input type="hidden" id="ct-${ct.name}${sfx}-search-setting-value" value="default" />
                                    </div>
                                </div>

                                <button id="ct-${ct.name}${sfx}-search-clear-button" class="btn btn-primary rounded me-2 d-none" type="button">Clear Search</button>
                                ${edit_action}   
                            </div>
                            <div id="ct-${ct.name}${sfx}-current-search-div" class="w-100 align-items-center my-2"></div>
                            ${ this.mode === 'edit' ? `<div id="ct-${ct.name}${sfx}-selection-action-div" class="w-100 justify-content-between align-items-center text-nowrap my-2">
                                <div class="form-inline">
                                    With selected:
                                    <select class="form-select-sm bg-primary mx-1" id="ct-${ct.name}${sfx}-selection-action-selector" data-ct="${ct.name}">
                                        <option value="explore" selected>Explore</option>
                                        <option value="export">Export (JSON)</option>
                                        <option value="export-csv">Export (CSV)</option>
                                        ${this.corpora.scholar_has_privilege('Contributor', role) ? '<option value="bulk-edit">Bulk Edit</option>' : ''}
                                        ${this.corpora.scholar_has_privilege('Contributor', role) ? '<option value="merge">Merge</option>' : ''}
                                        ${this.corpora.scholar_has_privilege('Editor', role) ? '<option value="create_view">Create View</option>' : ''}
                                        ${this.corpora.scholar_has_privilege('Contributor', role) ? '<option value="delete">Delete</option>' : ''}
                                    </select>
                                    <button type="button" class="btn btn-sm btn-secondary" id="ct-${ct.name}${sfx}-selection-action-go-button" data-ct="${ct.name}">Go</button>
                                </div>
                            </div>` : ''}

                            <div id="ct-${ct.name}${sfx}-table-container" class="card-body p-0 content-table-container">
                                <table class="table table-striped table-borderless mb-0">
                                    <thead class="thead-dark">
                                        <tr id="ct-${ct.name}${sfx}-table-header-row">
                                        </tr>
                                    </thead>
                                    <tbody id="ct-${ct.name}${sfx}-table-body">
                                    </tbody>
                                </table>
                            </div>
                            <div class="progress" style="height: 5px;">
                                <div id="ct-${ct.name}${sfx}-scroll-progress" class="progress-bar bg-secondary" role="progressbar" style="width: 0" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `)

            // setup view refreshing and deletion
            if (this.mode === 'edit' && (role === 'Editor' || role === 'Admin') && this.content_view) {
                onEl(getEl(`ct-${ct.name}${sfx}-refresh-view-button`), 'click', () => {
                    let submission = {
                        'cv-action': 'refresh',
                    }

                    this.corpora.make_request(
                        `/api/corpus/${corpus.id}/content-view/${this.content_view_id}/`,
                        'POST',
                        submission,
                        data => {
                            let refresh_button = getEl(`ct-${ct.name}${sfx}-refresh-view-button`)

                            if (data.status === 'populating') {
                                refresh_button.innerHTML = 'Refreshing...'
                                setDisabled(refresh_button)
                                this.corpora.await_content_view_population(corpus.id, data.id, () => {
                                    refresh_button.innerHTML = 'Refresh'
                                    setDisabled(refresh_button, false)
                                    this.pages_to_load = [{'page': 1}]
                                    this.load_pages()
                                })
                            } else {
                                refresh_button.innerHTML = 'Error with Refresh!'
                                setDisabled(refresh_button)
                            }
                        }
                    )
                })

                onEl(getEl(`ct-${ct.name}${sfx}-delete-view-button`), 'click', () => {
                    let multi_form = getEl('multiselect-form')
                    getEl('deletion-confirmation-modal-message').innerHTML = `
                        Are you sure you want to delete the "${this.label}" Content View?
                    `
                    appendToEl(multi_form, `
                        <input type='hidden' class="content-view-deletion-input" name='content-view' value='${this.content_view_id}'/>
                    `)
                    let deletion_modal = getEl('deletion-confirmation-modal')
                    onlyOnEl(deletion_modal, 'hidden.bs.modal', () => {
                        removeElsMatching('.content-view-deletion-input')
                    })
                    showModal(deletion_modal)
                })
            }

            // setup content type table headers
            let table_header_row = getEl(`ct-${ct.name}${sfx}-table-header-row`)
            appendToEl(table_header_row, `
                <th scope="col">
                    ${ this.mode === 'edit' ? `<input type="checkbox" id="ct_${ct.name}${sfx}_select-all_box" data-ct="${ct.name}">` : '' }
                </th>
            `)
            for (let x = 0; x < ct.fields.length; x++) {
                if (ct.fields[x].in_lists) {
                    let header_row_html = `
                        <th scope="col">
                            <a href="#" class="${ct.name}${sfx}-order-by" data-order-by="${ct.fields[x].type === 'cross_reference' ? ct.fields[x].name + '.label' : ct.fields[x].name}">${ct.fields[x].label}</a>
                        </th>
                    `
                    if (['geo_point', 'large_text'].includes(ct.fields[x].type)) {
                        header_row_html = `
                            <th scope="col">
                                ${ct.fields[x].label}
                            </th>
                        `
                    }
                    appendToEl(table_header_row, header_row_html)
                }
            }

            // handle order by event
            forElsMatching(`.${ct.name}${sfx}-order-by`, link => {
                onEl(link, 'click', e => {
                    e.preventDefault()
                    this.order_by(link.dataset.orderBy)
                })
            })

            if (this.mode === 'edit') {
                // handle select all box checking/unchecking
                let selection_action_div = getEl(`ct-${ct.name}${sfx}-selection-action-div`)
                this.toggle_drawer(selection_action_div, false)
                onEl(getEl(`ct_${ct.name}${sfx}_select-all_box`), 'change', event => {
                    let select_all = event.currentTarget
                    let ct_name = select_all.dataset.ct
                    let checked = select_all.checked

                    this.selected_content.all = checked
                    if (checked) this.selected_content.ids = []

                    forElsMatching(`.ct-${ct_name}${sfx}-selection-box`, box => {
                        box.checked = checked
                        setDisabled(box, checked)
                    })

                    // Merge exists to reconcile specific duplicates, so it only ever takes
                    // an explicit list of ids -- a select-all has no list to give it. Every
                    // other action either sends ids or falls back to the table's search.
                    let action_selector = getEl(`ct-${ct_name}${sfx}-selection-action-selector`)
                    let merge_option = getElWithQuery(`#ct-${ct_name}${sfx}-selection-action-selector option[value="merge"]`)
                    if (merge_option) {
                        setDisabled(merge_option, checked)
                        merge_option.innerHTML = checked ? 'Merge (select items individually)' : 'Merge'
                        // a disabled option stays selected, so move off it deliberately
                        if (checked && getVal(action_selector) === 'merge') setVal(action_selector, 'explore')
                    }

                    this.toggle_drawer(selection_action_div, checked)
                })

                // handle selection action "go" button click
                onEl(getEl(`ct-${ct.name}${sfx}-selection-action-go-button`), 'click', event => {
                    let ct_name = event.currentTarget.dataset.ct
                    let action = getVal(getEl(`ct-${ct.name}${sfx}-selection-action-selector`))
                    let multi_form = getEl('multiselect-form')
                    let content_ids_input = getEl('multiselect-content-ids')

                    if (this.selected_content.all) setVal(content_ids_input, 'all')
                    else setVal(content_ids_input, this.selected_content.ids.join(','))

                    // this launches the "explore content" action
                    if (action === 'explore') {
                        multi_form.setAttribute('action', `/corpus/${corpus_id}/${ct_name}/explore/`)
                        multi_form.submit()

                    // this launches the "bulk content edit" action
                    } else if (action === 'bulk-edit') {
                        multi_form.setAttribute('action', `/corpus/${corpus_id}/${ct_name}/`)
                        if (this.selected_content.all) {
                            // ids and search are mutually exclusive here as well: every
                            // consumer downstream tries ids first, so leaving 'all' in
                            // content-ids shadowed the search and edited nothing at all.
                            setVal(content_ids_input, '')
                            appendToEl(multi_form, `<input id='multiselect-content-query' type='hidden' name='content-query'>`)
                            setVal(getEl('multiselect-content-query'), JSON.stringify(search))
                        }
                        multi_form.submit()

                    // this launches the "export data to CSV" action
                    } else if (['export', 'export-csv'].includes(action)) {
                        let export_url = `/export/${corpus_id}/${ct_name}/`
                        let delimiter = '?'

                        if (action === 'export-csv') export_url += '?csv-format=true'

                        if (this.selected_content.all) {
                            Object.keys(search).forEach(param => {
                                export_url += `${delimiter}${param}=${search[param]}`
                                delimiter = '&'
                            })
                        } else {
                            export_url += `${delimiter}content-ids=${this.selected_content.ids.join(',')}`
                        }

                        let export_link = document.createElement('a')
                        export_link.href = export_url
                        export_link.setAttribute('download', `${ct_name}.json`)
                        document.body.appendChild(export_link)
                        export_link.click()
                        document.body.removeChild(export_link)

                    // this launches the "merge" action
                    } else if (action === 'merge') {
                        // Unreachable through the UI -- the option is disabled on
                        // select-all -- but the invariant matters: merge_content resolves
                        // its ids with id__in, so a literal 'all' raises on a non-ObjectId
                        // and 500s while the template renders.
                        if (this.selected_content.all) {
                            console.warn('Merge requires individually selected items; ignoring select-all.')
                            return
                        }
                        multi_form.setAttribute('action', `/corpus/${corpus_id}/${ct_name}/merge/`)
                        multi_form.submit()

                    // this launches the "delete" action
                    } else if (action === 'delete') {
                        // A select-all hands the server the table's search so it deletes
                        // the filtered subset; content-ids is cleared so it cannot shadow
                        // the search. Sending the literal 'all' instead -- with no search
                        // attached -- is what used to delete the entire content type.
                        // Everything appended here is removed again if the user cancels.
                        removeElsMatching('.content-deletion-input')
                        let deletion_modal = getEl('deletion-confirmation-modal')
                        let deleting_search = this.selected_content.all
                        let plural = corpus.content_types[ct_name].plural_name

                        appendToEl(multi_form, `
                            <input type='hidden' class='content-deletion-input' name='content-type' value='${ct_name}'/>
                        `)

                        if (deleting_search) {
                            setVal(content_ids_input, '')
                            appendToEl(multi_form, `
                                <input type='hidden' class='content-deletion-input' id='content-deletion-query' name='content-query'>
                            `)
                            // set as a property rather than an attribute so the JSON's
                            // quotes never have to survive HTML escaping
                            setVal(getEl('content-deletion-query'), JSON.stringify(search))
                        }

                        onlyOnEl(deletion_modal, 'hidden.bs.modal', () => {
                            removeElsMatching('.content-deletion-input')
                        })

                        let matching = this.meta && this.meta.total ? this.meta.total.toLocaleString('en-US') : ''
                        getEl('deletion-confirmation-modal-message').innerHTML = deleting_search
                            ? `Are you sure you want to delete all <b>${matching}</b> ${plural} matching the current search?`
                            : `Are you sure you want to delete the selected ${plural}?`
                        showModal(deletion_modal)

                    // this launches specific job tasks
                    } else if(this.job_manager !== null) {
                        if (this.selected_content.ids.length) {
                            this.job_manager.new_job(ct_name, this.selected_content.ids, action)
                        } else if (this.selected_content.all) {
                            this.job_manager.new_job(ct_name, search, action)
                        }
                    }
                })

                // populate content specific tasks
                if (this.job_manager !== null && this.corpora.scholar_has_privilege('Editor', role)) {
                    this.corpora.get_tasks(ct.name, tasks_data => {
                        // the API filters tasks by the scholar's permissions, but not by
                        // track_provenance -- which is what the job modal offers. Offering
                        // anything else here would submit a task the modal cannot select.
                        let launchable = tasks_data.filter(task => task.track_provenance)
                        if (!launchable.length) return

                        let options = launchable.map(task =>
                            `<option value="${task.id}">${task.name}</option>`
                        ).join('')

                        appendToEl(getEl(`ct-${ct.name}${sfx}-selection-action-selector`), `
                            <optgroup label="Launch Job">${options}</optgroup>
                        `)
                    })
                }
            }

            // setup content type search fields
            let search_settings_menu = getEl(`ct-${ct.name}${sfx}-search-settings-menu`)
            for (let x = 0; x < ct.fields.length; x++) {
                if (ct.fields[x].in_lists) {
                    appendToEl(search_settings_menu, `
                        <a class="dropdown-item ct-${ct.name}${sfx}-search-setting"
                            id="ct-${ct.name}${sfx}-search-setting-${x}"
                            data-field_name="${ct.fields[x].type === 'cross_reference' ? ct.fields[x].name + '.label' : ct.fields[x].name}"
                            data-field_type="${ct.fields[x].type}"
                            href="#">
                                ${ct.fields[x].label}
                        </a>
                    `)

                    // add cross reference sub field options
                    if (ct.fields[x].type === 'cross_reference') {
                        if (corpus.content_types.hasOwnProperty(ct.fields[x].cross_reference_type)) {
                            let cx = corpus.content_types[ct.fields[x].cross_reference_type]
                            for (let y = 0; y < cx.fields.length; y++) {
                                if (cx.fields[y].in_lists && cx.fields[y].type !== 'cross_reference') {
                                    appendToEl(search_settings_menu, `
                                        <a class="dropdown-item ct-${ct.name}${sfx}-search-setting"
                                            data-field-type="${cx.fields[y].type}"
                                            id="ct-${ct.name}${sfx}-search-setting-${x}.${y}"
                                            data-field_name="${ct.fields[x].name + '.' + cx.fields[y].name}"
                                            data-field_type="${cx.fields[y].type}"
                                            href="#">
                                                ${ct.fields[x].label} -> ${cx.fields[y].label}
                                        </a>
                                    `)
                                }
                            }
                        }
                    }
                }
            }

            // event for selecting a specific field to search
            forElsMatching(`.ct-${ct.name}${sfx}-search-setting`, field => {
              onEl(field, 'click', event => {
                event.preventDefault()
                let field_name = field.dataset.field_name
                let field_type = field.dataset.field_type
                let label = field.textContent
                let search_type_menu = getEl(`ct-${ct.name}${sfx}-search-type-menu`)

                if (field_name === 'default') {
                    search_type_menu.innerHTML = `
                        <span class="p-2">Select a specific field from the dropdown to the right in order to choose a different search type.</span>
                    `
                } else {
                    search_type_menu.innerHTML = `
                        <a class="dropdown-item ct-${ct.name}${sfx}-search-type" id="ct-${ct.name}${sfx}-search-type-default" href="#">Generic Search</a>
                        ${['text', 'large_text', 'keyword', 'html', 'number', 'decimal', 'boolean', 'date', 'timespan', 'file', 'link', 'iiif-image', 'geo_point', 'cross_reference'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sfx}-search-type" id="ct-${ct.name}${sfx}-search-type-exact" href="#">Exact Search</a>` : ''}
                        ${['text', 'large_text', 'keyword', 'html', 'cross_reference'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sfx}-search-type" id="ct-${ct.name}${sfx}-search-type-term" href="#">Term Search</a>` : ''}
                        ${['text', 'large_text', 'keyword', 'html', 'cross_reference'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sfx}-search-type" id="ct-${ct.name}${sfx}-search-type-phrase" href="#">Phrase Search</a>` : ''}
                        ${['text', 'large_text', 'keyword', 'html', 'cross_reference'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sfx}-search-type" id="ct-${ct.name}${sfx}-search-type-wildcard" href="#">Wildcard Search</a>` : ''}
                        ${['number', 'decimal', 'date', 'timespan', 'geo_point'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sfx}-search-type" id="ct-${ct.name}${sfx}-search-type-range" href="#">Range Search</a>` : ''}
                    `
                }

                // event for selecting a search type
                forElsMatching(`.ct-${ct.name}${sfx}-search-type`, type_link => {
                    onEl(type_link, 'click', type_event => {
                        type_event.preventDefault()
                        let search_type = type_link.id.replace(`ct-${ct.name}${sfx}-search-type-`, '')

                        getEl(`ct-${ct.name}${sfx}-search-type-selection`).textContent = type_link.textContent
                        setVal(getEl(`ct-${ct.name}${sfx}-search-type-value`), search_type)
                    })
                })

                getEl(`ct-${ct.name}${sfx}-search-setting-selection`).textContent = label
                setVal(getEl(`ct-${ct.name}${sfx}-search-setting-value`), field_name)
              })
            })

            // setup page break observer for infinite scroll
            this.page_observer = new IntersectionObserver(entries => {
                entries.forEach((entry, index) => {
                    if (entry.isIntersecting) {
                        let page_breaker = entry.target
                        let scroll_progress_bar = getEl(`ct-${ct.name}${sfx}-scroll-progress`)
                        let rec_num = page_breaker.dataset.record_num
                        let scroll_progress = Math.round((rec_num / this.meta.total) * 100)
                        let next_page = page_breaker.dataset.next_page

                        scroll_progress_bar.style.width = `${scroll_progress}%`
                        scroll_progress_bar.setAttribute('aria-valuenow', scroll_progress)

                        if (next_page) {
                            next_page = parseInt(next_page)
                            let next_page_token = page_breaker.dataset.next_page_token

                            if (!this.pages_loaded.has(next_page) && next_page <= this.total_pages) {
                                let already_loading = false
                                this.pages_to_load.forEach(p => {
                                    if (p['page'] === next_page) already_loading = true
                                })
                                if (!already_loading) {
                                    let page_info = {'page': next_page}
                                    if (next_page_token) page_info['page-token'] = next_page_token
                                    this.pages_to_load.push(page_info)
                                    if (!this.currently_loading_pages) this.load_pages(true)
                                }
                            }
                        }

                    }
                })
            })

            // setup search events
            onEl(getEl(`ct-${ct.name}${sfx}-search-box`), 'keypress', e => {
                clearTimeout(this.search_timer)
                if (e.key === 'Enter') {
                    this.do_search()
                } else this.search_timer = setTimeout(() => this.do_search(), 500)
            })

            onEl(getEl(`ct-${ct.name}${sfx}-search-clear-button`), 'click', event => {
                setVal(getEl(`ct-${ct.name}${sfx}-search-box`), '')
                for (let param in search) {
                    if (search.hasOwnProperty(param)) {
                        if (['q', 'page-token'].includes(param) || ['q_', 'f_', 't_', 'p_', 'w_', 'r_'].includes(param.slice(0, 2))) {
                            delete search[param]
                        }
                    }
                }
                getEl(`ct-${ct.name}${sfx}-search-setting-selection`).textContent = "All Fields"
                setVal(getEl(`ct-${ct.name}${sfx}-search-setting-value`), 'default')

                // was `search.pages_to_load`, which load_pages never reads -- so
                // clearing the search did not return you to page 1.
                this.pages_to_load = [{'page': 1}]
                this.load_pages()
            })

            // perform initial query of content based on search settings
            this.pages_to_load = [{'page': 1}]
            this.load_pages()
            if (this.give_search_focus) getEl(`ct-${ct.name}${sfx}-search-box`).focus()
        }
    }

    do_search() {
        let ct = this.corpus.content_types[this.content_type]
        let sfx = this.id_suffix
        let query = getVal(getEl(`ct-${ct.name}${sfx}-search-box`))
        let field = getVal(getEl(`ct-${ct.name}${sfx}-search-setting-value`))
        let search_type = getVal(getEl(`ct-${ct.name}${sfx}-search-type-value`))
        let search_type_map = {
            default: 'q',
            exact: 'f',
            term: 't',
            phrase: 'p',
            wildcard: 'w',
            range: 'r',
        }

        if (field === 'default') {
            this.search.q = query
        } else {
            let param_prefix = search_type_map[search_type]
            this.search[`${param_prefix}_${field}`] = query
        }

        getEl(`ct-${ct.name}${sfx}-search-clear-button`).classList.remove('d-none')
        this.pages_to_load = [{'page': 1}]
        this.load_pages()
    }

    async load_pages(add_to_existing_rows=false) {
        this.currently_loading_pages = true

        while (this.pages_to_load.length) {
            let page_info = this.pages_to_load[0]
            this.pages_loaded.add(page_info['page'])
            this.search['page'] = page_info.page
            if ('page-token' in page_info) this.search['page-token'] = page_info['page-token']

            await this.corpora.list_content(this.corpus.id, this.content_type, this.search, content => {
                this.total_pages = content.meta.num_pages
                this.load_content(content, add_to_existing_rows)
            })
            this.pages_to_load.shift()
        }
        this.currently_loading_pages = false
    }

    load_content(content, add_to_existing_rows=false) {
        let corpora = this.corpora
        let corpus = this.corpus
        let ct = corpus.content_types[content.meta.content_type]
        let search = this.search
        let sfx = this.id_suffix

        // instantiate some variables to keep track of elements
        let ct_table_body = getEl(`ct-${ct.name}${sfx}-table-body`)          // the table body for listing results
        let current_search_div = getEl(`ct-${ct.name}${sfx}-current-search-div`) // the search criteria div
        let total_indicator = getEl(`ct-${ct.name}${sfx}-total-badge`)       // the total indicator
        let has_filtering_criteria = false

        if (!add_to_existing_rows) {
            // clear the table body and search criteria div
            ct_table_body.innerHTML = ''
            current_search_div.innerHTML = ''
            this.pages_loaded.clear()

            // add the total number of results to the search criteria div
            total_indicator.innerHTML = `Total: ${content.meta.total.toLocaleString('en-US')}`
            total_indicator.dataset.total = content.meta.total

            // add existing search criteria to the div
            let has_search_indicators = false
            for (let search_setting in search) {
                if (search.hasOwnProperty(search_setting) && (search_setting === 'q' || ['q_', 'f_', 't_', 'p_', 'w_', 'r_', 's_'].includes(search_setting.slice(0, 2)))) {
                    let setting_type_map = {
                        q: 'Text searching',
                        f: 'Exact searching',
                        t: 'Term searching',
                        p: 'Phrase searching',
                        w: 'Wildcard searching',
                        r: 'Range searching',
                        s: 'Sorting'
                    }
                    let setting_type = setting_type_map[search_setting.slice(0, 1)]
                    let field = ""
                    let field_name = ""
                    let search_value = `${search[search_setting]}`

                    if (search_setting !== 'q') {
                        field = search_setting.substring(2)
                        let subfield = ""
                        if (field.includes('.')) {
                            let field_parts = field.split('.')
                            field = field_parts[0]
                            subfield = field_parts[1]
                        }

                        for (let x = 0; x < ct.fields.length; x++) {
                            if (ct.fields[x].name === field) {
                                field_name = ct.fields[x].label

                                if (subfield !== "" && ct.fields[x].type === 'cross_reference' && corpus.content_types.hasOwnProperty(ct.fields[x].cross_reference_type)) {
                                    let cx = corpus.content_types[ct.fields[x].cross_reference_type]
                                    for (let y = 0; y < cx.fields.length; y++) {
                                        if (cx.fields[y].name === subfield) {
                                            field_name += " -> " + cx.fields[y].label
                                        }
                                    }
                                }
                            }
                        }
                    }

                    if (setting_type === 'Searching') {
                        has_filtering_criteria = true;
                    }

                    appendToEl(current_search_div, `
                        <span class="badge bg-primary text-white p-2 me-2" style="font-size: 12px;">
                            ${setting_type} ${field_name} "${search_value}"
                            <a class="text-white ms-1 ${ct.name}${sfx}-remove-search-param" data-search-param="${search_setting}"><i class="far fa-times-circle"></i></a>
                        </span>
                    `)
                    has_search_indicators = true
                }
            }

            // show or hide search indicator drawer appropriately
            this.toggle_drawer(current_search_div, has_search_indicators)

            // remove search param event
            forElsMatching(`.${ct.name}${sfx}-remove-search-param`, link => {
                onlyOnEl(link, 'click', () => this.remove_search_param(link.dataset.searchParam))
            })
        }

        if (content.hasOwnProperty('meta')) this.meta = content.meta

        // if there are no search results, show a default message
        if (content.records.length < 1 && content.meta.page === 1) {
            let no_records_msg = `There are currently no ${ct.plural_name} in this corpus. Click the "Create" button above to create one.`
            if (has_filtering_criteria) {
                no_records_msg = `No ${ct.plural_name} in this corpus match your search criteria.`
            }

            let num_cols = 1
            for (let x = 0; x < ct.fields.length; x++) {
                if (ct.fields[x].in_lists) {
                    num_cols += 1
                }
            }

            let row_html = `
                <tr>
                    <td colspan="${num_cols}">
                        <div class="alert alert-warning m-0">
                            ${no_records_msg}
                        </div>
                    </td>
                </tr>
            `
            appendToEl(ct_table_body, row_html)

        // records exist, so populate the content type table with a page of results
        } else {
            // iterate through the records, adding a row for each one
            content.records.forEach((item, item_index) => {
                let load_item = true
                let rec_num = (item_index + 1) + ((content.meta.page - 1) * content.meta.page_size)

                if (this.overlapping_results)
                    if (getElWithQuery(`.${ct.name}${sfx}-content-row[data-corpora_id="${item.id}"]`))
                        load_item = false

                if (load_item) {
                    let selected = ''
                    if (this.selected_content.all) {
                        selected = "checked disabled"
                    } else if (this.selected_content.ids.includes(item.id)) {
                        selected = "checked"
                    }

                    let action_controls = `
                        <input id="ct_${ct.name}${sfx}_${item.id}_selection-box"
                            type="checkbox"
                            class="ct-${ct.name}${sfx}-selection-box me-2"
                            data-ct="${ct.name}"
                            data-id="${item.id}"
                            ${selected}>
                        <a href="${item.uri}" target="_blank">
                            <span class="badge bg-warning">Open</span>
                        </a>
                    `
                    if (this.mode === 'select') {
                        action_controls = `
                            <a href="#"
                                class="${ct.name}${sfx}-content-selection-link badge bg-warning"
                                data-id="${item.id}"
                                data-uri="${item.uri}"
                                data-label="${this.corpora.strip_html(item.label)}">
                                Select
                            </a>
                        `
                    } else if (this.mode === 'read-only') action_controls = ''

                    // infinite scroll page break indicators
                    let page_break_indicators = ''
                    if (content.meta.has_next_page) {
                        page_break_indicators = `data-next_page="${content.meta.page + 1}"`
                        if (content.meta.next_page_token) page_break_indicators += ` data-next_page_token="${content.meta.next_page_token}"`
                    }

                    let row_html = `
                        <tr class="${ct.name}${sfx}-content-row" data-corpora_id="${item.id}"
                            data-record_num="${rec_num}" ${page_break_indicators}>
                            <td class="ct-selection-cell">
                                ${action_controls}
                            </td>
                    `

                    ct.fields.map(field => {
                        if (field.in_lists) {
                            let value = ''
                            if (item.hasOwnProperty(field.name) && item[field.name] != null) {
                                value = this.format_column_value(item[field.name], field.type, field.multiple)
                            }

                            row_html += `
                                <td style="width: auto;">
                                    <div class="corpora-content-cell">
                                        ${value}
                                    </div>
                                </td>`
                        }
                    })

                    row_html += "</tr>"
                    appendToEl(ct_table_body, row_html)
                }
            })

            // remove any page breaker attributes for currently loaded page
            forElsMatching(`.${ct.name}${sfx}-content-row[data-next_page="${content.meta.page}"]`, row => {
                row.removeAttribute('data-next_page')
            })

            // make sure unobserved page breaker rows get observed
            forElsMatching(`.${ct.name}${sfx}-content-row:not([data-observed])`, row => {
                row.setAttribute('data-observed', 'true')
                this.page_observer.observe(row)
            })

            // accelerate loading of subsequent pages once first two are loaded
            if (!this.loading_accelerated && content.meta.page === 3) {
                this.search['page-size'] *= 10
                this.overlapping_results = true
                forElsMatching(`.${ct.name}${sfx}-content-row`, row => row.removeAttribute('data-next_page'))
                this.pages_loaded.clear()
                this.loading_accelerated = true
                this.pages_to_load = [{'page': 1}]
                this.load_pages(true)
            } else this.overlapping_results = false

            // conditionally scroll to top and set table height and make it resizable
            let table_container = getEl(`ct-${ct.name}${sfx}-table-container`)
            if (!add_to_existing_rows) table_container.scrollTop = 0

            if (!this.content_populated) {
                this.content_populated = true

                let height = table_container.offsetHeight
                let half_window_height = Math.round(window.innerHeight / 2)

                if (height > half_window_height) height = half_window_height
                if (height < this.min_height) height = this.min_height

                table_container.style.height = `${height}px`

                interact(table_container)
                    .resizable({
                        // resize from bottom only
                        edges: { bottom: true },

                        listeners: {
                            move (event) {
                                event.target.style.height = `${event.rect.height}px`
                            }
                        },
                        modifiers: [
                            // minimum size
                            interact.modifiers.restrictSize({
                                min: { height: 100 }
                            })
                        ],

                        inertia: true
                    })
                    .on('resizestart', () => {
                        table_container.style.overflowY = 'hidden'
                        table_container.style.userSelect = 'none'
                    })
                    .on('resizeend', () => {
                        table_container.style.overflowY = 'scroll'
                        table_container.style.userSelect = 'unset'
                    })
            }

            // handle smart link rendering
            forElsMatching('.corpora-content-link-cell:not([data-link_rendered])', cell => this.renderLink(cell))
        }

        // handle checking/unchecking content selection boxes
        // onlyOnEl, not onEl: load_content runs once per page of results and this
        // selector also matches boxes from pages already loaded, so plain binding
        // stacked a handler per page and pushed the same id repeatedly.
        forElsMatching(`.ct-${ct.name}${sfx}-selection-box`, box => {
            onlyOnEl(box, 'change', () => {
                let content_id = box.dataset.id
                let selection_action_div = getEl(`ct-${ct.name}${sfx}-selection-action-div`)

                if (box.checked) {
                    this.selected_content.ids.push(content_id)
                } else {
                    this.selected_content.ids = this.selected_content.ids.filter(id => id !== content_id)
                }

                this.toggle_drawer(selection_action_div, this.selected_content.ids.length > 0)
            })
        })

        // handle content selection in select mode
        if (this.mode === 'select') {
            forElsMatching(`.${ct.name}${sfx}-content-selection-link:not([data-click_rigged])`, link => {
                link.setAttribute('data-click_rigged', 'y')
                onEl(link, 'click', e => {
                    e.preventDefault()
                    if (this.selection_callback != null) {
                        this.selection_callback({
                            id: link.dataset.id,
                            uri: link.dataset.uri,
                            label: link.dataset.label
                        })
                    }
                })
            })
        }

        // callback if set by config
        if (typeof this.on_load === 'function') this.on_load(content.meta)
    }

    order_by(field) {
        let key = "s_" + field
        if (this.search.hasOwnProperty(key)) {
            if (this.search[key] === 'asc') {
                this.search[key] = 'desc'
            } else {
                this.search[key] = 'asc'
            }
        } else {
            this.search[key] = 'asc'
        }
        this.pages_to_load = [{'page': 1}]
        this.load_pages()
    }

    // shared show/hide for the two Bootstrap "drawers" in this table (the selection
    // action bar and the search-criteria bar). See toggleDrawer in utilities.js.
    toggle_drawer(drawer, visible) {
        toggleDrawer(drawer, visible)
    }

    remove_search_param(param) {
        if (this.search.hasOwnProperty(param)) {
            delete this.search[param]

            this.pages_to_load = [{'page': 1}]
            this.load_pages()
        }
    }

    format_column_value(field_value, field_type, is_multiple) {
        let formatted_values = []
        let raw_values = [field_value]
        let delimiter = ', '
        if (is_multiple) raw_values = field_value

        raw_values.forEach(value => {
            if (field_type === 'date') {
                value = this.corpora.date_string(value)
            } else if (field_type === 'html') {
                value = this.corpora.strip_html(value)
                delimiter = '<br />'
            } else if (field_type === 'timespan') {
                value = this.corpora.timespan_string(value)
            } else if (field_type === 'link') {
                value = `<div class="corpora-content-link-cell"
                    data-value="${value}"
                    data-label="${value}">    
                </div>`
            } else if (field_type === 'iiif-image') {
                value = `<img loading="lazy" src='${value}/full/,100/0/default.png' onerror="this.onerror=null; this.src=this.src.replace(/\\.png$/i, '.jpg');" />`
                delimiter = '<br />'
            } else if (field_type === 'file' && ['.png', '.jpg', '.gif', 'jpeg', '.tif'].includes(value.toLowerCase().substring(value.length - 4))) {
                value = `<img loading="lazy" src='/iiif/2/${value}/full/,100/0/default.png' />`
                delimiter = '<br />'
            } else if (field_type === 'large_text') {
                value = value.slice(0, 500) + '...'
            } else if (field_type === 'cross_reference') {
                value = `<a href="${value.uri}" target="_blank">${this.corpora.strip_html(value.label)}</a>`
            }
            formatted_values.push(value)
        })

        return formatted_values.join(delimiter)
    }

    async renderLink(target) {
        target.setAttribute('data-link_rendered', 'y')

        let url = target.getAttribute('data-value')
        let label = target.getAttribute('data-label')

        const link = document.createElement('a')
        link.href = url
        link.textContent = label
        link.target = '_blank'
        target.appendChild(link)

        try {
            const response = await fetch(url, {
                method: 'HEAD',
                mode: 'cors'
            })
            const contentType = response.headers.get('Content-Type')

            if (contentType && contentType.startsWith('image/')) {
                const thumbnail = document.createElement('img')

                thumbnail.src = url
                thumbnail.alt = label
                thumbnail.classList.add('p-md-1')
                thumbnail.style.maxWidth = '200px'
                thumbnail.style.maxHeight = '100px'
                thumbnail.style.cursor = 'pointer'
                thumbnail.onclick = () => window.open(url, '_blank')

                target.replaceChild(thumbnail, link)
            }
        } catch (error) {}
    }

}

