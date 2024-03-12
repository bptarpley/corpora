function pep8_variable_format(string) {
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

function pep8_class_format(string) {
    // expects a pep8 variable formatted string
    return string.toLowerCase().split('_').map(function(word) {
        return word.replace(word[0], word[0].toUpperCase())
    }).join('')
}

function unescape(string) {
  return new DOMParser().parseFromString(string,'text/html').querySelector('html').textContent
}


class Corpora {
    constructor(config={}) {
        this.host = 'host' in config ? config.host : ""
        this.auth_token = 'auth_token' in config ? config.auth_token : ""
        this.csrf_token = 'csrf_token' in config ? config.csrf_token : ""
    }

    make_request(path, type, params={}, callback, spool=false, spool_records = []) {
        let req = {
            type: type,
            url: `${this.host}${path}`,
            dataType: 'json',
            data: params,
            success: callback
        }

        if (path.startsWith('http')) {
            req.url = path
        }

        if (spool) {
            let corpora_instance = this
            req.success = function(data) {
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
        }

        if (this.auth_token) {
            req['beforeSend'] = function(xhr) { xhr.setRequestHeader("Authorization", `Token ${sender.auth_token}`); }
        } else if (type === 'POST' && this.csrf_token) {
            req['data'] = Object.assign({}, req['data'], {'csrfmiddlewaretoken': this.csrf_token})
        }

        let sender = this
        return $.ajax(req)
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
                corpus.events = new ReconnectingEventSource(`/events/${id}/`)
                corpus.events.addEventListener('alert', function (e) {
                    let alert = JSON.parse(e.data)
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
                }, false)
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
        }

        let search_param_input = $('#content-selection-search-params')

        let content_selection_params = {
            q: search_param_input.data('q'),
            only: 'label',
            s_label: 'asc',
            'page-size': search_param_input.data('page-size'),
            page: search_param_input.data('page')
        }

        corpora.list_content(corpus_id, content_type, content_selection_params, function(data){
            $('#content-selection-modal-prev-page-button').prop('disabled', content_selection_params.page <= 1)
            $('#content-selection-modal-next-page-button').prop('disabled', !data.meta.has_next_page)

            $('#content-selection-modal-label').html(`Select ${content_type}`)
            $('#content-selection-modal-table-header').html(content_type)
            $('#content-selection-modal-table-body').html('')
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

            // HANDLE SEARCH BOX
            $('#content-selection-modal-filter-box').keypress(function (e) {
                let key = e.which
                if (key === 13) {
                    search_param_input.data('q', $('#content-selection-modal-filter-box').val())
                    sender.select_content(corpus_id, content_type, callback, false)
                }
            })

            // previous select content page click event
            $('#content-selection-modal-prev-page-button').click(function() {
                search_param_input.data('page', content_selection_params.page - 1)
                sender.select_content(corpus_id, content_type, callback, false)
            })

            // next select content page click event
            $('#content-selection-modal-next-page-button').click(function() {
                search_param_input.data('page', content_selection_params.page + 1)
                sender.select_content(corpus_id, content_type, callback, false)
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

    date_string(timestamp, granularity='Day', adjust_for_timezone=true) {
        let date = new Date(timestamp)
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
}


class ContentTable {
    constructor(config={}) {
        this.container_id = 'container_id' in config ? config.container_id : null
        this.corpora = 'corpora' in config ? config.corpora : null
        this.corpus = 'corpus' in config ? config.corpus : null
        this.content_type = 'content_type' in config ? config.content_type : null
        this.mode = 'mode' in config ? config.mode : 'edit'
        this.search = 'search' in config ? config.search : {
            'page': 1,
            'page-size': 5,
        }
        this.on_load = 'on_load' in config ? config.on_load : null
        this.meta = null
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
            let selected_content = this.selected_content
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
            if (sender.mode === 'edit' && (role === 'Editor' || role === 'Admin')) {
                if (sender.content_view) {
                    edit_action = `
                        <button role="button" id="ct-${ct.name}${sender.id_suffix}-refresh-view-button" class="btn btn-primary rounded mr-2">Refresh View</button>
                        <button role="button" id="ct-${ct.name}${sender.id_suffix}-delete-view-button" class="btn btn-primary rounded mr-2">Delete View</button>
                    `
                } else {
                    edit_action = `<a role="button" id="ct-${ct.name}${sender.id_suffix}-new-button" href="/corpus/${corpus_id}/${ct.name}/" class="btn btn-primary rounded mr-2">Create</a>`
                }
            }

            this.container.append(`
                <div class="row">
                    <div class="col-12">
                        <a name="${ct.plural_name}"></a>
                        <div class="card mt-4">
                            <div class="card-header" style="padding: 0 !important;">
                                <div class="d-flex w-100 justify-content-between align-items-center text-nowrap p-2 ml-2">
                                    <h4>${sender.label}</h4>
                                    <div class="input-group ml-2 mr-2">
                                        <div class="input-group-prepend">
                                            <button id="ct-${ct.name}${sender.id_suffix}-search-type-selection" class="btn btn-primary dropdown-toggle" type="button" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">Text Search</button>
                                            <div id="ct-${ct.name}${sender.id_suffix}-search-type-menu" class="dropdown-menu">
                                                <span class="p-2">Select a specific field from the dropdown to the right in order to choose a different search type.</span>
                                            </div>
                                            <input type="hidden" id="ct-${ct.name}${sender.id_suffix}-search-type-value" value="default" />
                                        </div>
                                        <input type="text" class="form-control" id="ct-${ct.name}${sender.id_suffix}-search-box" placeholder="Search" />
                                        <div class="input-group-append">
                                            <button id="ct-${ct.name}${sender.id_suffix}-search-setting-selection" class="btn btn-primary dropdown-toggle" type="button" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">All Fields</button>
                                            <div id="ct-${ct.name}${sender.id_suffix}-search-settings-menu" class="dropdown-menu">
                                                <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-setting" id="ct-${ct.name}${sender.id_suffix}-search-setting-default" href="#">All Fields</a>
                                            </div>
                                            <input type="hidden" id="ct-${ct.name}${sender.id_suffix}-search-setting-value" value="default" />
                                        </div>
                                    </div>

                                    <button id="ct-${ct.name}${sender.id_suffix}-search-clear-button" class="btn btn-primary rounded mr-2 d-none" type="button">Clear Search</button>
                                    ${edit_action}

                                    
                                </div>
                                <div id="ct-${ct.name}${sender.id_suffix}-current-search-div" class="d-flex w-100 align-items-center p-2 pl-3 badge-secondary" style="padding-top: 12px !important;"></div>
                            </div>
                            <div class="card-body p-0">
                                <table class="table table-striped mb-0">
                                    <thead class="thead-dark">
                                        <tr id="ct-${ct.name}${sender.id_suffix}-table-header-row">
                                        </tr>
                                    </thead>
                                    <tbody id="ct-${ct.name}${sender.id_suffix}-table-body">
                                    </tbody>
                                </table>
                                <div class="row px-4">
                                    <div class="col-sm-12 d-flex w-100 justify-content-between align-items-center text-nowrap p-2 ml-2">
                                        ${ sender.mode === 'edit' ? `<div class="form-inline">
                                            With selected:
                                            <select class="form-control-sm btn-primary ml-1 mr-1" id="ct-${ct.name}${sender.id_suffix}-selection-action-selector" data-ct="${ct.name}">
                                                <option value="explore" selected>Explore</option>
                                                ${['Editor', 'Admin'].includes(role) ? '<option value="bulk-edit">Bulk Edit</option>' : ''}
                                                ${['Editor', 'Admin'].includes(role) ? '<option value="merge">Merge</option>' : ''}
                                                ${['Editor', 'Admin'].includes(role) ? '<option value="create_view">Create View</option>' : ''}
                                                ${['Editor', 'Admin'].includes(role) ? '<option value="delete">Delete</option>' : ''}
                                            </select>
                                            <button type="button" class="btn btn-sm btn-secondary" id="ct-${ct.name}${sender.id_suffix}-selection-action-go-button" data-ct="${ct.name}" disabled>Go</button>
                                        </div>` : ''}
                                        
                                        <div class="form-inline ml-auto mr-2">
                                            <select class="form-control btn-primary d-none" id="ct-${ct.name}${sender.id_suffix}-page-selector">
                                            </select>
                                        </div>
        
                                        <div class="form-inline mr-2">
                                            <select class="form-control btn-primary" id="ct-${ct.name}${sender.id_suffix}-per-page-selector">
                                                <option value="5" selected>5 Per Page</option>
                                                <option value="10">10 Per Page</option>
                                                <option value="20">20 Per Page</option>
                                                <option value="50">50 Per Page</option>
                                                <option value="80">80 Per Page</option>
                                                <option value="100">100 Per Page</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `)

            // setup view refreshing and deletion
            if (sender.content_view) {
                $(`#ct-${ct.name}${sender.id_suffix}-refresh-view-button`).click(function() {
                    let submission = {
                        'cv-action': 'refresh',
                    }

                    corpora.make_request(
                        `/api/corpus/${corpus.id}/content-view/${sender.content_view_id}/`,
                        'POST',
                        submission,
                        function (data) {
                            let refresh_button = $(`#ct-${ct.name}${sender.id_suffix}-refresh-view-button`)

                            if (data.status === 'populating') {
                                refresh_button.html('Refreshing...')
                                refresh_button.attr('disabled', true)
                                corpora.await_content_view_population(corpus.id, data.id, function(data) {
                                    refresh_button.html('Refresh')
                                    refresh_button.attr('disabled', false)
                                    corpora.list_content(sender.corpus.id, sender.content_type, sender.search, function(content){ sender.load_content(content); })
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

            // handle select all box checking/unchecking
            $(`#ct_${ct.name}${sender.id_suffix}_select-all_box`).change(function() {
                let ct_name = $(this).data('ct')
                let go_button = $(`#ct-${ct_name}${sender.id_suffix}-selection-action-go-button`)

                if ($(this).is(':checked')) {
                    selected_content.all = true
                    selected_content.ids = []

                    $(`.ct-${ct_name}${sender.id_suffix}-selection-box`).each(function() {
                        $(this).prop("checked", true)
                        $(this).attr("disabled", true)
                    })

                    go_button.removeAttr('disabled')
                } else {
                    selected_content.all = false
                    $(`.ct-${ct_name}${sender.id_suffix}-selection-box`).each(function() {
                        $(this).prop("checked", false)
                        $(this).removeAttr("disabled")
                    })

                    go_button.attr('disabled', true)
                }
            })

            // setup content type search fields
            let search_settings_menu = $(`#ct-${ct.name}${sender.id_suffix}-search-settings-menu`)
            for (let x = 0; x < ct.fields.length; x++) {
                if (ct.fields[x].in_lists) {
                    search_settings_menu.append(`
                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-setting" id="ct-${ct.name}${sender.id_suffix}-search-setting-${ct.fields[x].type === 'cross_reference' ? ct.fields[x].name + '.label' : ct.fields[x].name}" href="#">${ct.fields[x].label}</a>
                    `)

                    // add cross reference sub field options
                    if (ct.fields[x].type === 'cross_reference') {
                        if (corpus.content_types.hasOwnProperty(ct.fields[x].cross_reference_type)) {
                            let cx = corpus.content_types[ct.fields[x].cross_reference_type]
                            for (let y = 0; y < cx.fields.length; y++) {
                                if (cx.fields[y].in_lists && cx.fields[y].type !== 'cross_reference') {
                                    search_settings_menu.append(`
                                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-setting" id="ct-${ct.name}${sender.id_suffix}-search-setting-${ct.fields[x].name + '.' + cx.fields[y].name}" href="#">${ct.fields[x].label} -> ${cx.fields[y].label}</a>
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
                let field = event.target.id.replace(`ct-${ct.name}${sender.id_suffix}-search-setting-`, '')
                let label = $(this).text()
                let search_type_menu = $(`#ct-${ct.name}${sender.id_suffix}-search-type-menu`)

                if (field === 'default') {
                    search_type_menu.html(`
                        <span class="p-2">Select a specific field from the dropdown to the right in order to choose a different search type.</span>
                    `)
                } else {
                    search_type_menu.html(`
                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-default" href="#">Text Search</a>
                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-exact" href="#">Exact Search</a>
                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-term" href="#">Term Search</a>
                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-phrase" href="#">Phrase Search</a>
                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-wildcard" href="#">Wildcard Search</a>
                        <a class="dropdown-item ct-${ct.name}${sender.id_suffix}-search-type" id="ct-${ct.name}${sender.id_suffix}-search-type-range" href="#">Range Search</a>
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
                $(`#ct-${ct.name}${sender.id_suffix}-search-setting-value`).val(field)
            })

            // setup page selector events
            $(`#ct-${ct.name}${sender.id_suffix}-page-selector`).on("change", function () {
                let page_token = $(this).find(':selected').data('page-token')
                if (page_token) {
                    search['page-token'] = page_token
                } else {
                    delete search['page-token']
                    search.page = parseInt($(`#ct-${ct.name}${sender.id_suffix}-page-selector`).val())
                }
                corpora.list_content(corpus_id, ct.name, search, function(content){ sender.load_content(content); })
            })

            $(`#ct-${ct.name}${sender.id_suffix}-per-page-selector`).on("change", function () {
                search['page-size'] = parseInt($(`#ct-${ct.name}${sender.id_suffix}-per-page-selector`).val())
                search['page'] = 1
                corpora.list_content(corpus_id, ct.name, search, function(content){ sender.load_content(content); })
            })

            // setup search events
            $(`#ct-${ct.name}${sender.id_suffix}-search-box`).keypress(function (e) {
                let key = e.which
                if (key === 13) {
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
                        search.q = query
                    } else {
                        let param_prefix = search_type_map[search_type]
                        search[`${param_prefix}_${field}`] = query
                    }

                    $(`#ct-${ct.name}${sender.id_suffix}-search-clear-button`).removeClass('d-none')
                    corpora.list_content(corpus_id, ct.name, search, function(content){ sender.load_content(content); })
                }
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
                search.page = 1
                $(`#ct-${ct.name}${sender.id_suffix}-search-setting-selection`).text("All Fields")
                $(`#ct-${ct.name}${sender.id_suffix}-search-setting-value`).val('default')

                corpora.list_content(corpus_id, ct.name, search, function(content) { sender.load_content(content); })
            })

            $(`#ct-${ct.name}${sender.id_suffix}-selection-action-go-button`).click(function() {
                let ct_name = $(this).data('ct')
                let action = $(`#ct-${ct.name}${sender.id_suffix}-selection-action-selector`).val()
                let multi_form = $('#multiselect-form')
                $('#multiselect-content-ids').val(selected_content.ids.join(','))

                if (action === 'explore') {
                    multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/explore/`)
                    multi_form.submit()
                } else if (action === 'bulk-edit') {
                    multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/`)
                    if (selected_content.all) {
                        multi_form.append(`<input id='multiselect-content-query' type='hidden' name='content-query'>`)
                        $('#multiselect-content-query').val(JSON.stringify(search))
                    }
                    multi_form.submit()
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
                    multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/bulk-job-manager/`)
                    multi_form.append(`
                        <input type='hidden' name='task-id' value='${action}'/>
                    `)
                    if (selected_content.all) {
                        multi_form.append(`<input id='multiselect-content-query' type='hidden' name='content-query'>`)
                        $('#multiselect-content-query').val(JSON.stringify(search))
                    }
                    multi_form.submit()
                }
            })

            // perform initial query of content based on search settings
            corpora.list_content(corpus_id, ct.name, search, function(content){ sender.load_content(content); })

            // populate content targeted tasks
            corpora.get_tasks(ct.name, function(tasks_data) {
                if (tasks_data.length > 0) {
                    let task_selection_html = '<optgroup label="Launch Job">'
                    tasks_data.map(task => {
                        if (role === 'Admin' || available_tasks.includes(task.id)) {
                            task_selection_html += `<option value="${task.id}">${task.name}</option>`
                        }
                    })
                    task_selection_html += '</optgroup>'
                    $(`#ct-${ct.name}${sender.id_suffix}-selection-action-selector`).append(task_selection_html)
                }
            })
        }
    }

    load_content(content) {
        let corpora = this.corpora
        let corpus = this.corpus
        let ct = corpus.content_types[content.meta.content_type]
        let search = this.search
        let selected_content = this.selected_content
        let sender = this

        // instantiate some variables to keep track of elements
        let ct_table_body = $(`#ct-${ct.name}${sender.id_suffix}-table-body`); // <-- the table body for listing results
        let page_selector = $(`#ct-${ct.name}${sender.id_suffix}-page-selector`); // <-- the page select box
        let per_page_selector = $(`#ct-${ct.name}${sender.id_suffix}-per-page-selector`); // <-- the page size select box
        let current_search_div = $(`#ct-${ct.name}${sender.id_suffix}-current-search-div`); // <-- the search criteria div

        // clear the table body, page selector, and search criteria div
        ct_table_body.html('')
        page_selector.html('')
        current_search_div.html('')

        // add the total number of results to the search criteria div
        current_search_div.append(`
            <span id="ct-${ct.name}${sender.id_suffix}-total-badge" class="badge badge-primary p-2 mr-2" data-total="${content.meta.total}" style="font-size: 12px;">
                Total: ${content.meta.total.toLocaleString('en-US')}
            </span>
        `)

        // add existing search criteria to the div
        let has_filtering_criteria = false
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

                if (setting_type === 'Searching') { has_filtering_criteria = true; }

                current_search_div.append(`
                    <span class="badge badge-primary p-2 mr-2" style="font-size: 12px;">
                        ${setting_type} ${field_name} "${search_value}"
                        <a class="text-white ${ct.name}${sender.id_suffix}-remove-search-param" data-search-param="${search_setting}"><i class="far fa-times-circle"></i></a>
                    </span>
                `)
            }
        }

        // remove search param event
        $(`.${ct.name}${sender.id_suffix}-remove-search-param`).click(function() {
            sender.remove_search_param($(this).data('search-param'))
        })

        if (content.hasOwnProperty('meta')) sender.meta = content.meta

        // if there are no search results, show a default message
        if (content.records.length < 1) {
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
                        <div class="alert alert-warning">
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
            if (content.meta.hasOwnProperty('next_page_token')) {
                page_selector.append(`<option value="${content.meta.page}" selected>Page ${content.meta.page}</option>`)
                page_selector.append(`<option value="${content.meta.page + 1}" data-page-token="${content.meta.next_page_token}">Page ${content.meta.page + 1}</option>`)
                page_selector.removeClass("d-none")
                per_page_selector.prop('disabled', true)
            }
            else {
                // setup the page selector based on total # of pages within 50 page range
                let min_page = content.meta.page - 50
                let max_page = content.meta.page + 50
                let first_pg_msg = ''
                let last_pg_msg = ''

                if (min_page < 1) {
                    min_page = 1
                }
                if (max_page > content.meta.num_pages) {
                    max_page = content.meta.num_pages
                }

                while(max_page * content.meta.page_size > 9000)
                    max_page -= 1

                if (min_page > 1) {
                    first_pg_msg = ' and below'
                }
                if (max_page < content.meta.num_pages) {
                    last_pg_msg = ' and above'
                }

                let current_page_added = false
                for (let x = min_page; x <= max_page; x++) {
                    let option_html = `<option value="${x}">Page ${x}</option>`

                    if (x === content.meta.page) {
                        option_html = option_html.replace('">', '" selected>')
                        current_page_added = true
                    }
                    if (x === min_page) {
                        option_html = option_html.replace('</', `${first_pg_msg}</`)
                    } else if (x === max_page) {
                        option_html = option_html.replace('</', `${last_pg_msg}</`)
                    }

                    page_selector.append(option_html)
                }

                if (!current_page_added) {
                    page_selector.append(`<option value="${content.meta.page}" selected>Page ${content.meta.page}</option>`)
                } else {
                    per_page_selector.prop('disabled', false)
                }

                page_selector.removeClass("d-none")
                per_page_selector.removeClass("d-none")
                per_page_selector.val(search['page-size'].toString())
            }

            // iterate through the records, adding a row for each one
            content.records.forEach(item => {
                let selected = ''
                if (selected_content.all) {
                    selected = "checked disabled"
                } else if (selected_content.ids.includes(item.id)) {
                    selected = "checked"
                }

                let row_html = `
                    <tr>
                        <td class="ct-selection-cell">
                            ${ sender.mode === 'edit' ? `<input type="checkbox" id="ct_${ct.name}${sender.id_suffix}_${item.id}_selection-box" class="ct-${ct.name}${sender.id_suffix}-selection-box" data-ct="${ct.name}" data-id="${item.id}" ${selected}>` : '' }
                            <a href="${item.uri}" target="_blank">
                                <span class="badge">Open <span class="fas fa-external-link-square-alt"></span></span>
                            </a>
                        </td>
                `

                ct.fields.map(field => {
                    if (field.in_lists) {
                        let value = ''
                        if (item.hasOwnProperty(field.name)) {
                            value = item[field.name]

                            if (field.cross_reference_type && value) {
                                if (field.multiple) {
                                    let multi_value = ''
                                    for (let y in value) {
                                        multi_value += `, <a href="${value[y].uri}" target="_blank">${sender.strip_tags(value[y].label)}</a>`
                                    }
                                    if (multi_value) {
                                        multi_value = multi_value.substring(2)
                                    }
                                    value = multi_value
                                } else {
                                    value = `<a href="${value.uri}" target="_blank">${sender.strip_tags(value.label)}</a>`
                                }
                            } else if (field.multiple) {
                                if (field.type === 'text' || field.type === 'large_text' || field.type === 'keyword') {
                                    value = value.join(' ')
                                } else {
                                    let multi_value = ''
                                    for (let y in value) {
                                        if (field.type === 'date') {
                                            multi_value += `, ${corpora.date_string(value[y])}`
                                        } else if (field.type === 'timespan') {
                                            multi_value += `, ${corpora.timespan_string(value[y])}`
                                        }
                                        else {
                                            multi_value += `, ${value[y]}`
                                        }
                                    }
                                    if (multi_value) {
                                        multi_value = multi_value.substring(2)
                                    }
                                    value = multi_value
                                }
                            }
                            else if (field.type === 'date') {
                                value = corpora.date_string(value)
                            } else if (field.type === 'timespan') {
                                console.log(value)
                                value = corpora.timespan_string(value)
                            } else if (field.type === 'iiif-image') {
                                value = `<img src='${value}/full/,100/0/default.png' />`
                            } else if (field.type === 'file' && ['.png', '.jpg', '.gif', 'jpeg'].includes(value.toLowerCase().substring(value.length - 4))) {
                                value = `<img src='/iiif/2/${value}/full/,100/0/default.png' />`
                            } else if (field.type === 'large_text') {
                                value = value.slice(0, 500) + '...'
                            }
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
            })
        }

        // handle checking/unchecking content selection boxes
        $(`.ct-${ct.name}${sender.id_suffix}-selection-box`).change(function() {
            let ct_name = $(this).data('ct')
            let content_id = $(this).data('id')
            let go_button = $(`#ct-${ct_name}${sender.id_suffix}-selection-action-go-button`)

            if($(this).is(':checked')) {
                selected_content.ids.push(content_id)
            } else {
                selected_content.ids = selected_content.ids.filter(id => id !== content_id)
            }

            if (selected_content.ids.length > 0) { go_button.removeAttr('disabled'); }
            else { go_button.attr('disabled', true); }
        })

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

        this.corpora.list_content(this.corpus.id, this.content_type, this.search, function(content){ sender.load_content(content); })
    }


    remove_search_param(param) {
        if (this.search.hasOwnProperty(param)) {
            delete this.search[param]
            let sender = this

            this.corpora.list_content(this.corpus.id, this.content_type, this.search, function(content){ sender.load_content(content); })
        }
    }


    strip_tags(label) {
        return label.replace(/(<([^>]+)>)/gi, "")
    }
}


class ContentGraph {
    constructor(corpora, corpus, vis_div_id, vis_legend_id, config={}) {
        this.corpora = corpora
        this.corpus = corpus
        this.corpus_id = corpus.id
        this.corpus_uri = `/corpus/${this.corpus.id}`
        this.nodes = new vis.DataSet([])
        this.edges = new vis.DataSet([])
        this.groups = {}
        this.selected_uris = []
        this.filtering_views = {}
        this.collapsed_relationships = []
        this.hidden_cts = ['Corpus', 'File']
        this.extruded_nodes = []
        this.panes_displayed = {}
        this.seed_uris = []
        this.sprawls = []
        this.sprawl_timer = null
        this.click_timer = null
        this.click_registered = false
        this.hide_singletons = false
        this.per_type_limit = 'per_type_limit' in config ? config['per_type_limit'] : 20
        this.max_mass = 'max_node_mass' in config ? config['max_node_mass'] : 100
        this.vis_div_id = vis_div_id
        this.vis_div = $(`#${vis_div_id}`)
        this.vis_legend_id = vis_legend_id
        this.width = 'width' in config ? config['width'] : this.vis_div.width()
        this.height = 'height' in config ? config['height'] : this.vis_div.height()
        this.min_link_thickness = 'min_link_thickness' in config ? config['min_link_thickness'] : 1
        this.max_link_thickness = 'max_link_thickness' in config ? config['max_link_thickness'] : 15
        this.default_link_thickness = 'default_link_thickness' in config ? config['default_link_thickness'] : 1
        this.label_display = 'label_display' in config ? config['label_display'] : 'full'
        this.last_action = 'explore'
        this.first_start = true
        let sender = this

        // SETUP CT OPTIONS MODAL
        if (!$('#explore-ct-modal').length) {
            $('body').prepend(`
                <!-- Explore CT Modal -->
                <div class="modal fade" id="explore-ct-modal" tabindex="-1" role="dialog" aria-labelledby="explore-ct-modal-label" aria-hidden="true">
                    <div class="modal-dialog" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h4 class="modal-title" id="explore-ct-modal-label"><span class="modal-proxy-ct"></span> Options</h4>
                                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                <span aria-hidden="true">&times;</span>
                                </button>
                            </div>
                            <div class="modal-body">
                            
                                <h5>Filter by View</h5>
                                <div id="explore-ct-cv-div" class="mb-4 p-2"></div>
                                
                                <h5>Collapse Relationship</h5>
                                <div id="explore-ct-modal-collapse-div" class="p-2">
                                    <div class="row">
                                        <div class="col mb-2">
                                            Collapsing a relationship allows you to see the relationships between two different
                                            Content Types that normally are a step removed from each other. So, let's say a
                                            Content Type called "Novel" refers to a Content Type
                                            called "Chapter," and "Chapter" in turn refers to "Character." By
                                            clicking on "Chapter" in the legend (displaying this window), choosing "Novel" from the dropdown on the left,
                                            choosing "Character" from the dropdown on the right, and then clicking on the "Collapse"
                                            button, the visualization will hide all "Chapter" nodes and simply show all indirect
                                            relationships between "Novel" and "Character."
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col">
                                            <select class="form-control" id="from_ct_selector"></select>
                                        </div>
                                        <div class="col text-center">
                                            <i class="fas fa-arrow-left"></i> <span class="modal-proxy-ct"></span> <i class="fas fa-arrow-right"></i>
                                        </div>
                                        <div class="col">
                                            <select class="form-control" id="to_ct_selector"></select>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col mt-2 text-center">
                                            <select class="form-control" id="addproxy_ct_selector">
                                                <option value="None">Select Content Type to add another step to collapse...</option>
                                            </select>
                                            <button type="button" class="btn btn-primary" id="collapse-add-button">Collapse</button>
                                        </div>
                                    </div>
                                </div>
                                <div id="explore-ct-modal-already-collapsed-div" class="p-2 d-none">
                                    This Content Type is in a collapsed relationship. To uncollapse, click
                                    "uncollapse" next to Content Type in the visualization legend.
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                                <button type="button" class="btn btn-primary" id="explore-ct-sprawl-button">Sprawl Every <span class="modal-proxy-ct"></span></button>
                                <button type="button" class="btn btn-primary" id="explore-ct-hide-button">Hide Every <span class="modal-proxy-ct"></span></button>
                            </div>
                        </div>
                    </div>
                </div>
            `)

            // SETUP EXPLORE CT MODAL COLLAPSE SELECTORS AND EVENTS
            let from_ct_selector = $('#from_ct_selector')
            let to_ct_selector = $('#to_ct_selector')
            let add_ct_selector = $('#addproxy_ct_selector')
            for (let ct_name in this.corpus.content_types) {
                let option = `<option value='${ct_name}'>${ct_name}</option>`
                from_ct_selector.append(option)
                to_ct_selector.append(option)
                add_ct_selector.append(option)
            }

            add_ct_selector.change(function() {
                let ct_to_add = add_ct_selector.val()
                if (ct_to_add !== 'None') {
                    let cts_added = $('.modal-proxy-ct').html()
                    $('.modal-proxy-ct').html(cts_added + '.' + ct_to_add)
                }
            })

            $('#collapse-add-button').click(function() {
                let proxy_ct = $('.modal-proxy-ct').html()

                sender.collapsed_relationships.push({
                    from_ct: $('#from_ct_selector').val(),
                    proxy_ct: proxy_ct,
                    to_ct: $('#to_ct_selector').val()
                })

                sender.reset_graph()

                $('#explore-ct-modal').modal('hide')
            })

            $('#explore-ct-hide-button').click(function() {
                let hide_ct = $('.modal-proxy-ct').html()
                sender.hidden_cts.push(hide_ct)
                sender.reset_graph()
                $('#explore-ct-modal').modal('hide')
            })

            $('#explore-ct-sprawl-button').click(function() {
                let sprawl_ct = $('.modal-proxy-ct').html()
                sender.nodes.map(n => {
                    if (n.id.includes(`/${sprawl_ct}/`)) {
                        sender.sprawl_node(n.id)
                    }
                })
                $('#explore-ct-modal').modal('hide')
            })
        }

        // ENSURE MULTISELECT FORM EXISTS
        if (!$('#multiselect-form').length) {
            $('body').append(`
                <form id="multiselect-form" method="post" action="/not/set">
                    <input type="hidden" name="csrfmiddlewaretoken" value="${this.corpora.csrf_token}">
                    <input id="multiselect-content-ids" name="content-ids" type="hidden" value="">
                </form>
            `)
        }

        // ADD INITIAL CONTENT TO GRAPH
        if ('seeds' in config) {
            config.seeds.map(seed => {
                this.seed_uris.push(seed)
            })
        }

        // SETUP LEGEND
        this.setup_legend()

        // SETUP VIS.JS NETWORK
        this.network = new vis.Network(
            this.vis_div[0],
            {
                nodes: this.nodes,
                edges: this.edges
            },
            {
                nodes: {
                    shape: 'dot',
                    size: 10,
                    scaling: {
                        min: 10,
                        max: 200,
                        label: {
                            enabled: true,
                            min: 14,
                            max: 30,
                            maxVisible: 30,
                            drawThreshold: 5
                        }
                    },
                    font: {
                        background: "white"
                    },
                    mass: 2
                },
                edges: {
                    smooth: {
                        type: "continuous"
                    }
                },
                groups: this.groups,
                interaction: {
                    zoomSpeed: 0.4,
                    hover: true,
                    tooltipDelay: this.label_display === 'full' ? 3600000 : 100
                },
                physics: {
                    solver: 'barnesHut',
                    barnesHut: {
                        springConstant: .01,
                        damping: 0.8,
                        avoidOverlap: 1,
                        springLength: 200
                    },
                    /*
                    solver: 'repulsion',
                    repulsion: {
                        springConstant: .01,
                        centralGravity: .1,
                        nodeDistance: 200
                    },
                     */
                    stabilization: {
                        enabled: true,
                        fit: true
                    },
                    groups: this.groups
                },
            }
        )

        // ADD WHITE BACKGROUND
        this.network.on("beforeDrawing",  function(ctx) {
            // save current translate/zoom
            ctx.save()
            // reset transform to identity
            ctx.setTransform(1, 0, 0, 1, 0, 0)
            // fill background with solid white
            ctx.fillStyle = '#ffffff'
            ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height)
            // restore old transform
            ctx.restore()
        })

        // CUSTOM PHYSICS
        this.network.physics._performStep = function(nodeId) {
            const node = this.body.nodes[nodeId]
            const force = this.physicsBody.forces[nodeId]

            if (node.options.hasOwnProperty('group')) {
                force.x += this.options.groups[node.options.group].wind.x
                force.y += this.options.groups[node.options.group].wind.y
            }

            const velocity = this.physicsBody.velocities[nodeId]

            // store the state so we can revert
            this.previousStates[nodeId] = {
                x: node.x,
                y: node.y,
                vx: velocity.x,
                vy: velocity.y,
            }

            if (node.options.fixed.x === false) {
                velocity.x = this.calculateComponentVelocity(
                    velocity.x,
                    force.x,
                    node.options.mass
                )
                node.x += velocity.x * this.timestep
            } else {
                force.x = 0
                velocity.x = 0
            }

            if (node.options.fixed.y === false) {
                velocity.y = this.calculateComponentVelocity(
                    velocity.y,
                    force.y,
                    node.options.mass
                )
                node.y += velocity.y * this.timestep
            } else {
                force.y = 0
                velocity.y = 0
            }

            const totalVelocity = Math.sqrt(
                Math.pow(velocity.x, 2) + Math.pow(velocity.y, 2)
            )
            return totalVelocity
        }

        this.network.on("click", function(params) {
            sender.remove_unpinned_panes()

            if (params.nodes.length > 0) {
                let clicked_uri = params.nodes[0]
                let pane_id = `${clicked_uri.replace(/\//g, '-')}-pane`
                let canvas_offset = sender.vis_div.offset()
                let pane_x = params.pointer.DOM.x + canvas_offset.left
                let pane_y = params.pointer.DOM.y + canvas_offset.top

                if (!$(`#${pane_id}`).length) {
                    $('body').append(`
                        <div id="${pane_id}"
                            class="content-pane"
                            style="background-color: rgba(255, 255, 255, .8)
                                width: 200px
                                height: 225px
                                position: absolute
                                top: ${pane_y}px
                                left: ${pane_x}px
                                pointer-events: auto;"
                            data-uri="${clicked_uri}">
    
                            <div style="height: 25px;">
                                <span id="${pane_id}-select" title="Select" data-uri="${clicked_uri}" class="popup-button far fa-check-square" ${sender.selected_uris.includes(clicked_uri) ? "style='color: #EF3E36;'" : ''}></span>
                                <span id="${pane_id}-pin" title="Pin" data-uri="${clicked_uri}" class="popup-button fas fa-thumbtack"></span>
                                <span id="${pane_id}-sprawl" title="Sprawl" data-uri="${clicked_uri}" class="popup-button fas fa-expand-arrows-alt"></span>
                                <span id="${pane_id}-extrude" title="Hide" data-uri="${clicked_uri}" class="popup-button far fa-eye-slash"></span>
                                <a href="${clicked_uri}/" target="_blank"><span title="Open" class="popup-button float-right fas fa-external-link-square-alt"></span></a>
                            </div>
                            <div id="${pane_id}-meta">
                            </div>
                            <iframe id="${pane_id}-iframe" src="${clicked_uri}/?popup=y" frameBorder="0" width="200px" height="200px" />
                        </div>
                    `)

                    sender.build_meta_controls(clicked_uri, pane_id)

                    $(`#${pane_id}-select`).click(function() {
                        let uri = $(this).data('uri')
                        let node = sender.nodes.get(uri)

                        if (!sender.selected_uris.includes(uri)) {
                            sender.selected_uris.push(uri)
                            $(this).css('color', '#EF3E36')
                            node.font = {
                                background: '#EF3E36',
                                color: "white"
                            }
                        } else {
                            sender.selected_uris = sender.selected_uris.filter(val => val !== uri)
                            $(this).css('color', '#091540')
                            node.font = {
                                background: 'white',
                                color: "black"
                            }
                        }
                        sender.nodes.update(node)
                        sender.setup_legend()
                    })

                    $(`#${pane_id}-pin`).click(function() {
                        sender.pin_node($(this).data('uri'))
                    })

                    $(`#${pane_id}-sprawl`).click(function() {
                        sender.sprawl_node($(this).data('uri'), {pane_id: pane_id})
                    })

                    $(`#${pane_id}-extrude`).click(function() {
                        sender.extrude_node($(this).data('uri'), true)
                    })

                    sender.panes_displayed[clicked_uri] = {pinned: false}
                    sender.make_draggable(document.getElementById(pane_id))
                }
            }
        })

        this.network.on("dragStart", function(params){
            params.nodes.map(id => {
                let n = sender.nodes.get(id)
                n.fixed = false
                //affix_node_label(n)
                sender.nodes.update(n)
            })
        })

        this.network.on("dragEnd", function(params){
            params.nodes.map(id => {
                sender.nodes.update([{ id: id, fixed: true }])
            })
        })

        this.seed_uris.map(uri => this.sprawl_node(uri, {is_seed: true, sprawl_children: true}))
    }

    setup_legend() {
        let sender = this
        let group_colors = [
            '#EF3E36',
            '#091540',
            '#17BEBB',
            '#BFC0C0',
            '#2191FB',
            '#297045',
            '#9448BC',
            '#FFB627',
            '#CCC9E7',
            '#E9E3B4',
        ]
        let group_winds = [
            {x: 0, y: -1},
            {x: 0, y: 1},
            {x: -1, y: 0},
            {x: 1, y: 0},
            {x: -.5, y: .5},
            {x: .5, y: -.5},
            {x: -.7, y: -.7},
            {x: .7, y: .7},
            {x: -.5, y: -.5},
            {x: .5, y: .5}
        ]
        let group_color_cursor = 0

        // ensure the first content type in seeds receives the first color
        if (this.seed_uris.length) {
            let seed_group = this.seed_uris[0].split('/')[3]
            this.groups[seed_group] = {color: group_colors[group_color_cursor], wind: group_winds[group_color_cursor]}
            group_color_cursor++
        }

        let group_names = Object.keys(this.corpus.content_types).map(ct => ct)
        group_names.map(group_name => {
            if (group_name !== 'Corpus' && !Object.keys(this.groups).includes(group_name)) {
                this.groups[group_name] = {
                    color: group_colors[group_color_cursor],
                    wind: group_winds[group_color_cursor]
                }
                group_color_cursor++
                if (group_color_cursor >= group_colors.length) group_color_cursor = 0
            }
        })

        let legend = $(`#${this.vis_legend_id}`)
        legend.html('')
        for (let group_name in this.groups) {
            let action_links = ""

            this.collapsed_relationships.map(col_rel => {
                if (group_name === col_rel['proxy_ct']) {
                    action_links += `<a href="#" class="uncollapse-link mr-2" data-collapse="${col_rel.proxy_ct}">uncollapse</a>`
                }
            })

            this.hidden_cts.map(hidden => {
                if (group_name === hidden) {
                    action_links += `<a href="#" class="unhide-link mr-2" data-hidden="${hidden}">unhide</a>`
                }
            })

            legend.append(`
                <span class="badge mr-1 p-1 ct-legend-badge" style="background-color: ${this.groups[group_name].color}; color: #FFFFFF; cursor: pointer;">${group_name}</span>${action_links}
            `)
        }

        // LABEL OPTIONS
        legend.append(`
            <select id="explore-label-opt" class="mr-2">
                <option value="full" ${sender.label_display === 'full' ? 'selected' : ''}>Show full label</option>
                <option value="trunc" ${sender.label_display === 'trunc' ? 'selected' : ''}>Show truncated label</option>
                <option value="hover" ${sender.label_display === 'hover' ? 'selected' : ''}>Show label only on hover</option>
            </select>
        `)

        // SPRAWL OPTIONS
        legend.append(`
            <label for="explore-sprawl-opt" class="mr-1 mb-0">Sprawl Size:</label>
            <select id="explore-sprawl-opt" class="mr-2">
                <option value="5" ${sender.per_type_limit === 5 ? 'selected' : ''}>5</option>
                <option value="10" ${sender.per_type_limit === 10 ? 'selected' : ''}>10</option>
                <option value="20" ${sender.per_type_limit === 20 ? 'selected' : ''}>20</option>
                <option value="40" ${sender.per_type_limit === 40 ? 'selected' : ''}>40</option>
                <option value="80" ${sender.per_type_limit === 80 ? 'selected' : ''}>80</option>
            </select>
        `)

        // SINGLETON HIDING
        legend.append(`
            <button id="explore-hide-singletons" class="btn btn-sm btn-primary mr-2">Hide Singletons</button>
        `)

        // HIDE SINGLETONS CLICK
        $('#explore-hide-singletons').click(function() {
            let singletons = []
            sender.nodes.map(n => {
                if (sender.network.getConnectedNodes(n.id).length === 1) singletons.push(n.id)
            })
            singletons.map(uri => {
                let edge_ids = sender.network.getConnectedEdges(uri)
                edge_ids.map(edge_id => sender.edges.remove(edge_id))
                sender.nodes.remove(uri)
            })
        })

        // SELECTED OPTIONS
        if (this.selected_uris.length) {
            legend.append(`
                With selected: 
                <select id="explore-selected-action" class="ml-1">
                    <option value="explore" ${sender.last_action === 'explore' ? 'selected' : ''}>Explore in new tab</option>
                    <option value="hide" ${sender.last_action === 'hide' ? 'selected' : ''}>Hide</option>
                    <option value="sprawl" ${sender.last_action === 'sprawl' ? 'selected' : ''}>Sprawl</option>
                    <option value="merge" ${sender.last_action === 'merge' ? 'selected' : ''}>Merge...</option>
                </select>
                <button type="button" class="btn btn-primary btn-sm" id="explore-selected-action-button">Go</button>
            `)

            $('#explore-selected-action-button').click(function() {
                let action = $('#explore-selected-action').val()
                let ct_name = sender.selected_uris[0].split('/')[3]
                let multi_form = $('#multiselect-form')

                if (action === 'explore') {
                    multi_form.append(`
                        <input type='hidden' name='content-uris' value='${sender.selected_uris.join(',')}'/>
                    `)
                    multi_form.attr('action', `/corpus/${sender.corpus_id}/${ct_name}/explore/?popup=y`)
                    multi_form.attr('target', '_blank')
                    multi_form.submit()
                    multi_form.removeAttr('target')
                } else if (action === 'merge') {
                    let content_ids = []
                    let cts_valid = true

                    sender.selected_uris.map(uri => {
                        let uri_parts = uri.split('/')
                        if (uri_parts[3] === ct_name) {
                            content_ids.push(uri_parts[4])
                        } else {
                            cts_valid = false
                        }
                    })

                    if (cts_valid) {
                        $('#multiselect-content-ids').val(content_ids.join(','))
                        multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/merge/`)
                        multi_form.submit()
                    } else {
                        alert("In order to merge content, all selected nodes must be of the same content type!")
                    }
                } else if (action === 'hide') {
                    sender.selected_uris.map(uri => sender.extrude_node(uri, true))
                    sender.selected_uris = []
                    sender.setup_legend()
                } else if (action === 'sprawl') {
                    sender.selected_uris.map(uri => sender.sprawl_node(uri))
                }

                sender.last_action = action
            })
        }

        // LEGEND CLICK EVENTS
        $('.ct-legend-badge').click(function() {
            clearTimeout(sender.click_timer)
            let click_target = this

            // DOUBLE CLICK
            if (sender.click_registered) {
                sender.click_registered = false
                let explore_ct = $(click_target).html()
                sender.nodes.map(n => {
                    if (n.id.includes(`/${explore_ct}/`)) {
                        sender.sprawl_node(n.id)
                    }
                })
            // SINGLE CLICK
            } else {
                sender.click_registered = true
                sender.click_timer = setTimeout(function() {
                    sender.click_registered = false

                    let explore_ct = $(click_target).html()
                    $('#explore-ct-modal-label').html(`${explore_ct} Options`)
                    $('.modal-proxy-ct').html(explore_ct)

                    let collapsible = true
                    let hideable = !sender.hidden_cts.includes(explore_ct)

                    let cv_div = $('#explore-ct-cv-div')
                    cv_div.html('')
                    if (Object.keys(sender.corpus.content_types[explore_ct]).includes('views')) {
                        cv_div.append(`<select id="cv-selector" class="form-control" data-ct="${explore_ct}"><option value="--">None</option></select>`)
                        let cv_selector = $('#cv-selector')
                        sender.corpus.content_types[explore_ct].views.map(cv => {
                            let selected_indicator = ''
                            if (sender.filtering_views.hasOwnProperty(explore_ct) && sender.filtering_views[explore_ct] === cv.neo_super_node_uri) {
                                selected_indicator = ' selected'
                            }
                            cv_selector.append(`<option value="${cv.neo_super_node_uri}"${selected_indicator}>${cv.name}</option>`)
                        })

                        cv_selector.change(function() {
                            let ct = cv_selector.data('ct')
                            let cv_supernode = cv_selector.val()
                            if (cv_supernode === '--' && Object.keys(sender.filtering_views).includes(ct)) {
                                delete sender.filtering_views[ct]
                            } else {
                                sender.filtering_views[ct] = cv_supernode
                            }

                            sender.reset_graph()
                            $('#explore-ct-modal').modal('hide')
                        })
                    } else {
                        cv_div.append(`
                            <div class="alert alert-info">
                                No Content Views exist for this content type. Click <a id="create-cv-button" role="button">here</a> to create one. 
                            </div>
                        `)
                    }

                    sender.collapsed_relationships.map(col_rel => {
                        if (col_rel.proxy_ct === explore_ct) {
                            collapsible = false
                        }
                    })

                    if (collapsible) {
                        $('#explore-ct-modal-already-collapsed-div').addClass('d-none')
                        $('#explore-ct-modal-collapse-div').removeClass('d-none')
                    } else {
                        $('#explore-ct-modal-already-collapsed-div').removeClass('d-none')
                        $('#explore-ct-modal-collapse-div').addClass('d-none')
                    }

                    if (hideable) {
                        $('#explore-ct-hide-button').attr('disabled', false)
                    } else {
                        $('#explore-ct-hide-button').attr('disabled', true)
                    }

                    $('#explore-ct-modal').modal()

                }, 700)
            }
        })

        $('.uncollapse-link').click(function(e) {
            e.preventDefault()
            let col_proxy = $(this).data('collapse')
            for (let cl_index = 0; cl_index < sender.collapsed_relationships.length; cl_index++) {
                if (sender.collapsed_relationships[cl_index].proxy_ct === col_proxy) {
                    sender.collapsed_relationships.splice(cl_index, 1)
                    break
                }
            }
            sender.reset_graph()
        })

        $('.unhide-link').click(function(e) {
            e.preventDefault()
            let hid_index = sender.hidden_cts.indexOf($(this).data('hidden'))
            sender.hidden_cts.splice(hid_index, 1)
            sender.reset_graph()
        })

        $('#explore-label-opt').change(function() {
            let option = $('#explore-label-opt').val()
            sender.label_display = option
            if (option === 'full') {
                sender.network.setOptions({interaction:{tooltipDelay:3600000}})
            } else {
                sender.network.setOptions({interaction:{tooltipDelay:100}})
            }

            sender.nodes.map(n => {
                sender.format_label(n)
                sender.nodes.update(n)
            })
        })

        $('#explore-sprawl-opt').change(function() {
            sender.per_type_limit = parseInt($(this).val())
        })
    }

    format_label(n) {
        if (this.label_display === 'full') {
            n.label = n.label_data
            n.title = null
        } else if (this.label_display === 'trunc') {
            n.label = n.label_data.slice(0, 20)
            n.title = n.label_data
        } else {
            n.label = ''
            n.title = n.label_data
        }
    }

    sprawl_node(uri, options={}) {
        let opts = Object.assign(
            {
                is_seed: false,
                sprawl_children: false,
                pane_id: null,
                meta_only: false,
                sprawl_ct: null,
                skip: -1,
                resprawls: 0,
            },
            options
        )

        let sender = this
        let node_ct = uri.split('/').slice(-2)[0]
        let node_id = uri.split('/').slice(-1)[0]
        let sprawl_node = this.nodes.get(uri)
        let skip = 0

        if (opts.skip > 0) skip = opts.skip
        else if (sprawl_node && sprawl_node.hasOwnProperty('skip')) {
            skip = sprawl_node.skip
        }

        let net_json_params = {
            per_type_skip: skip,
            per_type_limit: this.per_type_limit
        }

        let filter_param = Object.keys(this.filtering_views).map(ct => `${ct}:${sender.filtering_views[ct]}`).join(',')
        if (filter_param) { net_json_params['filters'] = filter_param; }

        let collapse_param = this.collapsed_relationships.map(rel => `${rel.from_ct}-${rel.proxy_ct}-${rel.to_ct}`).join(',')
        if (collapse_param) { net_json_params['collapses'] = collapse_param; }

        let hidden_param = this.hidden_cts.join(',')
        if (hidden_param) { net_json_params['hidden'] = hidden_param; }

        if (opts.is_seed) net_json_params['is-seed'] = 'y'
        if (opts.meta_only) net_json_params['meta-only'] = 'y'
        if (opts.sprawl_ct) net_json_params['target-ct'] = opts.sprawl_ct

        this.sprawls.push(false)
        clearTimeout(this.sprawl_timer)
        this.sprawl_timer = setTimeout(this.await_sprawls.bind(this), 2000)
        let sprawl_index = this.sprawls.length - 1

        this.corpora.get_network_json(this.corpus_id, node_ct, node_id, net_json_params, function(net_json) {
            let children = []
            let origin_plotted = false
            let nodes_added = 0

            net_json.nodes.map(n => {
                if (n.id !== sender.corpus_uri && !sender.nodes.get(n.id) && !sender.extruded_nodes.includes(n.id)) {
                    n.label_data = unescape(n.label)
                    sender.format_label(n)
                    if (n.id === uri) {
                        n.meta = net_json.meta
                        origin_plotted = true
                    }
                    sender.nodes.add(n)
                    nodes_added += 1
                    if (opts.sprawl_children) {
                        children.push(n.id)
                    }
                }
            })

            net_json.edges.map(e => {
                e.id = `${e.from}-${e.to}`
                if (!sender.extruded_nodes.includes(e.from) && !sender.extruded_nodes.includes(e.to) && !sender.edges.get(e.id)) {
                    sender.edges.add(e)
                }
            })

            if (!origin_plotted) {
                sender.nodes.update([{'id': uri, 'meta': net_json.meta}])
            }

            if (opts.sprawl_children) {
                children.map(child_uri => sender.sprawl_node(child_uri))
            }

            if (!opts.meta_only && !opts.sprawl_ct && sprawl_node && sprawl_node.hasOwnProperty('meta') && nodes_added === 0) {
                let plotted = sender.network.getConnectedEdges(uri).length
                let total_count = 0
                for (let path in sprawl_node.meta) {
                    if (!sprawl_node.meta[path].collapsed) {
                        total_count += sprawl_node.meta[path].count
                    }
                }
                if (plotted < total_count && opts.resprawls < 10) {
                    opts.resprawls += 1
                    sender.sprawl_node(uri, opts)
                }
            }
            if (opts.pane_id) {
                sender.build_meta_controls(uri, opts.pane_id)
            }
        })

        if (sprawl_node && !opts.meta_only && !opts.sprawl_ct) {
            sprawl_node.skip = skip += this.per_type_limit
            sender.nodes.update(sprawl_node)
        }

        sender.sprawls[sprawl_index] = true
    }

    await_sprawls() {
        clearTimeout(this.sprawl_timer)
        if (this.sprawls.includes(false)) {
            this.sprawl_timer = setTimeout(this.await_sprawls.bind(this), 2000)
        } else {
            this.sprawls = []
            this.normalize_collapse_thickness()
            this.setup_legend()

            if (this.first_start) {
                // PIN ALL SEED NODES
                this.seed_uris.map(seed_uri => {
                    this.nodes.update([{id: seed_uri, fixed: true}])
                })

                // FIT NETWORK
                this.network.fit()

                this.first_start = false
            }
        }
    }

    build_meta_controls(uri, pane_id) {
        let sender = this
        let node = this.nodes.get(uri)
        let meta_div = $(`#${pane_id}-meta`)
        meta_div.html('')
        if (!node.hasOwnProperty('meta')) {
            this.sprawl_node(uri, {pane_id: pane_id, meta_only: true})
        } else {
            let node_edge_ids = this.network.getConnectedEdges(uri)
            let ct_counts = {}

            node_edge_ids.map(e_id => {
                let e_parts = e_id.split('-')
                let other = e_parts[1]
                if (other.includes(node.group)) other = e_parts[0]
                let other_ct = other.split('/').slice(-2)[0]
                if (other_ct in ct_counts) ct_counts[other_ct] += 1
                else ct_counts[other_ct] = 1
            })

            for (let path in node.meta) {
                let path_parts = path.split('-')
                let sprawl_ct = path_parts[path_parts.length - 1]
                if (this.groups.hasOwnProperty(sprawl_ct)) {
                    let plotted = ct_counts.hasOwnProperty(sprawl_ct) ? ct_counts[sprawl_ct] : 0
                    meta_div.append(`
                        <span
                            class="badge mr-1 p-1 meta-badge"
                            style="background-color: ${this.groups[sprawl_ct].color}; color: #FFFFFF; cursor: pointer;"
                            data-uri="${uri}" data-sprawl_ct="${sprawl_ct}" data-skip="${plotted}"
                        >
                            ${sprawl_ct} (${plotted} / ${node.meta[path].collapsed ? 'collapsed' : node.meta[path].count})
                        </span>
                    `)
                }
            }

            $('.meta-badge').off('click').on('click', function() {
                sender.sprawl_node($(this).data('uri'), {
                    pane_id: pane_id,
                    sprawl_ct: $(this).data('sprawl_ct'),
                    skip: parseInt($(this).data('skip'))
                })
            })
        }
    }

    reset_graph() {
        this.edges.clear()
        this.nodes.clear()
        this.first_start = true

        this.seed_uris.map(uri => {
            this.sprawl_node(uri, {is_seed: true, sprawl_children: true})
        })
    }

    extrude_node(uri, remove_isolated=false) {
        let sender = this
        this.extruded_nodes.push(uri)
        let edge_ids = this.network.getConnectedEdges(uri)
        edge_ids.map(edge_id => this.edges.remove(edge_id))
        this.nodes.remove(uri)

        if (remove_isolated) {
            let isolated_nodes = new vis.DataView(this.nodes, {
                filter: function (node) {
                    let connEdges = sender.edges.get({
                        filter: function (edge) {
                            return (
                                (edge.to == node.id) || (edge.from == node.id))
                        }
                    })
                    return connEdges.length == 0
                }
            })

            isolated_nodes.map(i => this.extrude_node(i.id, false))
        }
    }

    pin_node(uri) {
        if (!this.panes_displayed[uri].pinned) {
            this.panes_displayed[uri].pinned = true
            let pin_id = `${uri.replace(/\//g, '-')}-pane-pin`
            $(`#${pin_id}`).css('color', '#EF3E36')
        } else {
            this.panes_displayed[uri].pinned = false
            this.remove_unpinned_panes()
        }
    }

    normalize_collapse_thickness() {
        this.collapsed_relationships.map(col_rel => {
            let title_a = `has${col_rel.to_ct}via${col_rel.proxy_ct}`
            let title_b = `has${col_rel.from_ct}via${col_rel.proxy_ct}`

            let redundant_edges = this.edges.get({
                filter: function(edge) {
                    return edge.title === title_b
                }
            })

            redundant_edges.map(r => {
                let id_parts = r.id.split('-')
                let inverse_id = `${id_parts[1]}-${id_parts[0]}`
                let inverse_edge = this.edges.get(inverse_id)
                if (inverse_edge === null) {
                    this.edges.add({
                        id: inverse_id,
                        from: id_parts[1],
                        to: id_parts[0],
                        title: title_a,
                        freq: r.freq
                    })
                }
                this.edges.remove(r.id)
            })

            let col_edges = this.edges.get({
                filter: function(edge) {
                    return edge.title === title_a
                }
            })

            let min_freq = 9999999999999999999999
            let max_freq = 1
            col_edges.map(e => {
                if (e.freq < min_freq) { min_freq = e.freq; }
                if (e.freq > max_freq) { max_freq = e.freq; }
            })

            let updated_edges = []
            col_edges.map(e => {
                let mx = (e.freq - min_freq) / (max_freq - min_freq)
                let preshiftNorm = mx * (this.max_link_thickness - this.min_link_thickness)
                updated_edges.push({
                    id: e.id,
                    value: parseInt(preshiftNorm + this.min_link_thickness)
                })
            })
            this.edges.update(updated_edges)
        })

        let update_nodes = []
        let aggregated_edge_cts = []
        this.collapsed_relationships.map(rel => {
            aggregated_edge_cts.push(rel.from_ct)
            aggregated_edge_cts.push(rel.to_ct)
        })

        this.nodes.map(node => {
            let update_node = {id: node.id, value: 0, mass: 0}

            if (aggregated_edge_cts.includes(node.group)) {
                let conn_edge_ids = this.network.getConnectedEdges(node.id)
                update_node.value = 0
                conn_edge_ids.map(conn_edge_id => {
                    let conn_edge = this.edges.get(conn_edge_id)
                    if (conn_edge.hasOwnProperty('freq')) {
                        update_node.value += conn_edge.freq
                    } else {
                        update_node.value += 1
                    }
                })
            } else {
                update_node.value = this.network.getConnectedEdges(node.id).length
            }
            update_node.mass = update_node.value > this.max_mass ? this.max_mass : update_node.value

            if ((!node.hasOwnProperty('value') || !node.hasOwnProperty('mass')) || (node.value !== update_node.value || node.mass !== update_node.mass)) {
                update_nodes.push(update_node)
            }
        })

        if (update_nodes.length) this.nodes.update(update_nodes)
    }

    remove_unpinned_panes() {
        for (let pane_uri in this.panes_displayed) {
            if (!this.panes_displayed[pane_uri].pinned) {
                let pane_id = `${pane_uri.replace(/\//g, '-')}-pane`
                $(`#${pane_id}`).remove()
                delete this.panes_displayed[pane_uri]
            }
        }
    }

    make_draggable(elmnt) {
        var pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0
        if (document.getElementById(elmnt.id + "header")) {
            // if present, the header is where you move the DIV from:
            document.getElementById(elmnt.id + "header").onmousedown = dragMouseDown
        } else {
            // otherwise, move the DIV from anywhere inside the DIV:
            elmnt.onmousedown = dragMouseDown
        }

        function dragMouseDown(e) {
            e = e || window.event
            e.preventDefault()
            // get the mouse cursor position at startup:
            pos3 = e.clientX
            pos4 = e.clientY
            document.onmouseup = closeDragElement
            // call a function whenever the cursor moves:
            document.onmousemove = elementDrag
        }

        function elementDrag(e) {
            e = e || window.event
            e.preventDefault()
            // calculate the new cursor position:
            pos1 = pos3 - e.clientX
            pos2 = pos4 - e.clientY
            pos3 = e.clientX
            pos4 = e.clientY
            // set the element's new position:
            elmnt.style.top = (elmnt.offsetTop - pos2) + "px"
            elmnt.style.left = (elmnt.offsetLeft - pos1) + "px"
        }

        function closeDragElement() {
            // stop moving when mouse button is released:
            document.onmouseup = null
            document.onmousemove = null
        }
    }
}


class ContentSelector {
    constructor(config={}) {
        this.id_element = 'id_element' in config ? config.id_element : null
        this.label_element = 'label_element' in config ? config.label_element : null
        this.previous_modal = 'previous_modal' in config ? config.previous_modal : null
        this.corpora = 'corpora' in config ? config.corpora : null
        this.corpus = 'corpus' in config ? config.corpus : null
        this.content_type = 'content_type' in config ? config.content_type : null
        this.content_selection_vars = {
            q: '*',
            only: 'label',
            s_label: 'asc',
            page_size: 10,
            page: 1
        }
        this.content_search_timer = null
        this.content_selection_modal = $('#content-selection-modal')

        if (this.corpora && this.corpus && this.content_type) {
            if (!this.content_selection_modal.length) {
                $('body').prepend(`
                    <div class="modal fade" id="content-selection-modal" tabindex="-1" role="dialog" aria-labelledby="content-selection-modal-label" aria-hidden="true">
                        <div class="modal-dialog" role="document">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title" id="content-selection-modal-label">Select ContentType</h5>
                                    <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                    <span aria-hidden="true">&times;</span>
                                    </button>
                                </div>
                                <div class="modal-body">
                                    <input type="hidden" id="content-selection-id-element-id" value="" />
                                    <input type="hidden" id="content-selection-label-element-id" value="" />
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
                                    <button type="button" id="content-selection-modal-prev-page-button" class="btn btn-secondary"><span class="fas fa-angle-left"></span></button>
                                    <button type="button" id="content-selection-modal-next-page-button" class="btn btn-secondary"><span class="fas fa-angle-right"></span></button>
                                    <button type="button" id="content-create-new-button" class="btn btn-primary">Create New</button>
                                    <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `)
            }
        }
    }

    load_content_selection() {
        let sender = this
        this.corpora.list_content(sender.corpus.id, sender.content_type, sender.content_selection_vars, function(data){
            if (data.meta && data.records) {
                $('#content-selection-modal-prev-page-button').prop('disabled', sender.content_selection_vars.page <= 1)
                $('#content-selection-modal-next-page-button').prop('disabled', !data.meta.has_next_page)

                $('#content-selection-modal-label').html(`Select ${sender.content_type}`)
                $('#content-selection-modal-table-header').html(sender.content_type)
                $('#content-selection-modal-table-body').empty()
                data.records.forEach(record => {
                    $('#content-selection-modal-table-body').append(`
                        <tr><td>
                          <a id="xref-item-${record.id}"
                              class="content-selection-item" href="#"
                              data-id="${record.id}"
                              data-uri="${record.uri}"
                              data-label="${record.label}">
                            ${record.label}
                          </a>
                        </td></tr>
                    `)
                })

                $(`.content-selection-item`).click(function() {
                    let clicked_content = $(this)
                    sender.id_element.val(clicked_content.data('id'))
                    sender.label_element.val(clicked_content.data('label'))
                    sender.content_selection_modal.modal('hide')
                    if (sender.previous_modal) sender.previous_modal.modal()
                })
            }
        })
    }

    rig_up_events() {
        let sender = this

        this.content_selection_modal = $('#content-selection-modal')
        this.content_selection_modal.on('shown.bs.modal', function(e) {
          filter_box.val('')
          filter_box.focus()
        })

        let filter_box = $('#content-selection-modal-filter-box')
        filter_box.off('keyup').on('keyup', function(e) {
            let query = filter_box.val()
            query = query.replaceAll("'", ' ')
            sender.content_selection_vars.q = query + '*'
            sender.content_selection_vars['t_label'] = `${query}`
            sender.content_selection_vars['operator'] = 'or'
            sender.content_selection_vars.page = 1
            delete sender.content_selection_vars['s_label']

            let key = e.which
            if (key === 13) {
                sender.load_content_selection()
            } else {
                clearTimeout(sender.content_search_timer)
                sender.content_search_timer = setTimeout(function() {
                    sender.load_content_selection()
                }, 500)
            }
        })

        // previous select content page click event
        $('#content-selection-modal-prev-page-button').off('click').on('click', function() {
            sender.content_selection_vars.page -= 1
            sender.load_content_selection()
        })

        // next select content page click event
        $('#content-selection-modal-next-page-button').off('click').on('click', function() {
            sender.content_selection_vars.page += 1
            sender.load_content_selection()
        })

        // SETUP CONTENT CREATE NEW BUTTON
        let new_button = $('#content-create-new-button')
        new_button.off('click').on('click', function() {
            let left = (screen.width / 2)
            let top = (screen.height / 2)
            let options = `top=${top},left=${left},popup=true`
            let creation_url = `/corpus/${sender.corpus.id}/${sender.content_type}/?popup=y`
            return window.open(creation_url, '_blank', options)
        })
    }

    select() {
        $('#content-selection-id-element-id').val(this.id_element_id)
        $('#content-selection-label-element-id').val(this.label_element_id)
        this.rig_up_events()
        this.load_content_selection()
        if (this.previous_modal) this.previous_modal.modal('hide')
        this.content_selection_modal.modal()
    }
}


class JobManager {
    constructor(config={}) {
        this.jobs_container = 'jobs_container' in config ? config.jobs_container : null
        this.provenance_container = 'provenance_container' in config ? config.provenance_container : null
        this.provenance = 'provenance' in config ? config.provenance : []
        this.corpora = 'corpora' in config ? config.corpora : null
        this.corpus = 'corpus' in config ? config.corpus : null
        this.content_type = 'content_type' in config ? config.content_type : null
        this.content_id = 'content_id' in config ? config.content_id : null
        this.scholar_id = 'scholar_id' in config ? config.scholar_id : null
        this.custom_parameter_types = 'custom_parameter_types' in config ? config.custom_parameter_types : {}
        this.scholar = null
        this.jobsites = []
        this.job_modal = $('#job-modal')
        this.report_modal = $('#job-report-modal')
        this.job_report_timer = null

        let sender = this

        // get info about this scholar's relationship to the corpus.
        this.corpora.get_scholar(this.scholar_id, function(scholar) {
            sender.scholar = scholar
            sender.scholar.role = 'Viewer'
            if (sender.corpus.id in sender.scholar.available_corpora)
                sender.scholar.role = sender.scholar.available_corpora[sender.corpus.id]['role']

            // we only proceed setting things up if they are an admin or an editor
            if (['Admin', 'Editor'].includes(sender.scholar.role)) {
                // setup the job queue viewer
                if (sender.jobs_container) {
                    sender.jobs_container = $(`#${sender.jobs_container}`)
                    sender.corpora.get_jobs(sender.corpus.id, sender.content_type, sender.content_id, {}, function(jobs) {
                        if (jobs.records.length) {
                            jobs.records.forEach(job => {
                                sender.register_job(
                                    job.id,
                                    job.task_name,
                                    job.status,
                                    job.configuration.parameters ? job.configuration.parameters : null,
                                    job.report_path,
                                    job.submitted_time,
                                    null,
                                    job.percent_complete
                                )
                            })
                        } else {
                            sender.report_no_jobs()
                        }
                    })

                    // start listening to job events
                    sender.corpus.events.addEventListener('job', function (e) {
                        sender.update_job(JSON.parse(e.data))
                    }, false)

                    // load provenance if provided
                    if (sender.provenance_container) {
                        sender.provenance_container = $(`#${sender.provenance_container}`)
                        if (sender.provenance.length) {
                            sender.provenance.forEach(prov => sender.register_job(
                                prov.job_id,
                                prov.task_name,
                                prov.status,
                                prov.task_configuration.parameters ? prov.task_configuration.parameters : null,
                                prov.report_path,
                                prov.submitted,
                                prov.completed,
                                null
                            ))
                        } else {
                            sender.report_no_jobs(true)
                        }

                        $('body').on('click', '.job-retry-button', function() {
                            let retry_button = $(this)
                            sender.corpora.retry_job(
                                sender.corpus.id,
                                retry_button.data('content-type'),
                                retry_button.data('content-id'),
                                retry_button.data('job-id'),
                                function(data) {
                                    $(`#provenance-${retry_button.data('job-id')}-div`).remove()
                                    if ($('.provenance-container').length === 0) {
                                        sender.report_no_jobs(true)
                                    }
                                }
                            )
                        })
                    }

                    $('body').on('click', '.job-report-button', function() {
                        sender.view_job_report($(this).data('job-id'))
                    })
                }
            }

            // we now have a scholar with "available" (in terms of permission to use) jobsites and tasks specified.
            // despite having permissions to run a given task on a jobsite, let's make sure these jobsites and tasks
            // exist so we can present them as potential jobs to enqueue
            sender.corpora.get_jobsites(function (jobsites) {
                let jobsite_selector_options = ''
                jobsites.forEach(js => { if (sender.scholar.available_jobsites.includes(js.id)) {
                    sender.jobsites.push(js)
                    if (js.name === 'Local') {
                        sender.local_jobsite_id = js.id
                    }
                    jobsite_selector_options += `
                        <option value="${js.id}" class="${js.type}" ${js.name === 'Local' ? 'selected' : ''}>
                            ${js.name}
                        </option>
                    `
                }})

                // now that we have jobsites that both exist and are available to the scholar, let's do the same for
                // tasks. the task API endpoint already filters tasks by permissions
                sender.corpora.get_tasks(null, function(tasks) {
                    tasks.forEach(task => {
                        for (let js_index = 0; js_index < sender.jobsites.length; js_index ++) {
                            if (task.name in sender.jobsites[js_index].task_registry) {
                                sender.jobsites[js_index].task_registry[task.name] = task
                            }
                        }
                    })

                    // now that we have a filtered list of jobsites and tasks, let's build the UI for launching and
                    // monitoring jobs
                    if (!sender.job_modal.length) {
                        $('body').prepend(`
                            <div class="modal fade" id="job-modal" tabindex="-1" role="dialog" aria-labelledby="job-modal-label" aria-hidden="true">
                                <div class="modal-dialog" role="document">
                                    <div class="modal-content">
                                            <input type="hidden" id="job-content-type">
                                            <input type="hidden" id="job-content-id">
                                            <div class="modal-header">
                                                <h5 class="modal-title" id="job-modal-label">Run a Job</h5>
                                                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                                <span aria-hidden="true">&times;</span>
                                                </button>
                                            </div>
                                            <div class="modal-body">
                                                <div class="form-group">
                                                    <label for="jobsite-selector">Jobsite</label>
                                                    <select id="jobsite-selector" class="form-control" name="jobsite">
                                                        ${jobsite_selector_options}
                                                    </select>
                                                </div>
                                                <div id="task-selector-div" class="form-group">
                                                    <label for="task-selector">Task</label>
                                                    <select id="task-selector" class="form-control" name="task">
                                                    </select>
                                                </div>
                                                <div id="task-parameters-div">
                                                </div>
                                            </div>
                                            <div class="modal-footer">
                                                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                                                <button type="button" class="btn btn-primary" id="job-submit-button" disabled>Run</button>
                                            </div>
                                    </div>
                                </div>
                            </div>
                        `)
                        sender.job_modal = $('#job-modal')

                        $('#jobsite-selector').change(function() {
                            sender.load_tasks()
                        })

                        $('#task-selector').change(function() {
                            let task_id = $('#task-selector').val()
                            let jobsite_id = $('#jobsite-selector').val()

                            sender.jobsites.forEach(jobsite => {
                                if (jobsite.id === jobsite_id) {
                                    for (let task_name in jobsite.task_registry) {
                                        let task = jobsite.task_registry[task_name]
                                        if (task.id === task_id) {
                                            sender.load_task_parameters(task)
                                        }
                                    }
                                }
                            })
                        })

                        $('#job-submit-button').click(function () {
                            let job_submission = {
                                jobsite_id: $('#jobsite-selector').val(),
                                task_id: $('#task-selector').val(),
                                content_type: $('#job-content-type').val(),
                                content_id: $('#job-content-id').val() ? $('#job-content-id').val() : null,
                                parameters: {}
                            }

                            $('.job-parameter-value').each(function() {
                                let param = $(this)
                                job_submission['parameters'][param.attr('name')] = param.val()
                            })

                            sender.corpora.submit_jobs(sender.corpus.id, [job_submission], function() {
                                sender.job_modal.modal('hide')
                            })
                        })


                    }

                    if (!sender.report_modal.length) {
                        $('body').prepend(`
                            <div class="modal fade" id="job-report-modal" tabindex="-1" role="dialog" aria-labelledby="job-report-modal-label" aria-hidden="true">
                                <div class="modal-dialog modal-lg" role="document">
                                    <div class="modal-content">
                                        <div class="modal-header">
                                            <h5 class="modal-title">Job Report</h5>
                                            <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                            <span aria-hidden="true">&times;</span>
                                            </button>
                                        </div>
                                        <div class="modal-body">
                                            <pre id="job-report-div">Loading...</pre>
                                        </div>
                                        <div class="modal-footer">
                                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `)
                        sender.report_modal = $('#job-report-modal')
                    }
                })
            })
        })
    }

    load_tasks(content_type=null) {
        let jobsite_selector = $('#jobsite-selector')
        let task_selector = $('#task-selector')
        task_selector.empty()

        let first = true
        this.jobsites.forEach(jobsite => {
            if (jobsite.id === jobsite_selector.val()) {
                for (let task_name in jobsite.task_registry) {
                    let task = jobsite.task_registry[task_name]
                    if ((!content_type || content_type === task.content_type) && task.track_provenance)
                    {
                        task_selector.append(`
                            <option class="job-task" value="${task.id}">
                                ${task.name}
                            </option>
                        `)
                        if (first) {
                            this.load_task_parameters(task)
                            first = false
                        }
                    }
                }
            }
        })

        if ($('option.job-task').length) {
            $(`#task-selector-div`).removeClass("d-none")
            $(`#job-submit-button`).attr('disabled', false)
        } else {
            $(`#task-selector-div`).addClass("d-none")
            $(`#job-submit-button`).attr('disabled', true)
        }
    }

    load_task_parameters(task) {
        let task_parameters_div = $('#task-parameters-div')
        let parameters = task['configuration']['parameters']

        task_parameters_div.empty()

        for (let parameter in parameters) {
            let parameter_html = ''

            if (parameters[parameter].hasOwnProperty('type')) {
                if (parameters[parameter].type in this.custom_parameter_types) {
                    parameter_html = this.custom_parameter_types[parameters[parameter].type](parameter, parameters[parameter])
                } else {
                    let note_html = ''
                    if (parameters[parameter].hasOwnProperty('note')) {
                        note_html = `<span class='text-muted'>${parameters[parameter]['note']}</span>`
                    }

                    if (parameters[parameter]['type'] === 'corpus_file') {
                        let select_options = ''
                        Object.keys(this.corpus.files).forEach(file_key => {
                            select_options += `<option value="${file_key}">${this.corpus.files[file_key].basename}</option>`
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-file-selector">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-file-selector" class="form-control job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'corpus_repo') {
                        let select_options = ''
                        Object.keys(this.corpus.repos).forEach(repo_name => {
                            select_options += `<option value="${repo_name}">${repo_name}</option>`
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-repo-selector">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-repo-selector" class="form-control job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'content_type') {
                        let select_options = ''
                        Object.keys(this.corpus.content_types).forEach(ct => {
                            select_options += `<option value="${ct}">${this.corpus.content_types[ct].name}</option>`
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-ct-selector">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-ct-selector" class="form-control job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'content_type_field') {
                        let select_options = ''
                        Object.keys(this.corpus.content_types).forEach(ct => {
                            this.corpus.content_types[ct].fields.map(f => {
                                select_options += `<option value="${ct}->${f.name}">${ct} -> ${f.label}</option>`
                            })
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-ct-field-selector">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-ct-field-selector" class="form-control job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'xref') {
                        parameter_html = `
                          <div class="form-group">
                            <label for="${parameter}-content-label">${parameters[parameter]['label']}</label>
                            <input id="${parameter}-content-label" type="text" readonly>
                            <button id="${parameter}-selection-button" class="btn btn-secondary">Select</button>
                            <input type="hidden" id="${parameter}-content-id" class="job-parameter-value" name="${parameter}">
                          </div>
                        `
                    } else if (parameters[parameter]['type'] === 'boolean') {
                        let checked = parameters[parameter]['value'] ? 'checked' : ''

                        parameter_html = `
                            <div class="form-check">
                                <input id="${parameter}-boolean-checkbox" type="checkbox" class="form-check-input job-parameter-value" name="${parameter}" ${checked}>
                                <label for="${parameter}-boolean-checkbox" class="form-check-label">${parameters[parameter]['label']}</label>
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'choice' && parameters[parameter].hasOwnProperty('choices')) {
                        let select_options = ''
                        parameters[parameter]['choices'].forEach(choice => {
                            select_options += `<option>${choice}</option>\n`
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-choice-selector">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-choice-selector" class="form-control job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'pep8_text') {
                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-pep8-text-box">${parameters[parameter]['label']}</label>
                                <input id="${parameter}-pep8-text-box" type="text" class="form-control job-parameter-value" name="${parameter}" />
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'text') {
                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-text-box">${parameters[parameter]['label']}</label>
                                <input id="${parameter}-text-box" type="text" class="form-control job-parameter-value" name="${parameter}" />
                                ${note_html}
                            </div>
                        `
                    }
                }

                task_parameters_div.append(parameter_html)

                if (parameters[parameter]['type'] === 'pep8_text') {
                    let pep8_box = $(`#${parameter}-pep8-text-box`)
                    pep8_box.focusout(function () {
                        pep8_box.val(pep8_variable_format(pep8_box.val()))
                    })
                } else if (parameters[parameter]['type'] === 'xref') {
                    let selector = new ContentSelector({
                        id_element: $(`#${parameter}-content-id`),
                        label_element: $(`#${parameter}-content-label`),
                        previous_modal: this.job_modal,
                        corpora: corpora,
                        corpus: corpus,
                        content_type: parameters[parameter].content_type
                    })

                    $(`#${parameter}-selection-button`).click(function() {
                        selector.select()
                    })
                }
            }
        }
    }

    view_job_report(job_id) {
        $('#job-report-modal').modal()
        $('#job-report-modal').on('hidden.bs.modal', function (e) {
            clearTimeout(this.job_report_timer)
        })
        this.load_job_report(job_id)
    }

    load_job_report(job_id) {
        let no_cache_string = Math.random().toString(36).substring(7)
        let report_url = `/corpus/${this.corpus.id}/get-file/?path=job_reports/${job_id}.txt&no-cache=${no_cache_string}`
        let report_div = $('#job-report-div')
        let sender = this

        report_div.load(report_url, function() {
            report_div.scrollTop(report_div[0].scrollHeight)

            if (!report_div.html().includes('CORPORA JOB COMPLETE')) {
                sender.job_report_timer = setTimeout(() => { sender.load_job_report(job_id) }, 10000)
            }
        })
    }

    new_job(content_type, content_id) {
        this.load_tasks(content_type)
        if (content_type) $('#job-content-type').val(content_type)
        if (content_id) $('#job-content-id').val(content_id)
        this.job_modal.modal()
    }

    update_job(info) {
        let job_progress = $(`#job-${info.job_id}-progress`)
        if (job_progress.length) {
            job_progress.css("width", `${info.percent_complete}%`)
            job_progress.attr("aria-valuenow", info.percent_complete)
            job_progress.html(`${info.percent_complete}%`)

            if (info.status !== "running") {
                let stale_job_div = $(`#job-${info.job_id}-container`)
                if (stale_job_div.length) {
                    let sender = this
                    if (this.content_type === 'Corpus') {
                        this.corpora.get_corpus(this.corpus.id, function(data) {
                            if (data && data.provenance) {
                                data.provenance.forEach(prov => {
                                    if (prov.job_id === info.job_id) sender.register_job(
                                        prov.job_id,
                                        prov.task_name,
                                        prov.status,
                                        prov.task_configuration.parameters ? prov.task_configuration.parameters : null,
                                        prov.report_path,
                                        prov.submitted,
                                        prov.completed,
                                        null
                                    )
                                })
                            }
                        })
                    } else {
                        this.corpora.get_content(this.corpus.id, this.content_type, this.content_id, function (data) {
                            if (data && data.provenance) {
                                data.provenance.forEach(prov => {
                                    if (prov.job_id === info.job_id) sender.register_job(
                                        prov.job_id,
                                        prov.task_name,
                                        prov.status,
                                        prov.task_configuration.parameters ? prov.task_configuration.parameters : null,
                                        prov.report_path,
                                        prov.submitted,
                                        prov.completed,
                                        null
                                    )
                                })
                            }
                        })
                    }
                    stale_job_div.remove()

                    if ($('.job-container').length === 0) {
                        this.report_no_jobs()
                    }

                    let loc = window.location
                    let alert = $(`
                        <div class="alert alert-${info.status === "complete" ? 'success' : 'danger'}"
                            style="width: 95%; float: left; margin: 0px;">
                          Task <b>${info.task_name}</b> has completed ${info.status === "complete" ? 'successfully' : 'with errors'}.
                          You may wish to 
                          <button type="button"
                              class="btn btn-link"
                              onclick="window.location.replace('${loc.protocol}//${loc.host}${loc.pathname}')"
                              style="padding: 0px; vertical-align: unset;">
                            refresh the page
                          </button>
                          to view the results.
                        </div>
                    `)
                    Toastify({
                        node: alert[0],
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
        } else {
            let sender = this
            this.corpora.get_job(this.corpus.id, info.job_id, function (job) {
                sender.register_job(
                    job.id,
                    job.task_name,
                    job.status,
                    job.configuration.parameters ? job.configuration.parameters : null,
                    job.report_path,
                    job.submitted_time,
                    null,
                    job.percent_complete
                )
            })
        }
    }

    register_job(job_id, task_name, status, parameters, report_path, submitted, completed, percent_complete) {
        let container = this.jobs_container
        let report_button = ''
        let retry_button = ''
        let param_tray = ''
        let progress_bar = ''
        let container_class = 'job-container'
        let alert_class = 'success'

        if (['complete', 'error'].includes(status)) {
            container = this.provenance_container
            container_class = 'provenance-container'

            if (status === 'error') alert_class = 'danger'
        }

        if (container) {
            if ($(`.${container_class}`).length === 0) container.empty()

            if (['Admin', 'Editor'].includes(this.scholar.role)) {
                if (report_path) {
                    report_button = `
                        <button type="button" class="btn btn-sm btn-primary mr-1 mb-1 job-report-button" data-job-id="${job_id}">View Report</button>
                    `
                }

                if (['complete', 'error'].includes(status)) {
                    retry_button = `
                        <button
                          type="button"
                          role="button"
                          class="btn btn-sm btn-danger mr-1 mb-1 job-retry-button"
                          data-job-id="${job_id}"
                          data-content-type="${this.content_type}"
                          data-content-id="${this.content_id}"
                        >Retry</button>
                    `
                }

                if (parameters) {
                    let param_list = []
                    for (let param in parameters) {
                        param_list.push(`<b>${parameters[param].label}</b><br /> ${parameters[param].value}`)
                    }
                    param_tray = `
                        <a class="btn btn-sm btn-primary mt-1"
                           data-toggle="collapse"
                           href="#job-${job_id}-parameters"
                           role="button"
                           aria-expanded="false"
                           aria-controls="job-${job_id}-parameters">
                            Show Parameters
                        </a>
                        <div class="collapse mt-1" id="job-${job_id}-parameters">
                            <div class="card card-body" style="display: block;">
                                ${param_list.join('<br /><br />')}
                            </div>
                        </div>
                    `
                }

                if (percent_complete || percent_complete === 0) {
                    progress_bar = `
                        <div class="row">
                            <div class="col-sm-12">
                                <div id="job-${job_id}-progress"
                                    class="progress-bar progress-bar-striped bg-success progress-bar-animated mb-1"
                                    role="progressbar"
                                    aria-valuenow="${percent_complete}"
                                    aria-valuemin="0"
                                    aria-valuemax="100"
                                    style="width: ${percent_complete}%; height: 10px;">  
                                  ${percent_complete}%
                                </div>    
                            </div>
                        </div>
                    `
                }
            }

            container.prepend(`
                <div id="job-${job_id}-container" class="alert alert-${alert_class} ${container_class}">
                    ${progress_bar}
                    <div class="row">
                        <div class="col-sm-12 d-flex justify-content-between">
                            <span>
                                Task: <b>${task_name}</b><br />
                                Submitted: ${this.corpora.time_string(submitted)}<br />
                                ${completed ? `Completed: ${this.corpora.time_string(completed)}<br />` : ''}
                                ${param_tray}
                            </span>
                            <span class="text-right">
                                ${report_button}
                                ${retry_button}
                            </span>
                        </div>
                    </div>
                </div>
            `)
        }
    }

    report_no_jobs(completed=false) {
        let container = this.jobs_container
        let message_suffix = `jobs running for this ${this.content_type}`
        if (completed) {
            container = this.provenance_container
            message_suffix = `completed jobs for this ${this.content_type}`
        }
        container.html(`
            <div class="alert alert-info">
                There are currently no ${message_suffix}.
            </div>
        `)
    }
}