class Corpora {
    constructor(config={}) {
        this.host = 'host' in config ? config.host : ""
        this.auth_token = 'auth_token' in config ? config.auth_token : ""
        this.csrf_token = 'csrf_token' in config ? config.csrf_token : ""
    }

    make_request(path, type, params={}, callback, spool=false, spool_records = []) {
        let url = `${this.host}${path}`
        let req_options = {}

        if (path.startsWith('http')) url = path
        if (this.auth_token) {
            req_options = {headers: {Authorization: `Token ${this.auth_token}`}}
        }

        if (type === 'GET') url += `?${new URLSearchParams(params).toString()}`
        else if (type === 'POST') {
            req_options['method'] = 'POST'
            if (!req_options.headers) req_options.headers = {}
            if (this.csrf_token) req_options.headers['X-CSRFToken'] = this.csrf_token

            if (params) {
                let post_params = new FormData()
                for (let p in params) {
                    post_params.append(p, params[p])
                }
                req_options['body'] = post_params
            }
        }

        return fetch(url, req_options)
            .then(res => {
                if (type === 'POST' && res.ok) {
                    if (res.status === 204 || res.headers.get('Content-Length') === '0') {
                        return {}
                    } else return res.json()
                }
                else if (type === 'GET') return res.json()
            })
            .then(data => {
                if (spool) {
                    if (
                        data.hasOwnProperty('records') &&
                        data.hasOwnProperty('meta') &&
                        data.meta.hasOwnProperty('has_next_page') &&
                        data.meta.hasOwnProperty('page') &&
                        data.meta.hasOwnProperty('page_size') &&
                        data.meta.has_next_page
                    ) {
                        let next_params = Object.assign({}, params)
                        next_params.page = data.meta.page + 1
                        next_params['page-size'] = data.meta.page_size

                        this.make_request(
                            path,
                            type,
                            next_params,
                            callback,
                            spool,
                            spool_records.concat(data.records)
                        )
                    } else {
                        data.records = spool_records.concat(data.records)
                        callback(data)
                    }
                }
                else callback(data)
            })
    }

    get_scholars(search={}, callback) {
        this.make_request(
            "/api/scholar/",
            "GET",
            search,
            callback
        )
    }

    get_scholar(scholar_id, callback) {
        this.make_request(
            `/api/scholar/${scholar_id}/`,
            "GET",
            {},
            callback
        )
    }

    scholar_has_privilege(privilege, role) {
        return role === privilege ||
            role === 'Admin' ||
            (role === 'Editor' && ['Editor', 'Contributor', 'Viewer'].includes(privilege)) ||
            (role === 'Contributor' && ['Contributor', 'Viewer'].includes(privilege))
    }

    get_corpora(search={}, callback) {
        this.make_request(
            "/api/corpus/",
            "GET",
            search,
            callback
        )
    }

    get_corpus(id, callback, include_views=false) {
        let params = {}
        if (include_views) {
            params['include-views'] = true
        }

        this.make_request(
            `/api/corpus/${id}/`,
            "GET",
            params,
            corpus => {
                corpus.events = new SharedWorker(`/corpus/${id}/event-dispatcher/`)
                corpus.event_ids = new Set()
                corpus.event_callbacks = {
                    alert: function (alert) {
                        if (!corpus.event_ids.has(alert.event_id)) {
                            // prevent duplicate alerts
                            corpus.event_ids.add(alert.event_id)

                            let alert_div = htmlToEl(`
                                <div class="alert alert-${alert.type === "success" ? 'success' : 'danger'}"
                                    style="width: 95%; float: left; margin: 0px;">
                                  ${alert.message}
                                </div>
                            `)
                            Toastify({
                                node: alert_div,
                                duration: 10000,
                                close: true,
                                gravity: 'bottom',
                                position: 'right',
                                style: {
                                    background: 'unset',
                                    padding: '8px'
                                }
                            }).showToast()
                        }
                    }
                }

                corpus.events.port.start()
                corpus.events.port.onmessage = (event) => {
                    let payload = JSON.parse(event.data)
                    if (payload.event_type && Object.keys(corpus.event_callbacks).includes(payload.event_type)) {
                        corpus.event_callbacks[payload.event_type](payload)
                    }
                }

                callback(corpus)
            }
        )
    }

    get_job(corpus_id, job_id, callback) {
        this.make_request(
            `/api/jobs/corpus/${corpus_id}/job/${job_id}/`,
            "GET",
            {},
            callback
        )
    }

    get_jobs(corpus_id=null, content_type=null, content_id=null, params={}, callback) {
        let url = '/api/jobs/'
        if (corpus_id) { url += `corpus/${corpus_id}/`; }
        if (corpus_id && content_type && content_type !== 'Corpus') { url += `${content_type}/`; }
        if (corpus_id && content_type && content_id) { url += `${content_id}/`; }
        this.make_request(
            url,
            "GET",
            params,
            callback
        )
    }

    submit_jobs(corpus_id, jobs, callback) {
        this.make_request(
            `/api/jobs/corpus/${corpus_id}/submit/`,
            "POST",
            {
                'job-submissions': JSON.stringify(jobs)
            },
            callback
        )
    }

    retry_job(corpus_id, content_type, content_id, job_id, callback) {
        this.make_request(
            `/api/jobs/corpus/${corpus_id}/submit/`,
            "POST",
            {
                'retry-job-id': job_id,
                'retry-content-type': content_type,
                'retry-content-id': content_id
            },
            callback
        )
    }

    get_jobsites(callback) {
        this.make_request(
            `/api/jobsites/`,
            "GET",
            {},
            callback
        )
    }

    get_tasks(content_type=null, callback) {
        let url = '/api/tasks/'
        if (content_type) {
            url += `${content_type}/`
        }

        this.make_request(
            url,
            "GET",
            {},
            callback
        )
    }

    get_plugin_schema(callback) {
        this.make_request(
            `/api/plugin-schema/`,
            "GET",
            {},
            callback
        )
    }

    edit_content_types(corpus_id, schema, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/type/`,
            "POST",
            {
                schema: schema
            },
            callback
        )
    }

    get_content(corpus_id, content_type, content_id, callback) {
        return this.make_request(
            `/api/corpus/${corpus_id}/${content_type}/${content_id}/`,
            "GET",
            {},
            callback
        )
    }

    list_content(corpus_id, content_type, search={}, callback, spool=false) {
        return this.make_request(
            `/api/corpus/${corpus_id}/${content_type}/`,
            "GET",
            search,
            callback,
            spool
        )
    }

    edit_content(corpus_id, content_type, fields={}) {
        this.make_request(
            `/api/corpus/${corpus_id}/${content_type}/`,
            "POST",
            fields,
            callback
        )
    }

    get_network_json(corpus_id, content_type, content_id, options={}, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/${content_type}/${content_id}/network-json/`,
            "GET",
            options,
            callback
        )
    }

    get_corpus_files(corpus_id, path, filter, callback) {
        let endpoint = `/api/corpus/${corpus_id}/files/`

        this.make_request(
            endpoint,
            "GET",
            {
                path: path,
                filter: filter
            },
            callback
        )
    }

    make_corpus_file_dir(corpus_id, path, new_dir, callback) {
        let endpoint = `/api/corpus/${corpus_id}/files/`

        this.make_request(
            endpoint,
            "POST",
            {
                path: path,
                newdir: new_dir
            },
            callback
        )
    }

    get_content_files(corpus_id, content_type, content_id, path, filter, callback) {
        let endpoint = `/api/corpus/${corpus_id}/${content_type}/files/`
        if (content_id) {
            endpoint = endpoint.replace('/files/', `/${content_id}/files/`)
        }

        this.make_request(
            endpoint,
            "GET",
            {
                path: path,
                filter: filter
            },
            callback
        )
    }

    make_content_file_dir(corpus_id, content_type, content_id, path, new_dir, callback) {
        let endpoint = `/api/corpus/${corpus_id}/${content_type}/files/`
        if (content_id) {
            endpoint = endpoint.replace('/files/', `/${content_id}/files/`)
        }

        this.make_request(
            endpoint,
            "POST",
            {
                path: path,
                newdir: new_dir
            },
            callback
        )
    }

    get_preference(content_type, content_uri, preference, callback) {
        this.make_request(
            `/api/scholar/preference/${content_type}/${preference}/`,
            "GET",
            {
                content_uri: content_uri
            },
            callback
        )
    }

    set_preference(content_type, content_uri, preference, value, callback) {
        this.make_request(
            `/api/scholar/preference/${content_type}/${preference}/`,
            "POST",
            {
                content_uri: content_uri,
                value: value
            },
            callback
        )
    }

    create_content_view(corpus, callback=null) {
        removeEl(getEl('cv-creation-modal'))

        appendToEl(document.body, `
            <div class="modal fade" id="cv-creation-modal" tabindex="-1" role="dialog" aria-labelledby="cv-creation-modal-label" aria-hidden="true">
                <div class="modal-dialog modal-lg" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 id="cv-creation-modal-label" class="modal-title">Content View</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close">
                            </button>
                        </div>
                        <div class="modal-body" style="max-height: 70vh; overflow-y: scroll;">
                            <div class="alert alert-info">
                                A "Content View" is a defined subset of content for a particular content type. To define one,
                                start by giving it a name and choosing the content type. You may then start filtering content
                                by performing a search and/or creating a pattern of association. Once a Content View is created,
                                it will appear on the Corpus page, and may also be selected as a filtering criteria in any Explore
                                pane.
                            </div>

                            <div class="form-group">
                                <label for="cv-name-box" class="form-label">Name</label>
                                <input id="cv-name-box" type="text" class="form-control">
                            </div>

                            <div class="form-group">
                                <label for="cv-target-ct" class="form-label">Content Type</label>
                                <select id="cv-target-ct" class="form-select bg-primary"><option value="None">--select--</option></select>
                            </div>

                            <div id="cv-target-table-div"></div>

                            <div id="cv-pattern-div" class="d-none mt-3">

                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="cv-create-button">Create</button>
                        </div>
                    </div>
                </div>
            </div>
        `)

        let cv_modal = getEl('cv-creation-modal')
        let target_ct_selector = getEl('cv-target-ct')
        let target_table_div = getEl('cv-target-table-div')
        let target_table = null

        setVal(target_ct_selector, 'None')
        target_table_div.innerHTML = ''

        Object.keys(corpus.content_types).forEach(ct_key => {
            let ct = corpus.content_types[ct_key]
            appendToEl(target_ct_selector, `<option value="${ct.name}">${ct.name}</option>`)
        })

        onEl(target_ct_selector, 'change', () => {
            let target_ct = getVal(target_ct_selector)
            let patass_div = getEl('cv-pattern-div')

            target_table_div.innerHTML = ''
            patass_div.classList.remove('d-none')
            patass_div.innerHTML = ''
            appendToEl(patass_div, '<button type="button" class="btn btn-primary" id="cv-create-pattern-button">Create a Pattern of Association</button>')

            target_table = new ContentTable({
                container_id: 'cv-target-table-div',
                corpora: this,
                corpus: corpus,
                content_type: target_ct,
                mode: 'read-only'
            })

            onlyOnEl(getEl('cv-create-pattern-button'), 'click', event => {
                let pattern_div = getEl('cv-pattern-div')
                let root_ct = corpus.content_types[getVal(target_ct_selector)]
                appendToEl(pattern_div, `<div id="patass-canvas" class="d-flex flex-column"></div>`)
                let canvas = getEl('patass-canvas')

                let patass_step = (step, direction, ct) => {
                    let next_ct_options = new Set()
                    ct.fields.forEach(field => {
                        if (field.type === 'cross_reference') {
                            let next_ct = field.cross_reference_type
                            next_ct_options.add(`<option value="--> ${next_ct}">--> ${next_ct}</option>`)
                        }
                    })
                    for (let ct_name in corpus.content_types) {
                        if (ct_name !== ct.name) {
                            corpus.content_types[ct_name].fields.forEach(field => {
                                if (field.type === 'cross_reference' && field.cross_reference_type === ct.name) {
                                    next_ct_options.add(`<option value="<-- ${ct_name}"><-- ${ct_name}</option>`)
                                }
                            })
                        }
                    }

                    let next_selector = `
                        <select class="patass-next-selector form-select-sm bg-secondary d-flex align-self-center" data-step="${step}">
                            <option value="--">Select...</option>
                            ${Array.from(next_ct_options).join('\n')}
                        </select>
                    `

                    appendToEl(canvas, `
                        ${ step > 0 ? ` <div class="patass-pipe patass-step-${step} d-flex align-self-center">&nbsp;</div>` : '' }
                        <div id="patass-step-${step}-circle" class="patass-ct-circle patass-step-${step} d-flex justify-content-center align-self-center" data-step="${step}" data-direction="${direction ? direction : ''}" data-ct="${ct.name}" data-ids=""><span class="mx-auto my-auto">${ct.plural_name}</span></div>
                        ${ step > 0 ? `<div class="patass-ct-controls d-flex justify-content-center align-self-center"><button role="button" class="btn btn-sm btn-secondary patass-specific-ids-button" data-step="${step}">Specify</button></div>` : '' }
                        <div class="patass-pipe patass-from-ct-to-add patass-step-${step} d-flex align-self-center">&nbsp;</div>
                        <div class="patass-add-circle patass-step-${step} d-flex justify-content-center align-self-center" data-step="${step}" data-origin-ct="${ct.name}">${next_selector}</div>
                    `)

                    forElsMatching('.patass-next-selector', selector_el => {
                        onlyOnEl(selector_el, 'change', () => {
                            if (getVal(selector_el) !== '--') {
                                let selected_step = parseInt(selector_el.dataset.step)
                                let [next_direction, next_ct_name] = getVal(selector_el).split(' ')
                                let next_ct = corpus.content_types[next_ct_name]
                                removeElsMatching('.patass-add-circle')
                                removeElsMatching('.patass-from-ct-to-add')
                                patass_step(selected_step + 1, next_direction, next_ct)
                            }
                        })
                    })

                    forElsMatching('.patass-specific-ids-button', button => {
                        onlyOnEl(button, 'click', () => {
                            let button_step = button.dataset.step
                            let ct_circle = getEl(`patass-step-${button_step}-circle`)
                            let ids = ct_circle.dataset.ids.split(',')
                            if (ids[0] === '') ids = []
                            let ct_circle_span = ct_circle.querySelector('span')

                            this.select_content(corpus, ct.name, (new_id, new_label) => {
                                ids.push(new_id)
                                ct_circle.dataset.ids = ids.join(',')
                                let label = ct_circle_span.innerHTML
                                if (!label.includes(' (')) label += ' ('
                                else label = label.slice(0, -1) + ', '
                                // was the template-global `corpus_id`, which only
                                // happened to exist on the corpus page.
                                label += `<a href="/corpus/${corpus.id}/${ct.name}/${new_id}/" target="_blank">${new_label}</a>)`
                                ct_circle_span.innerHTML = label
                            })
                        })
                    })
                }

                patass_step(0, null, root_ct)
                removeEl(event.currentTarget)
            })
        })

        onEl(getEl('cv-create-button'), 'click', () => {
            let patass = ''
            forElsMatching('.patass-ct-circle', circle => {
                let step = parseInt(circle.dataset.step)
                if (step > 0) {
                    let ct = circle.dataset.ct
                    let direction = circle.dataset.direction
                    let ids = circle.dataset.ids ? circle.dataset.ids.split(',') : []

                    patass += `${direction}(${ct}${ ids.length ? `[${ids.join(',')}]` : '' }) `
                }
            })

            if (patass.length) {
                patass = patass.slice(0, -1)
            }

            let submission = {
                'cv-name': getVal(getEl('cv-name-box')),
                'cv-target-ct': getVal(target_ct_selector),
                'cv-search-json': JSON.stringify(target_table ? target_table.search : {}),
                'cv-patass': patass
            }

            this.make_request(
                `/api/corpus/${corpus.id}/content-view/`,
                'POST',
                submission,
                data => {
                    let finish = view => {
                        hideModal(cv_modal)
                        if (callback) callback(view)
                    }

                    if (data.status === 'populating') {
                        let create_button = getEl('cv-create-button')
                        create_button.innerHTML = 'Populating...'
                        setDisabled(create_button)
                        this.await_content_view_population(corpus.id, data.id, finish)
                    } else finish(data)
                }
            )
        })

        onEl(cv_modal, 'hidden.bs.modal', () => removeEl(cv_modal))
        showModal(cv_modal)
    }

    await_content_view_population(corpus_id, content_view_id, callback) {
        this.make_request(
            // was `corpus.id` (a template global), ignoring the corpus_id argument.
            `/api/corpus/${corpus_id}/content-view/${content_view_id}/`,
            'GET',
            {},
            data => {
                if (data.status === 'populating') {
                    setTimeout(() => {
                        this.await_content_view_population(corpus_id, content_view_id, callback)
                    }, 5000)
                } else {
                    callback(data)
                }
            }
        )
    }

    select_content(corpus, content_type, callback) {
        // NOTE: this modal is deliberately id'd differently from the one ContentSelector
        // builds. Both used to be called `content-selection-modal` despite having
        // different internals, so whichever rendered first silently won.
        let modal = getEl('corpora-content-selection-modal')

        if (!modal) {
            appendToEl(document.body, `
                <div class="modal fade" id="corpora-content-selection-modal" tabindex="-1" role="dialog" aria-labelledby="corpora-content-selection-modal-label" aria-hidden="true">
                    <div class="modal-dialog modal-lg" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="corpora-content-selection-modal-label">Select ContentType</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close">
                                </button>
                            </div>
                            <div id="corpora-content-selection-modal-body" class="modal-body">

                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            </div>
                        </div>
                    </div>
                </div>
            `)
            modal = getEl('corpora-content-selection-modal')
        }

        getEl('corpora-content-selection-modal-label').innerHTML = `Select ${content_type}`
        clearEl(getEl('corpora-content-selection-modal-body'))

        new ContentTable({
            label: ``,
            container_id: 'corpora-content-selection-modal-body',
            corpora: this,
            corpus: corpus,
            mode: 'select',
            min_height: 300,
            content_type: content_type,
            selection_callback: content => {
                callback(content.id, content.label)
                hideModal(modal)
            }
        })

        showModal(modal)
    }

    build_associated_content_tables(corpus, content_type, content_id, container_id, job_manager=null) {
        let associated_cts = {}
        for (let ct_name in corpus.content_types) {
            let ct = corpus.content_types[ct_name]
            ct.fields.forEach(field => {
                if (field.type === 'cross_reference' && field.cross_reference_type === content_type && field.in_lists) {
                    if (!(ct_name in associated_cts)) {
                        associated_cts[ct_name] = []
                    }
                    associated_cts[ct_name].push({
                        name: field.name,
                        label: field.label
                    })
                }
            })
        }

        let container = getEl(container_id)

        // nothing cross-references this content type, so say so rather than leaving
        // the container empty and looking broken
        if (!Object.keys(associated_cts).length) {
            let plural_name = corpus.content_types[content_type]?.plural_name ?? content_type
            container.innerHTML = `
                <div class="alert alert-info m-0">
                    No content types in this corpus reference ${plural_name} in their schema.
                </div>
            `
            return
        }

        container.innerHTML = ''

        for (let ct_name in associated_cts) {
            associated_cts[ct_name].forEach(xref_field => {
                let associated_search = {
                    page: 1,
                    'page-size': 5,
                }
                associated_search[`f_${xref_field.name}.id`] = content_id
                new ContentTable({
                    label: `${corpus.content_types[ct_name].plural_name} (${xref_field.label})`,
                    container_id: container_id,
                    corpora: this,
                    corpus: corpus,
                    content_type: ct_name,
                    search: associated_search,
                    // passed through so these tables can still launch jobs against a
                    // selection; without it no "Launch Job" options are offered
                    job_manager: job_manager
                })
            })
        }
    }

    confirm_action(callback, title='Confirm', message='Are you Sure?', actionButton='Confirm', dangerous=false) {
        let confirm_modal = getEl('corpora-confirm-modal')

        if (!confirm_modal) {
            prependToEl(document.body, `
                <div class="modal fade" id="corpora-confirm-modal" tabindex="-1" role="dialog" aria-labelledby="corpora-confirm-modal-label" aria-hidden="true">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="corpora-confirm-modal-label">${title}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close">
                                </button>
                            </div>
                            <div class="modal-body">
                                <div id="corpora-confirm-modal-message" class="alert alert-${dangerous ? 'danger' : 'info'}">${message}</div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="button" class="btn btn-primary" id="corpora-confirm-modal-action-button">${actionButton}</button>
                            </div>
                        </div>
                    </div>
                </div>
            `)
            confirm_modal = getEl('corpora-confirm-modal')
        } else {
            let message_div = getEl('corpora-confirm-modal-message')
            message_div.innerHTML = message
            message_div.classList.toggle('alert-danger', dangerous)
            message_div.classList.toggle('alert-info', !dangerous)

            getEl('corpora-confirm-modal-label').innerHTML = title
        }

        let confirm_button = getEl('corpora-confirm-modal-action-button')
        confirm_button.innerHTML = actionButton
        // onlyOnEl rather than onEl: this runs on every confirm, and accumulated
        // handlers would fire every previous callback too.
        onlyOnEl(confirm_button, 'click', () => {
            callback()
            hideModal(confirm_modal)
        })
        showModal(confirm_modal)
    }

    cancel_action() {
        hideModal(getEl('corpora-confirm-modal'))
    }

    file_url(uri) {
        return `/file/uri/${uri.split('/').join('|')}/`
    }

    image_url(uri) {
        return `/image/uri/${uri.split('/').join('|')}/`
    }

    iiif_url(id, iiif_info={}, region='full', size='max', rotation=0, quality='default', format='png') {
        if (iiif_info.hasOwnProperty('fixed_region'))
            region = `${iiif_info.fixed_region.x},${iiif_info.fixed_region.y},${iiif_info.fixed_region.w},${iiif_info.fixed_region.h}`
        if (iiif_info.hasOwnProperty('fixed_rotation'))
            rotation = iiif_info.fixed_rotation

        return `${id}/${region}/${size}/${rotation}/${quality}.${format}`
    }

    time_string(timestamp, from_mongo=true, just_time=false, adjust_for_timezone=true) {
        let date = null
        if (from_mongo) date = new Date((timestamp * 1000) + (new Date().getTimezoneOffset() * 60 * 1000))
        else date = new Date(timestamp)

        let representation = null
        if (adjust_for_timezone) representation = date.toLocaleString('en-US', { timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone })
        else representation = date.toLocaleString('en-US')

        if (just_time) representation = representation.split(', ')[1]
        return representation
    }

    date_string(timestamp, granularity='Day', adjust_for_timezone=true, from_mongo=false) {
        let date = null
        if (from_mongo) date = new Date((timestamp * 1000) + (new Date().getTimezoneOffset() * 60 * 1000))
        else date = new Date(timestamp)

        if (granularity === 'Day')
            return date.toLocaleString('default', {month: 'numeric', day: 'numeric', year: 'numeric'})
        else if (granularity === 'Year')
            return date.toLocaleString('default', { year: 'numeric' })
        else if (granularity === 'Month')
            return date.toLocaleString('default', { month: 'long', year: 'numeric' })
        else if (granularity === 'Time')
            return this.time_string(timestamp, from_mongo, false, adjust_for_timezone)
    }

    timespan_string(timespan) {
        let uncertain_prefix = ''
        let granularity = timespan.granularity ?? 'Day'
        let start_string = ''
        let end_string = ''
        let range_combinator = ''

        if (timespan.start) {
            start_string = this.date_string(timespan.start, granularity)
            if (timespan.uncertain) uncertain_prefix = 'Around '

            if (timespan.end) {
                end_string = this.date_string(timespan.end, granularity)

                if (start_string !== end_string) {
                    range_combinator = ' - '
                    if (timespan.uncertain) {
                        uncertain_prefix = 'Between '
                        range_combinator = ' and '
                    }
                } else end_string = ''
            }
        }

        return `${uncertain_prefix}${start_string}${range_combinator}${end_string}`
    }

    generate_unique_id() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2)
    }

    strip_html(html) {
        let doc = new DOMParser().parseFromString(html, 'text/html');
        return doc.body.textContent || "";
    }

    pep8_variable_format(string) {
        const a = 'àáäâãåăæçèéëêǵḧìíïîḿńǹñòóöôœøṕŕßśșțùúüûǘẃẍÿź·/-,:;'
        const b = 'aaaaaaaaceeeeghiiiimnnnooooooprssstuuuuuwxyz______'
        const accented = new RegExp(a.split('').join('|'), 'g')

        return string.toString().toLowerCase()
            .replace(/\s+/g, '_')                            // spaces to underscores
            .replace(accented, c => b.charAt(a.indexOf(c)))  // strip accents
            .replace(/&/g, '_and_')
            .replace(/[^\w\-]+/g, '')                        // drop non-word characters
            .replace(/\-\-+/g, '_')                           // collapse repeated dashes
            .replace(/^-+/, '')
            .replace(/-+$/, '')
    }

    pep8_class_format(string) {
        // expects a pep8 variable formatted string. empty segments are skipped --
        // 'a__b' used to throw here, since ''[0] is undefined.
        return string.toLowerCase().split('_')
            .filter(word => word.length)
            .map(word => word[0].toUpperCase() + word.slice(1))
            .join('')
    }

    unescape(string) {
      return new DOMParser().parseFromString(string,'text/html').querySelector('html').textContent
    }
}
