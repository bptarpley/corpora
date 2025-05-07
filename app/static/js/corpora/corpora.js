class Corpora {
    constructor(config={}) {
        this.host = 'host' in config ? config.host : ""
        this.auth_token = 'auth_token' in config ? config.auth_token : ""
        this.csrf_token = 'csrf_token' in config ? config.csrf_token : ""
    }

    make_request(path, type, params={}, callback, spool=false, spool_records = []) {
        let url = `${this.host}${path}`
        let req_options = {}
        let sender = this

        if (path.startsWith('http')) url = path
        if (this.auth_token) {
            req_options = {headers: {Authorization: `Token ${sender.auth_token}`}}
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

                        corpora_instance.make_request(
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
            function(corpus) {
                corpus.events = new SharedWorker(`/corpus/${id}/event-dispatcher/`)
                corpus.event_callbacks = {
                    alert: function (alert) {
                        let alert_div = $(`
                            <div class="alert alert-${alert.type === "success" ? 'success' : 'danger'}"
                                style="width: 95%; float: left; margin: 0px;">
                              ${alert.message}
                            </div>
                        `)
                        Toastify({
                            node: alert_div[0],
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
        let cv_modal = $('#cv-creation-modal')
        let ct_keys = Object.keys(corpus.content_types)
        let sender = this

        if (!cv_modal.length) {
            $('body').append(`
                <div class="modal fade" id="cv-creation-modal" tabindex="-1" role="dialog" aria-labelledby="cv-creation-modal-label" aria-hidden="true">
                    <div class="modal-dialog modal-lg" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 id="cv-creation-modal-label" class="modal-title">Content View</h5>
                                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                <span aria-hidden="true">&times;</span>
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
                                    <label for="cv-name-box">Name</label>
                                    <input id="cv-name-box" type="text" class="form-control">
                                </div>
                                
                                <div class="form-group">
                                    <label for="cv-target-ct">Content Type</label>
                                    <select id="cv-target-ct" class="form-control btn-primary"><option value="None">--select--</option></select>
                                </div>
                                
                                <div id="cv-target-table-div"></div>
                                
                                <div id="cv-pattern-div" class="d-none mt-3">
                                    
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                                <button type="button" class="btn btn-primary" id="cv-create-button">Create</button>
                            </div>
                        </div>
                    </div>
                </div>
            `)

            cv_modal = $('#cv-creation-modal')
            let target_ct_selector = $('#cv-target-ct')
            let target_table_div = $('#cv-target-table-div')

            target_ct_selector.val('None')
            target_table_div.html('')

            ct_keys.map(ct_key => {
                let ct = corpus.content_types[ct_key]
                target_ct_selector.append(`<option value="${ct.name}">${ct.name}</option>`)
            })

            target_ct_selector.change(function() {
                let target_ct = $(this).val()
                let patass_div = $('#cv-pattern-div')

                target_table_div.html('')
                patass_div.removeClass('d-none')
                patass_div.html('')
                patass_div.append('<button type="button" class="btn btn-primary" id="cv-create-pattern-button">Create a Pattern of Association</button>')

                let target_table = new ContentTable({
                    container_id: 'cv-target-table-div',
                    corpora: sender,
                    corpus: corpus,
                    content_type: target_ct,
                    mode: 'view'
                })

                $('#cv-create-pattern-button').click(function() {
                    let pattern_div = $('#cv-pattern-div')
                    let target_ct = corpus.content_types[target_ct_selector.val()]
                    pattern_div.append(`<div id="patass-canvas" class="d-flex flex-column"></div>`)
                    let canvas = $('#patass-canvas')

                    let patass_step = (step, direction, ct) => {
                        let next_ct_options = []
                        ct.fields.map(field => {
                            if (field.type === 'cross_reference') {
                                let next_ct = field.cross_reference_type
                                next_ct_options.push(`<option value="--> ${next_ct}">--> ${next_ct}</option>`)
                            }
                        })
                        for (let ct_name in corpus.content_types) {
                            if (ct_name !== ct.name) {
                                corpus.content_types[ct_name].fields.map(field => {
                                    if (field.type === 'cross_reference' && field.cross_reference_type === ct.name) {
                                        next_ct_options.push(`<option value="<-- ${ct_name}"><-- ${ct_name}</option>`)
                                    }
                                })
                            }
                        }

                        let next_selector = `<select class="patass-next-selector form-control-sm btn-secondary d-flex align-self-center" data-step="${step}"><option value="--">Select...</option>${next_ct_options}</select>`

                        canvas.append(`
                            ${ step > 0 ? ` <div class="patass-pipe patass-step-${step} d-flex align-self-center">&nbsp;</div>` : '' }
                            <div id="patass-step-${step}-circle" class="patass-ct-circle patass-step-${step} d-flex justify-content-center align-self-center" data-step="${step}" data-direction="${direction ? direction : ''}" data-ct="${ct.name}" data-ids=""><span class="mx-auto my-auto">${ct.plural_name}</span></div>
                            ${ step > 0 ? `<div class="patass-ct-controls d-flex justify-content-center align-self-center"><button role="button" class="btn btn-sm btn-secondary patass-specific-ids-button" data-step="${step}">Specify</button></div>` : '' }
                            <div class="patass-pipe patass-from-ct-to-add patass-step-${step} d-flex align-self-center">&nbsp;</div>
                            <div class="patass-add-circle patass-step-${step} d-flex justify-content-center align-self-center" data-step="${step}" data-origin-ct="${ct.name}">${next_selector}</div>
                        `)

                        $('.patass-next-selector').off('change').on('change', function() {
                            if ($(this).val() !== '--') {
                                let step = parseInt($(this).data('step'))
                                let [next_direction, next_ct_name] = $(this).val().split(' ')
                                let next_ct = corpus.content_types[next_ct_name]
                                $('.patass-add-circle').remove()
                                $('.patass-from-ct-to-add').remove()
                                patass_step(step + 1, next_direction, next_ct)
                            }
                        })

                        $('.patass-specific-ids-button').off('click').on('click', function() {
                            let step = $(this).data('step')
                            let ct_circle = $(`#patass-step-${step}-circle`)
                            let ids = ct_circle.data('ids').split(',')
                            if (ids[0] === '') ids = []
                            let ct_circle_span = $(`#patass-step-${step}-circle > span`)

                            sender.select_content(corpus_id, ct.name, function(new_id, new_label) {
                                ids.push(new_id)
                                ct_circle.data('ids', ids.join(','))
                                let label = ct_circle_span.html()
                                if (!label.includes(' (')) label += ' ('
                                else label = label.slice(0, -1) + ', '
                                label += `<a href="/corpus/${corpus_id}/${ct.name}/${new_id}/" target="_blank">${new_label}</a>)`
                                ct_circle_span.html(label)
                            })
                        })
                    }

                    patass_step(0, null, target_ct, [])


                    $(this).remove()
                })

                $('#cv-create-button').click(function() {
                    let patass = ''
                    $('.patass-ct-circle').each(function() {
                        let step = parseInt($(this).data('step'))
                        if (step > 0) {
                            let ct = $(this).data('ct')
                            let direction = $(this).data('direction')
                            let ids = $(this).data('ids')
                            if (ids) ids = ids.split(',')
                            else ids = []

                            patass += `${direction}(${ct}${ ids.length ? `[${ids.join(',')}]` : '' }) `
                        }
                    })

                    if (patass.length) {
                        patass = patass.slice(0, -1)
                    }

                    let submission = {
                        'cv-name': $('#cv-name-box').val(),
                        'cv-target-ct': target_ct_selector.val(),
                        'cv-search-json': JSON.stringify(target_table.search),
                        'cv-patass': patass
                    }

                    sender.make_request(
                        `/api/corpus/${corpus.id}/content-view/`,
                        'POST',
                        submission,
                        function (data) {
                            if (data.status === 'populating') {
                                let create_button = $('#cv-create-button')
                                create_button.html('Populating...')
                                create_button.attr('disabled', true)
                                sender.await_content_view_population(corpus.id, data.id, function(data) {
                                    cv_modal.modal('hide')
                                    callback(data)
                                })
                            } else {
                                cv_modal.modal('hide')
                                callback(data)
                            }
                        }
                    )
                })
            })
        }

        cv_modal.modal()
        cv_modal.on('hidden.bs.modal', function() { cv_modal.remove(); })
    }

    await_content_view_population(corpus_id, content_view_id, callback) {
        let sender = this
        sender.make_request(
            `/api/corpus/${corpus.id}/content-view/${content_view_id}/`,
            'GET',
            {},
            function (data) {
                if (data.status === 'populating') {
                    setTimeout(function() {
                        sender.await_content_view_population(corpus_id, content_view_id, callback)
                    }, 5000)
                } else {
                    callback(data)
                }
            }
        )
    }

    select_content(corpus_id, content_type, callback, new_selection=true) {
        let sender = this
        let modal = $('#content-selection-modal')

        if (new_selection) {
            modal.remove()
            modal = $('#content-selection-modal')
        }

        if (!modal.length) {
            $('body').append(`
                <div class="modal fade" id="content-selection-modal" tabindex="-1" role="dialog" aria-labelledby="content-selection-modal-label" aria-hidden="true">
                    <div class="modal-dialog modal-lg" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="content-selection-modal-label">Select ContentType</h5>
                                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                <span aria-hidden="true">&times;</span>
                                </button>
                            </div>
                            <div class="modal-body">
                                <div class="alert alert-light">
                                    <div class="mb-2">
                                        <input type="text" class="form-control" id="content-selection-modal-filter-box" aria-placeholder="Search" placeholder="Search">
                                    </div>
                                    <table class="table table-striped">
                                        <thead class="thead-dark">
                                            <th scope="col" id="content-selection-modal-table-header">ContentType</th>
                                        </thead>
                                        <tbody id="content-selection-modal-table-body">
                                            <tr><td>Loading...</td></tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <input type="hidden" id="content-selection-search-params" data-page-size="10" data-page="1" data-q="*" />
                                <button type="button" id="content-selection-modal-prev-page-button" class="btn btn-secondary"><span class="fas fa-angle-left"></span></button>
                                <button type="button" id="content-selection-modal-next-page-button" class="btn btn-secondary"><span class="fas fa-angle-right"></span></button>
                                <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                            </div>
                        </div>
                    </div>
                </div>
            `)
            modal = $('#content-selection-modal')

            // HANDLE SEARCH BOX
            $('#content-selection-modal-filter-box').keypress(function (e) {
                let key = e.which
                if (key === 13) {
                    let search_param_input = $('#content-selection-search-params')
                    search_param_input.data('q', $('#content-selection-modal-filter-box').val())
                    sender.select_content(corpus_id, content_type, callback, false)
                }
            })

            // previous select content page click event
            $('#content-selection-modal-prev-page-button').click(function() {
                let search_param_input = $('#content-selection-search-params')
                search_param_input.data('page', parseInt(search_param_input.data('page')) - 1)
                sender.select_content(corpus_id, content_type, callback, false)
            })

            // next select content page click event
            $('#content-selection-modal-next-page-button').click(function() {
                let search_param_input = $('#content-selection-search-params')
                search_param_input.data('page', parseInt(search_param_input.data('page')) + 1)
                sender.select_content(corpus_id, content_type, callback, false)
            })
        }

        let search_param_input = $('#content-selection-search-params')

        let content_selection_params = {
            q: search_param_input.data('q'),
            only: 'label',
            s_label: 'asc',
            'page-size': search_param_input.data('page-size'),
            page: search_param_input.data('page')
        }

        sender.list_content(corpus_id, content_type, content_selection_params, function(data){
            $('#content-selection-modal-prev-page-button').prop('disabled', content_selection_params.page <= 1)
            $('#content-selection-modal-next-page-button').prop('disabled', !data.meta.has_next_page)

            $('#content-selection-modal-label').html(`Select ${content_type}`)
            $('#content-selection-modal-table-header').html(content_type)
            $('#content-selection-modal-table-body').empty()
            for (let x = 0; x < data.records.length; x++) {
                $('#content-selection-modal-table-body').append(`
                    <tr><td><a class="content-selection-item" data-id="${data.records[x].id}" data-label="${data.records[x].label}">${data.records[x].label}</a></td></tr>
                `)
            }

            // HANDLE ITEM CLICKING
            $('.content-selection-item').click(function() {
                modal.modal('hide')
                callback($(this).data('id'), $(this).data('label'))
            })

            $('#content-selection-modal').modal()
        })
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
        if (from_mongo) date = new Date(timestamp*1000)
        else date = new Date(timestamp)

        let representation = null
        if (adjust_for_timezone) representation = date.toLocaleString('en-US', { timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone })
        else representation = date.toLocaleString('en-US')

        if (just_time) representation = representation.split(', ')[1]
        return representation
    }

    date_string(timestamp, granularity='Day', adjust_for_timezone=true, from_mongo=false) {
        let date = null
        if (from_mongo) date = new Date(timestamp*1000)
        else date = new Date(timestamp)

        if (granularity === 'Day')
            return date.toISOString().split('T')[0]
        else if (granularity === 'Year')
            return date.toLocaleString('default', { year: 'numeric' })
        else if (granularity === 'Month')
            return date.toLocaleString('default', { month: 'long', year: 'numeric' })
        else if (granularity === 'Time')
            return this.time_string(timestamp, false, false, adjust_for_timezone)
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
    const p = new RegExp(a.split('').join('|'), 'g')

    return string.toString().toLowerCase()
        .replace(/\s+/g, '_') // Replace spaces with -
        .replace(p, c => b.charAt(a.indexOf(c))) // Replace special characters
        .replace(/&/g, '_and_') // Replace & with 'and'
        .replace(/[^\w\-]+/g, '') // Remove all non-word characters
        .replace(/\-\-+/g, '_') // Replace multiple - with single -
        .replace(/^-+/, '') // Trim - from start of text
        .replace(/-+$/, ''); // Trim - from end of text
}

    pep8_class_format(string) {
        // expects a pep8 variable formatted string
        return string.toLowerCase().split('_').map(function(word) {
            return word.replace(word[0], word[0].toUpperCase())
        }).join('')
    }

    unescape(string) {
      return new DOMParser().parseFromString(string,'text/html').querySelector('html').textContent
    }
}
