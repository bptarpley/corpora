class ContentTable {
    constructor(config={}) {
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
            this.container = $(`#${this.container_id}`)

            // shortcut vars for quick access (and also to circumvent "this.x" issue in events)
            let corpora = this.corpora
            let corpus_id = this.corpus.id
            let corpus = this.corpus
            let ct = this.corpus.content_types[this.content_type]
            let role = this.corpus.scholar_role
            let search = this.search
            this.label = 'label' in config ? config.label : ct.plural_name
            let sender = this

            // ensure component ids will be unique
            while ($(`#ct-${ct.name}${sender.id_suffix}-table-body`).length) sender.id_suffix += 1

            // ensure multiselection form and deletion confirmation modal exist
            if (!$('#multiselect-form').length && sender.mode === 'edit') {
                this.container.append(`
                    <form id="multiselect-form" method="post" action="/not/set">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${this.corpora.csrf_token}">
                        <input id="multiselect-content-ids" name="content-ids" type="hidden" value="">
                    </form>
                `)
            }
            if (!$('#deletion-confirmation-modal').length && sender.mode === 'edit') {
                $('body').prepend(`
                    <div class="modal fade" id="deletion-confirmation-modal" tabindex="-1" role="dialog" aria-labelledby="deletion-confirmation-modal-label" aria-hidden="true">
                        <div class="modal-dialog">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title" id="deletion-confirmation-modal-label">Confirm Deletion</h5>
                                    <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                    <span aria-hidden="true">&times;</span>
                                    </button>
                                </div>
                                <div class="modal-body">
                                    <div id="deletion-confirmation-modal-message" class="alert alert-danger"></div>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                                    <button type="button" class="btn btn-primary" id="deletion-confirmation-button">Delete</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `)
                // CONTENT DELETION BUTTON
                $('#deletion-confirmation-button').click(function() {
                    let multi_form = $('#multiselect-form')
                    multi_form.append(`
                        <input type='hidden' name='deletion-confirmed' value='y'/>
                    `)
                    multi_form.attr('action', corpus.uri + '/')
                    multi_form.submit()
                })
            }

            let edit_action = ``
            if (sender.mode === 'edit') {
                if (sender.content_view) {
                    if (sender.corpora.scholar_has_privilege('Editor', role)) {
                        edit_action = `
                            <button role="button" id="ct-${ct.name}${sender.id_suffix}-refresh-view-button" class="btn btn-primary rounded mr-2">Refresh View</button>
                            <button role="button" id="ct-${ct.name}${sender.id_suffix}-delete-view-button" class="btn btn-primary rounded">Delete View</button>
                        `
                    }
                } else if (sender.corpora.scholar_has_privilege('Contributor', role)) {
                    edit_action = `<a role="button" id="ct-${ct.name}${sender.id_suffix}-new-button" href="/corpus/${corpus_id}/${ct.name}/" class="btn btn-primary rounded">Create</a>`
                }
            }

            this.container.append(`
                <div class="row corpora-content-table" data-content-type="${ct.name}">
                    <div class="col-12">
                        <a name="${ct.plural_name}"></a>
                        <div class="alert alert-info mt-4">
                            <h4>${sender.label}</h4>
                            <div class="d-flex w-100 justify-content-between align-items-center text-nowrap my-2">
                                <span id="ct-${ct.name}${sender.id_suffix}-total-badge" class="badge badge-secondary p-2 mr-2">
                                    Total: 0
                                </span>
                                <div class="input-group mr-2">
                                    <div class="input-group-prepend">
                                        <button id="ct-${ct.name}${sender.id_suffix}-search-type-selection" class="btn btn-secondary dropdown-toggle" type="button" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">Text Search</button>
                                        <div id="ct-${ct.name}${sender.id_suffix}-search-type-menu" class="dropdown-menu">
                                            <span class="p-2">Select a specific field from the dropdown to the right in order to choose a different search type.</span>
                                        </div>
                                        <input type="hidden" id="ct-${ct.name}${sender.id_suffix}-search-type-value" value="default" />
                                    </div>
                                    <input type="text" class="form-control" id="ct-${ct.name}${sender.id_suffix}-search-box" placeholder="Search" style="border: solid 1px #091540;" />
                                    <div class="input-group-append">
                                        <button id="ct-${ct.name}${sender.id_suffix}-search-setting-selection" class="btn btn-secondary dropdown-toggle" type="button" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">All Fields</button>
                                        <div id="ct-${ct.name}${sender.id_suffix}-search-settings-menu" class="dropdown-menu">
                                            <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-setting" data-field_name="default" data-field_type="all" id="ct-${ct.name}${sender.id_suffix}-search-setting-default" href="#">All Fields</a>
                                        </div>
                                        <input type="hidden" id="ct-${ct.name}${sender.id_suffix}-search-setting-value" value="default" />
                                    </div>
                                </div>

                                <button id="ct-${ct.name}${sender.id_suffix}-search-clear-button" class="btn btn-primary rounded mr-2 d-none" type="button">Clear Search</button>
                                ${edit_action}   
                            </div>
                            <div id="ct-${ct.name}${sender.id_suffix}-current-search-div" class="w-100 align-items-center my-2"></div>
                            ${ sender.mode === 'edit' ? `<div id="ct-${ct.name}${sender.id_suffix}-selection-action-div" class="w-100 justify-content-between align-items-center text-nowrap my-2">
                                <div class="form-inline">
                                    With selected:
                                    <select class="form-control-sm btn-primary ml-1 mr-1" id="ct-${ct.name}${sender.id_suffix}-selection-action-selector" data-ct="${ct.name}">
                                        <option value="explore" selected>Explore</option>
                                        <option value="export">Export (JSON)</option>
                                        <option value="export-csv">Export (CSV)</option>
                                        ${sender.corpora.scholar_has_privilege('Contributor', role) ? '<option value="bulk-edit">Bulk Edit</option>' : ''}
                                        ${sender.corpora.scholar_has_privilege('Contributor', role) ? '<option value="merge">Merge</option>' : ''}
                                        ${sender.corpora.scholar_has_privilege('Editor', role) ? '<option value="create_view">Create View</option>' : ''}
                                        ${sender.corpora.scholar_has_privilege('Contributor', role) ? '<option value="delete">Delete</option>' : ''}
                                    </select>
                                    <button type="button" class="btn btn-sm btn-secondary" id="ct-${ct.name}${sender.id_suffix}-selection-action-go-button" data-ct="${ct.name}">Go</button>
                                </div>
                            </div>` : ''}

                            <div id="ct-${ct.name}${sender.id_suffix}-table-container" class="card-body p-0 content-table-container">
                                <table class="table table-striped mb-0">
                                    <thead class="thead-dark">
                                        <tr id="ct-${ct.name}${sender.id_suffix}-table-header-row">
                                        </tr>
                                    </thead>
                                    <tbody id="ct-${ct.name}${sender.id_suffix}-table-body">
                                    </tbody>
                                </table>
                            </div>
                            <div class="progress" style="height: 5px;">
                                <div id="ct-${ct.name}${sender.id_suffix}-scroll-progress" class="progress-bar bg-secondary" role="progressbar" style="width: 0" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `)

            // setup view refreshing and deletion
            if (sender.mode === 'edit' && (role === 'Editor' || role === 'Admin') && sender.content_view) {
                $(`#ct-${ct.name}${sender.id_suffix}-refresh-view-button`).click(function() {
                    let submission = {
                        'cv-action': 'refresh',
                    }

                    sender.corpora.make_request(
                        `/api/corpus/${corpus.id}/content-view/${sender.content_view_id}/`,
                        'POST',
                        submission,
                        function (data) {
                            let refresh_button = $(`#ct-${ct.name}${sender.id_suffix}-refresh-view-button`)

                            if (data.status === 'populating') {
                                refresh_button.html('Refreshing...')
                                refresh_button.attr('disabled', true)
                                sender.corpora.await_content_view_population(corpus.id, data.id, function(data) {
                                    refresh_button.html('Refresh')
                                    refresh_button.attr('disabled', false)
                                    sender.pages_to_load = [{'page': 1}]
                                    sender.load_pages()
                                })
                            } else {
                                refresh_button.html('Error with Refresh!')
                                refresh_button.attr('disabled', true)
                            }
                        }
                    )
                })

                $(`#ct-${ct.name}${sender.id_suffix}-delete-view-button`).click(function() {
                    let multi_form = $('#multiselect-form')
                    $('#deletion-confirmation-modal-message').html(`
                        Are you sure you want to delete the "${sender.label}" Content View?
                    `)
                    multi_form.append(`
                        <input type='hidden' class="content-view-deletion-input" name='content-view' value='${sender.content_view_id}'/>
                    `)
                    let deletion_modal = $('#deletion-confirmation-modal')
                    deletion_modal.modal()
                    deletion_modal.on('hidden.bs.modal', function (e) {
                        $('.content-view-deletion-input').remove()
                    })
                })
            }

            // setup content type table headers
            let table_header_row = $(`#ct-${ct.name}${sender.id_suffix}-table-header-row`)
            table_header_row.append(`
                <th scope="col">
                    ${ sender.mode === 'edit' ? `<input type="checkbox" id="ct_${ct.name}${sender.id_suffix}_select-all_box" data-ct="${ct.name}">` : '' }
                </th>
            `)
            for (let x = 0; x < ct.fields.length; x++) {
                if (ct.fields[x].in_lists) {
                    let header_row_html = `
                        <th scope="col">
                            <a href="#" class="${ct.name}${sender.id_suffix}-order-by" data-order-by="${ct.fields[x].type === 'cross_reference' ? ct.fields[x].name + '.label' : ct.fields[x].name}">${ct.fields[x].label}</a>
                        </th>
                    `
                    if (['geo_point', 'large_text'].includes(ct.fields[x].type)) {
                        header_row_html = `
                            <th scope="col">
                                ${ct.fields[x].label}
                            </th>
                        `
                    }
                    table_header_row.append(header_row_html)
                }
            }

            // handle order by event
            $(`.${ct.name}${sender.id_suffix}-order-by`).click(function(e) {
                e.preventDefault()
                sender.order_by($(this).data('order-by'))
            })

            if (sender.mode === 'edit') {
                // handle select all box checking/unchecking
                let selection_action_div = $(`#ct-${ct.name}${sender.id_suffix}-selection-action-div`)
                selection_action_div.hide()
                $(`#ct_${ct.name}${sender.id_suffix}_select-all_box`).change(function () {
                    let ct_name = $(this).data('ct')

                    if ($(this).is(':checked')) {
                        sender.selected_content.all = true
                        sender.selected_content.ids = []

                        $(`.ct-${ct_name}${sender.id_suffix}-selection-box`).each(function () {
                            $(this).prop("checked", true)
                            $(this).attr("disabled", true)
                        })

                        selection_action_div.slideDown('slow', 'swing', function() {
                            selection_action_div.addClass('d-flex')
                        })
                    } else {
                        sender.selected_content.all = false
                        $(`.ct-${ct_name}${sender.id_suffix}-selection-box`).each(function () {
                            $(this).prop("checked", false)
                            $(this).removeAttr("disabled")
                        })

                        selection_action_div.removeClass('d-flex')
                        selection_action_div.hide()
                    }
                })

                // handle selection action "go" button click
                $(`#ct-${ct.name}${sender.id_suffix}-selection-action-go-button`).click(function() {
                    let ct_name = $(this).data('ct')
                    let action = $(`#ct-${ct.name}${sender.id_suffix}-selection-action-selector`).val()
                    let multi_form = $('#multiselect-form')
                    let content_ids_input = $('#multiselect-content-ids')

                    if (sender.selected_content.all) content_ids_input.val('all')
                    else content_ids_input.val(sender.selected_content.ids.join(','))

                    if (action === 'explore') {
                        multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/explore/`)
                        multi_form.submit()
                    } else if (action === 'bulk-edit') {
                        multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/`)
                        if (sender.selected_content.all) {
                            multi_form.append(`<input id='multiselect-content-query' type='hidden' name='content-query'>`)
                            $('#multiselect-content-query').val(JSON.stringify(search))
                        }
                        multi_form.submit()
                    } else if (['export', 'export-csv'].includes(action)) {
                        let export_url = `/export/${corpus_id}/${ct_name}/`
                        let delimiter = '?'

                        if (action === 'export-csv') export_url += '?csv-format=true'

                        if (sender.selected_content.all) {
                            Object.keys(search).forEach(param => {
                                export_url += `${delimiter}${param}=${search[param]}`
                                delimiter = '&'
                            })
                        } else {
                            export_url += `${delimiter}content-ids=${sender.selected_content.ids.join(',')}`
                        }

                        let export_link = document.createElement('a')
                        export_link.href = export_url
                        export_link.setAttribute('dowload', `${ct_name}.json`)
                        document.body.appendChild(export_link)
                        export_link.click()
                        document.body.removeChild(export_link)


                    } else if (action === 'merge') {
                        multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/merge/`)
                        multi_form.submit()
                    } else if (action === 'delete') {
                        $('#deletion-confirmation-modal-message').html(`
                            Are you sure you want to delete the selected ${corpus.content_types[ct_name].plural_name}?
                        `)
                        multi_form.append(`
                            <input type='hidden' name='content-type' value='${ct_name}'/>
                        `)
                        $('#deletion-confirmation-modal').modal()
                    } else {
                        if (sender.selected_content.ids.length > 1 || sender.selected_content.all || sender.job_manager === null) {
                            multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/bulk-job-manager/`)
                            multi_form.append(`
                                <input type='hidden' name='task-id' value='${action}'/>
                            `)
                            if (sender.selected_content.all) {
                                multi_form.append(`<input id='multiselect-content-query' type='hidden' name='content-query'>`)
                                $('#multiselect-content-query').val(JSON.stringify(search))
                            }
                            multi_form.submit()
                        } else if (sender.job_manager !== null) {
                            sender.job_manager.new_job(ct_name, sender.selected_content.ids[0], action)
                        }
                    }
                })

                // populate content specific tasks
                sender.corpora.get_tasks(ct.name, function (tasks_data) {
                    if (tasks_data.length > 0) {
                        let task_selection_html = '<optgroup label="Launch Job">'
                        tasks_data.map(task => {
                            if (role === 'Admin') {
                                task_selection_html += `<option value="${task.id}">${task.name}</option>`
                            }
                        })
                        task_selection_html += '</optgroup>'
                        $(`#ct-${ct.name}${sender.id_suffix}-selection-action-selector`).append(task_selection_html)
                    }
                })
            }

            // setup content type search fields
            let search_settings_menu = $(`#ct-${ct.name}${sender.id_suffix}-search-settings-menu`)
            for (let x = 0; x < ct.fields.length; x++) {
                if (ct.fields[x].in_lists) {
                    search_settings_menu.append(`
                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-setting"
                            id="ct-${ct.name}${sender.id_suffix}-search-setting-${x}"
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
                                    search_settings_menu.append(`
                                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-setting"
                                            data-field-type="${cx.fields[y].type}"
                                            id="ct-${ct.name}${sender.id_suffix}-search-setting-${x}.${y}"
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
            $(`.ct-${ct.name}${sender.id_suffix}-search-setting`).click(function (event) {
                event.preventDefault()
                let field = $(this)
                let field_name = field.data('field_name')
                let field_type = field.data('field_type')
                let label = field.text()
                let search_type_menu = $(`#ct-${ct.name}${sender.id_suffix}-search-type-menu`)

                search_type_menu.empty()

                if (field_name === 'default') {
                    search_type_menu.html(`
                        <span class="p-2">Select a specific field from the dropdown to the right in order to choose a different search type.</span>
                    `)
                } else {
                    search_type_menu.html(`
                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-default" href="#">Generic Search</a>
                        ${['text', 'large_text', 'keyword', 'html', 'number', 'decimal', 'boolean', 'date', 'timespan', 'file', 'link', 'iiif-image', 'geo_point', 'cross_reference'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-exact" href="#">Exact Search</a>` : ''}
                        ${['text', 'large_text', 'keyword', 'html', 'cross_reference'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-term" href="#">Term Search</a>` : ''}
                        ${['text', 'large_text', 'keyword', 'html', 'cross_reference'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-phrase" href="#">Phrase Search</a>` : ''}
                        ${['text', 'large_text', 'keyword', 'html', 'cross_reference'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-wildcard" href="#">Wildcard Search</a>` : ''}
                        ${['number', 'decimal', 'date', 'timespan', 'geo_point'].includes(field_type) ? `<a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-range" href="#">Range Search</a>` : ''}
                    `)
                }

                // event for selecting a search type
                $(`.ct-${ct.name}${sender.id_suffix}-search-type`).click(function (event) {
                    event.preventDefault()
                    let search_type = event.target.id.replace(`ct-${ct.name}${sender.id_suffix}-search-type-`, '')
                    let label = $(this).text()

                    $(`#ct-${ct.name}${sender.id_suffix}-search-type-selection`).text(label)
                    $(`#ct-${ct.name}${sender.id_suffix}-search-type-value`).val(search_type)
                })

                $(`#ct-${ct.name}${sender.id_suffix}-search-setting-selection`).text(label)
                $(`#ct-${ct.name}${sender.id_suffix}-search-setting-value`).val(field_name)
            })

            // setup page break observer for infinite scroll
            this.page_observer = new IntersectionObserver(entries => {
                entries.forEach((entry, index) => {
                    if (entry.isIntersecting) {
                        let page_breaker = $(entry.target)
                        let scroll_progress_bar = $(`#ct-${ct.name}${sender.id_suffix}-scroll-progress`)
                        let rec_num = page_breaker.data('record_num')
                        let scroll_progress = Math.round((rec_num / sender.meta.total) * 100)
                        let next_page = page_breaker.data('next_page')

                        scroll_progress_bar.css('width', `${scroll_progress}%`)
                        scroll_progress_bar.attr('aria-valuenow', scroll_progress)

                        if (next_page) {
                            next_page = parseInt(next_page)
                            let next_page_token = page_breaker.data('next_page_token')

                            if (!sender.pages_loaded.has(next_page) && next_page <= sender.total_pages) {
                                let already_loading = false
                                sender.pages_to_load.forEach(p => {
                                    if (p['page'] === next_page) already_loading = true
                                })
                                if (!already_loading) {
                                    let page_info = {'page': next_page}
                                    if (next_page_token) page_info['page-token'] = next_page_token
                                    sender.pages_to_load.push(page_info)
                                    if (!sender.currently_loading_pages) sender.load_pages(true)
                                }
                            }
                        }

                    }
                })
            })

            // setup search events
            $(`#ct-${ct.name}${sender.id_suffix}-search-box`).keypress(function (e) {
                clearTimeout(sender.search_timer)
                let key = e.which
                if (key === 13) {
                    sender.do_search()
                } else sender.search_timer = setTimeout(() => {sender.do_search()}, 500)
            })

            $(`#ct-${ct.name}${sender.id_suffix}-search-clear-button`).click(function (event) {
                $(`#ct-${ct.name}${sender.id_suffix}-search-box`).val('')
                for (let param in search) {
                    if (search.hasOwnProperty(param)) {
                        if (['q', 'page-token'].includes(param) || ['q_', 'f_', 't_', 'p_', 'w_', 'r_'].includes(param.slice(0, 2))) {
                            delete search[param]
                        }
                    }
                }
                $(`#ct-${ct.name}${sender.id_suffix}-search-setting-selection`).text("All Fields")
                $(`#ct-${ct.name}${sender.id_suffix}-search-setting-value`).val('default')

                search.pages_to_load = [{'page': 1}]
                sender.load_pages()
            })

            // perform initial query of content based on search settings
            sender.pages_to_load = [{'page': 1}]
            sender.load_pages()
            if (sender.give_search_focus) $(`#ct-${ct.name}${sender.id_suffix}-search-box`).focus()
        }
    }

    do_search() {
        let sender = this

        let ct = sender.corpus.content_types[sender.content_type]
        let query = $(`#ct-${ct.name}${sender.id_suffix}-search-box`).val()
        let field = $(`#ct-${ct.name}${sender.id_suffix}-search-setting-value`).val()
        let search_type = $(`#ct-${ct.name}${sender.id_suffix}-search-type-value`).val()
        let search_type_map = {
            default: 'q',
            exact: 'f',
            term: 't',
            phrase: 'p',
            wildcard: 'w',
            range: 'r',
        }

        if (field === 'default') {
            sender.search.q = query
        } else {
            let param_prefix = search_type_map[search_type]
            sender.search[`${param_prefix}_${field}`] = query
        }

        $(`#ct-${ct.name}${sender.id_suffix}-search-clear-button`).removeClass('d-none')
        sender.pages_to_load = [{'page': 1}]
        sender.load_pages()
    }

    async load_pages(add_to_existing_rows=false) {
        let sender = this
        this.currently_loading_pages = true

        while (this.pages_to_load.length) {
            let page_info = this.pages_to_load[0]
            sender.pages_loaded.add(page_info['page'])
            this.search['page'] = page_info.page
            if ('page-token' in page_info) this.search['page-token'] = page_info['page-token']

            await this.corpora.list_content(corpus_id, this.content_type, this.search, function(content){
                sender.total_pages = content.meta.num_pages
                sender.load_content(content, add_to_existing_rows)
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
        let sender = this

        // instantiate some variables to keep track of elements
        let ct_table_body = $(`#ct-${ct.name}${sender.id_suffix}-table-body`); // <-- the table body for listing results
        let page_selector = $(`#ct-${ct.name}${sender.id_suffix}-page-selector`); // <-- the page select box
        let per_page_selector = $(`#ct-${ct.name}${sender.id_suffix}-per-page-selector`); // <-- the page size select box
        let current_search_div = $(`#ct-${ct.name}${sender.id_suffix}-current-search-div`); // <-- the search criteria div
        let total_indicator = $(`#ct-${ct.name}${sender.id_suffix}-total-badge`) // <-- the total indicator
        let has_filtering_criteria = false

        if (!add_to_existing_rows) {
            // clear the table body and search criteria div
            ct_table_body.html('')
            current_search_div.html('')
            sender.pages_loaded.clear()

            // add the total number of results to the search criteria div
            total_indicator.html(`Total: ${content.meta.total.toLocaleString('en-US')}`)
            total_indicator.data('total', content.meta.total)

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

                    current_search_div.append(`
                        <span class="badge badge-primary p-2 mr-2" style="font-size: 12px;">
                            ${setting_type} ${field_name} "${search_value}"
                            <a class="text-white ml-1 ${ct.name}${sender.id_suffix}-remove-search-param" data-search-param="${search_setting}"><i class="far fa-times-circle"></i></a>
                        </span>
                    `)
                    has_search_indicators = true
                }
            }

            // show or hide search indicator drawer appropriately
            if (has_search_indicators) {
                current_search_div.slideDown('slow', 'swing', function() {
                    current_search_div.addClass('d-flex')
                })
            } else {
                current_search_div.removeClass('d-flex')
                current_search_div.hide()
            }

            // remove search param event
            $(`.${ct.name}${sender.id_suffix}-remove-search-param`).click(function () {
                sender.remove_search_param($(this).data('search-param'))
            })
        }

        if (content.hasOwnProperty('meta')) sender.meta = content.meta

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
            ct_table_body.append(row_html)

            page_selector.addClass("d-none")
            per_page_selector.addClass("d-none")

        // records exist, so populate the content type table with a page of results
        } else {
            // iterate through the records, adding a row for each one
            content.records.forEach((item, item_index) => {
                let load_item = true
                let rec_num = (item_index + 1) + ((content.meta.page - 1) * content.meta.page_size)

                if (sender.overlapping_results)
                    if ($(`.${ct.name}${sender.id_suffix}-content-row[data-corpora_id="${item.id}"]`).length)
                        load_item = false

                if (load_item) {
                    let selected = ''
                    if (sender.selected_content.all) {
                        selected = "checked disabled"
                    } else if (sender.selected_content.ids.includes(item.id)) {
                        selected = "checked"
                    }

                    let action_controls = `
                        <input id="ct_${ct.name}${sender.id_suffix}_${item.id}_selection-box"
                            type="checkbox"
                            class="ct-${ct.name}${sender.id_suffix}-selection-box mr-2"
                            data-ct="${ct.name}"
                            data-id="${item.id}"
                            ${selected}>
                        <a href="${item.uri}" target="_blank">
                            <span class="badge badge-warning">Open</span>
                        </a>
                    `
                    if (sender.mode === 'select') {
                        action_controls = `
                            <a href="#"
                                class="${ct.name}${sender.id_suffix}-content-selection-link badge badge-warning"
                                data-id="${item.id}"
                                data-uri="${item.uri}"
                                data-label="${sender.corpora.strip_html(item.label)}">
                                Select
                            </a>
                        `
                    }

                    // infinite scroll page break indicators
                    let page_break_indicators = ''
                    if (content.meta.has_next_page) {
                        page_break_indicators = `data-next_page="${content.meta.page + 1}"`
                        if (content.meta.next_page_token) page_break_indicators += ` data-next_page_token="${content.meta.next_page_token}"`
                    }

                    let row_html = `
                        <tr class="${ct.name}${sender.id_suffix}-content-row" data-corpora_id="${item.id}"
                            data-record_num="${rec_num}" ${page_break_indicators}>
                            <td class="ct-selection-cell">
                                ${action_controls}
                            </td>
                    `

                    ct.fields.map(field => {
                        if (field.in_lists) {
                            let value = ''
                            if (item.hasOwnProperty(field.name) && item[field.name] != null) {
                                value = sender.format_column_value(item[field.name], field.type, field.multiple)
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
                    ct_table_body.append(row_html)
                }
            })

            // remove any page breaker attributes for currently loaded page
            $(`.${ct.name}${sender.id_suffix}-content-row[data-next_page="${content.meta.page}"]`).each(function() {
                $(this).removeAttr('data-next_page')
            })

            // make sure unobserved page breaker rows get observed
            $(`.${ct.name}${sender.id_suffix}-content-row:not([data-observed])`).each(function() {
                this.setAttribute('data-observed', 'true')
                sender.page_observer.observe(this)
            })

            // accelerate loading of subsequent pages once first two are loaded
            if (!sender.loading_accelerated && content.meta.page === 3) {
                sender.search['page-size'] *= 10
                sender.overlapping_results = true
                $(`.${ct.name}${sender.id_suffix}-content-row`).each(function() {
                    $(this).removeAttr('data-next_page')
                })
                sender.pages_loaded.clear()
                sender.loading_accelerated = true
                sender.pages_to_load = [{'page': 1}]
                sender.load_pages(true)
            } else sender.overlapping_results = false

            // conditionally scroll to top and set table height and make it resizable
            let table_container = $(`#ct-${ct.name}${sender.id_suffix}-table-container`)
            if (!add_to_existing_rows) table_container.scrollTop(0)

            if (!sender.content_populated) {
                sender.content_populated = true

                let height = table_container.height()
                let half_window_height = Math.round($(window).height() / 2)

                if (height > half_window_height) height = half_window_height
                if (height < sender.min_height) height = sender.min_height

                if (table_container.parent().height() < 0) table_container.css('height', '50vh')
                else if (content.meta.total >= 5) table_container.css('height', `${height}px`)
                interact(table_container[0])
                    .resizable({
                        // resize from bottom only
                        edges: { bottom: true },

                        listeners: {
                            move (event) {
                                var target = event.target
                                $(target).css('height', `${event.rect.height}px`)
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
                    .on('resizestart', function() {
                        table_container.css('overflow-y', 'hidden')
                        table_container.css('user-select', 'none')
                    })
                    .on('resizeend', function() {
                        table_container.css('overflow-y', 'scroll')
                        table_container.css('user-select', 'unset')
                    })
            }
        }

        // handle checking/unchecking content selection boxes
        $(`.ct-${ct.name}${sender.id_suffix}-selection-box`).change(function() {
            let ct_name = $(this).data('ct')
            let content_id = $(this).data('id')
            let selection_action_div = $(`#ct-${ct.name}${sender.id_suffix}-selection-action-div`)

            if($(this).is(':checked')) {
                sender.selected_content.ids.push(content_id)
            } else {
                sender.selected_content.ids = sender.selected_content.ids.filter(id => id !== content_id)
            }

            if (sender.selected_content.ids.length > 0) {
                selection_action_div.slideDown('slow', 'swing', function () {
                    selection_action_div.addClass('d-flex')
                })
            } else {
                selection_action_div.removeClass('d-flex')
                selection_action_div.hide()
            }
        })

        // handle content selection in select mode
        if (sender.mode === 'select') {
            $(`.${ct.name}${sender.id_suffix}-content-selection-link`).click(function(e) {
                e.preventDefault()
                let link = $(this)
                if (sender.selection_callback != null) {
                    sender.selection_callback({
                        id: link.data('id'),
                        uri: link.data('uri'),
                        label: link.data('label')
                    })
                }
            })
        }

        // callback if set by config
        if (typeof sender.on_load === 'function') sender.on_load(content.meta)
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
        let sender = this
        this.pages_to_load = [{'page': 1}]
        sender.load_pages()
    }

    remove_search_param(param) {
        if (this.search.hasOwnProperty(param)) {
            delete this.search[param]
            let sender = this

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
            } else if (field_type === 'iiif-image') {
                value = `<img loading="lazy" src='${value}/full/,100/0/default.png' />`
                delimiter = '<br />'
            } else if (field_type === 'file' && ['.png', '.jpg', '.gif', 'jpeg'].includes(value.toLowerCase().substring(value.length - 4))) {
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
}

