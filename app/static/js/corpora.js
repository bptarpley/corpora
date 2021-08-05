function pep8_variable_format(string) {
    const a = 'àáäâãåăæçèéëêǵḧìíïîḿńǹñòóöôœøṕŕßśșțùúüûǘẃẍÿź·/-,:;';
    const b = 'aaaaaaaaceeeeghiiiimnnnooooooprssstuuuuuwxyz______';
    const p = new RegExp(a.split('').join('|'), 'g');

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
        return word.replace(word[0], word[0].toUpperCase());
    }).join('');
}

function unescape(string) {
  return new DOMParser().parseFromString(string,'text/html').querySelector('html').textContent;
}

class Corpora {
    constructor(config={}) {
        this.host = 'host' in config ? config.host : "";
        this.auth_token = 'auth_token' in config ? config.auth_token : "";
        this.csrf_token = 'csrf_token' in config ? config.csrf_token : "";
    }

    make_request(path, type, params={}, callback, spool=false, spool_records = []) {
        let req = {
            type: type,
            url: `${this.host}${path}`,
            dataType: 'json',
            data: params,
            success: callback
        };

        if (path.startsWith('http')) {
            req.url = path;
        }

        if (spool) {
            let corpora_instance = this;
            req.success = function(data) {
                if (
                    data.hasOwnProperty('records') &&
                    data.hasOwnProperty('meta') &&
                    data.meta.hasOwnProperty('has_next_page') &&
                    data.meta.hasOwnProperty('page') &&
                    data.meta.hasOwnProperty('page_size') &&
                    data.meta.has_next_page
                ) {
                    let next_params = Object.assign({}, params);
                    next_params.page = data.meta.page + 1;
                    next_params['page-size'] = data.meta.page_size;

                    corpora_instance.make_request(
                        path,
                        type,
                        next_params,
                        callback,
                        spool,
                        spool_records.concat(data.records)
                    )
                } else {
                    data.records = spool_records.concat(data.records);
                    callback(data);
                }
            }
        }

        if (this.auth_token) {
            req['beforeSend'] = function(xhr) { xhr.setRequestHeader("Authorization", `Token ${sender.auth_token}`); }
        } else if (type === 'POST' && this.csrf_token) {
            req['data'] = Object.assign({}, req['data'], {'csrfmiddlewaretoken': this.csrf_token});
        }

        let sender = this;
        $.ajax(req);
    }

    get_scholars(search={}, callback) {
        this.make_request(
            "/api/scholar/",
            "GET",
            search,
            callback
        );
    }

    get_scholar(scholar_id, callback) {
        this.make_request(
            `/api/scholar/${scholar_id}/`,
            "GET",
            {},
            callback
        );
    }

    get_corpora(search={}, callback) {
        this.make_request(
            "/api/corpus/",
            "GET",
            search,
            callback
        );
    }

    get_corpus(id, callback, include_views=false) {
        let params = {};
        if (include_views) {
            params['include-views'] = true;
        }

        this.make_request(
            `/api/corpus/${id}/`,
            "GET",
            params,
            callback
        );
    }

    get_jobs(corpus_id=null, content_type=null, content_id=null, params={}, callback) {
        let url = '/api/jobs/';
        if (corpus_id) { url += `corpus/${corpus_id}/`; }
        if (corpus_id && content_type) { url += `${content_type}/`; }
        if (corpus_id && content_type && content_id) { url += `${content_id}`; }
        this.make_request(
            url,
            "GET",
            params,
            callback
        );
    }

    get_corpus_jobs(corpus_id, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/jobs/`,
            "GET",
            {},
            callback
        );
    }

    get_content_jobs(corpus_id, content_type, content_id, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/${content_type}/${content_id}/jobs/`,
            "GET",
            {},
            callback
        );
    }

    get_jobsites(callback) {
        this.make_request(
            `/api/jobsites/`,
            "GET",
            {},
            callback
        );
    }

    get_tasks(content_type=null, callback) {
        let url = '/api/tasks/';
        if (content_type) {
            url += `${content_type}/`
        }

        this.make_request(
            url,
            "GET",
            {},
            callback
        );
    }

    edit_content_types(corpus_id, schema, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/type/`,
            "POST",
            {
                schema: schema
            },
            callback
        );
    }

    get_content(corpus_id, content_type, content_id, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/${content_type}/${content_id}/`,
            "GET",
            {},
            callback
        );
    }

    list_content(corpus_id, content_type, search={}, callback, spool=false) {
        this.make_request(
            `/api/corpus/${corpus_id}/${content_type}/`,
            "GET",
            search,
            callback,
            spool
        );
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
        );
    }

    get_corpus_files(corpus_id, path, filter, callback) {
        let endpoint = `/api/corpus/${corpus_id}/files/`;

        this.make_request(
            endpoint,
            "GET",
            {
                path: path,
                filter: filter
            },
            callback
        );
    }

    make_corpus_file_dir(corpus_id, path, new_dir, callback) {
        let endpoint = `/api/corpus/${corpus_id}/files/`;

        this.make_request(
            endpoint,
            "POST",
            {
                path: path,
                newdir: new_dir
            },
            callback
        );
    }

    get_content_files(corpus_id, content_type, content_id, path, filter, callback) {
        let endpoint = `/api/corpus/${corpus_id}/${content_type}/files/`;
        if (content_id) {
            endpoint = endpoint.replace('/files/', `/${content_id}/files/`);
        }

        this.make_request(
            endpoint,
            "GET",
            {
                path: path,
                filter: filter
            },
            callback
        );
    }

    make_content_file_dir(corpus_id, content_type, content_id, path, new_dir, callback) {
        let endpoint = `/api/corpus/${corpus_id}/${content_type}/files/`;
        if (content_id) {
            endpoint = endpoint.replace('/files/', `/${content_id}/files/`);
        }

        this.make_request(
            endpoint,
            "POST",
            {
                path: path,
                newdir: new_dir
            },
            callback
        );
    }

    get_preference(content_type, content_uri, preference, callback) {
        this.make_request(
            `/api/scholar/preference/${content_type}/${preference}/`,
            "GET",
            {
                content_uri: content_uri
            },
            callback
        );
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

    file_url(uri) {
        return `/file/uri/${uri.split('/').join('|')}/`;
    }

    image_url(uri) {
        return `/image/uri/${uri.split('/').join('|')}/`;
    }

    time_string(timestamp) {
        let date = new Date(timestamp * 1000);
        return date.toLocaleString('en-US', { timeZone: 'UTC' });
    }

    date_string(timestamp) {
        let date = new Date(timestamp * 1000);
        return date.toISOString().split('T')[0];
    }
}

class ContentTable {
    constructor(config={}) {
        this.container_id = 'container_id' in config ? config.container_id : null;
        this.corpora = 'corpora' in config ? config.corpora : null;
        this.corpus = 'corpus' in config ? config.corpus : null;
        this.content_type = 'content_type' in config ? config.content_type : null;
        this.search = 'search' in config ? config.search : {
            'page': 1,
            'page-size': 5,
        };
        this.selected_content = {
            all: false,
            ids: []
        };

        if (this.container_id && this.corpora && this.corpus && this.content_type) {
            this.container = $(`#${this.container_id}`);

            // shortcut vars for quick access (and also to circumvent "this.x" issue in events)
            let corpora = this.corpora;
            let corpus_id = this.corpus.id;
            let corpus = this.corpus;
            let ct = this.corpus.content_types[this.content_type];
            let role = this.corpus.scholar_role;
            let search = this.search;
            let selected_content = this.selected_content;
            let sender = this;

            // ensure multiselection form and deletion confirmation modal exist
            if (!$('#multiselect-form').length) {
                this.container.append(`
                    <form id="multiselect-form" method="post" action="/not/set">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${this.corpora.csrf_token}">
                        <input id="multiselect-content-ids" name="content-ids" type="hidden" value="">
                    </form>
                `);
            }
            if (!$('#deletion-confirmation-modal').length) {
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
                `);
                // CONTENT DELETION BUTTON
                $('#deletion-confirmation-button').click(function() {
                    let multi_form = $('#multiselect-form');
                    multi_form.append(`
                        <input type='hidden' name='deletion-confirmed' value='y'/>
                    `);
                    multi_form.attr('action', corpus.uri + '/');
                    multi_form.submit();
                });
            }

            this.container.append(`
                <div class="row">
                    <div class="col-12">
                        <a name="${ct.plural_name}"></a>
                        <div class="card mt-4">
                            <div class="card-header" style="padding: 0 !important;">
                                <div class="d-flex w-100 justify-content-between align-items-center text-nowrap p-2 ml-2">
                                    <h4>${ct.plural_name}</h4>
                                    <div class="input-group ml-2 mr-2">
                                        <div class="input-group-prepend">
                                            <button id="ct-${ct.name}-search-type-selection" class="btn btn-primary dropdown-toggle" type="button" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">Text Search</button>
                                            <div id="ct-${ct.name}-search-type-menu" class="dropdown-menu">
                                                <span class="p-2">Select a specific field from the dropdown to the right in order to choose a different search type.</span>
                                            </div>
                                            <input type="hidden" id="ct-${ct.name}-search-type-value" value="default" />
                                        </div>
                                        <input type="text" class="form-control" id="ct-${ct.name}-search-box" placeholder="Search" />
                                        <div class="input-group-append">
                                            <button id="ct-${ct.name}-search-setting-selection" class="btn btn-primary dropdown-toggle" type="button" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">All Fields</button>
                                            <div id="ct-${ct.name}-search-settings-menu" class="dropdown-menu">
                                                <a class="dropdown-item ct-${ct.name}-search-setting" id="ct-${ct.name}-search-setting-default" href="#">All Fields</a>
                                            </div>
                                            <input type="hidden" id="ct-${ct.name}-search-setting-value" value="default" />
                                        </div>
                                    </div>

                                    <button id="ct-${ct.name}-search-clear-button" class="btn btn-primary rounded mr-2 d-none" type="button">Clear Search</button>
                                    ${ (role === 'Editor' || role === 'Admin') ? `<a role="button" id="ct-${ct.name}-new-button" href="/corpus/${corpus_id}/${ct.name}/" class="btn btn-primary rounded mr-2">New ${ct.name}</a>` : ''}

                                    <div class="form-inline mr-2">
                                        <select class="form-control btn-primary d-none" id="ct-${ct.name}-page-selector">
                                        </select>
                                    </div>

                                    <div class="form-inline mr-2">
                                        <select class="form-control btn-primary" id="ct-${ct.name}-per-page-selector">
                                            <option selected>5</option>
                                            <option>10</option>
                                            <option>20</option>
                                            <option>50</option>
                                        </select>
                                    </div>
                                </div>
                                <div id="ct-${ct.name}-current-search-div" class="d-flex w-100 align-items-center p-2 pl-3 badge-secondary" style="padding-top: 12px !important;"></div>
                            </div>
                            <div class="card-body">
                                <table class="table table-striped">
                                    <thead class="thead-dark">
                                        <tr id="ct-${ct.name}-table-header-row">
                                        </tr>
                                    </thead>
                                    <tbody id="ct-${ct.name}-table-body">
                                    </tbody>
                                </table>
                                <div class="form-inline">
                                    With selected:
                                    <select class="form-control-sm btn-primary ml-1 mr-1" id="ct-${ct.name}-selection-action-selector">
                                        <option value="explore" selected>Explore</option>
                                        <option value="merge">Merge</option>
                                        ${['Editor', 'Admin'].includes(role) ? '<option value="create_view">Create View</option>' : ''}
                                        ${['Editor', 'Admin'].includes(role) ? '<option value="delete">Delete</option>' : ''}
                                    </select>
                                    <button type="button" class="btn btn-sm btn-secondary" id="ct-${ct.name}-selection-action-go-button" disabled>Go</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `);

            // setup content type table headers
            let table_header_row = $(`#ct-${ct.name}-table-header-row`);
            table_header_row.append(`
                <th scope="col">
                    <input type="checkbox" id="ct_${ct.name}_select-all_box">
                </th>
            `);
            for (let x = 0; x < ct.fields.length; x++) {
                if (ct.fields[x].in_lists) {
                    table_header_row.append(`
                        <th scope="col">
                            <a href="#" class="${ct.name}-order-by" data-order-by="${ct.fields[x].type === 'cross_reference' ? ct.fields[x].name + '.label' : ct.fields[x].name}"><h5>${ct.fields[x].label}</h5></a>
                        </th>
                    `);
                }
            }

            // handle order by event
            $(`.${ct.name}-order-by`).click(function(e) {
                e.preventDefault();
                sender.order_by($(this).data('order-by'));
            });

            // handle select all box checking/unchecking
            $(`#ct_${ct.name}_select-all_box`).change(function() {
                let id_parts = this.id.split('_');
                let ct_name = id_parts[1];
                let go_button = $(`#ct-${ct_name}-selection-action-go-button`);

                if ($(this).is(':checked')) {
                    selected_content.all = true;
                    selected_content.ids = [];

                    $(`.ct-${ct_name}-selection-box`).each(function() {
                        $(this).prop("checked", true);
                        $(this).attr("disabled", true);
                    });

                    go_button.removeAttr('disabled');
                } else {
                    selected_content.all = false;
                    $(`.ct-${ct_name}-selection-box`).each(function() {
                        $(this).prop("checked", false);
                        $(this).removeAttr("disabled");
                    });

                    go_button.attr('disabled', true);
                }
            });

            // setup content type search fields
            let search_settings_menu = $(`#ct-${ct.name}-search-settings-menu`);
            for (let x = 0; x < ct.fields.length; x++) {
                if (ct.fields[x].in_lists) {
                    search_settings_menu.append(`
                        <a class="dropdown-item ct-${ct.name}-search-setting" id="ct-${ct.name}-search-setting-${ct.fields[x].type === 'cross_reference' ? ct.fields[x].name + '.label' : ct.fields[x].name}" href="#">${ct.fields[x].label}</a>
                    `);

                    // add cross reference sub field options
                    if (ct.fields[x].type === 'cross_reference') {
                        if (corpus.content_types.hasOwnProperty(ct.fields[x].cross_reference_type)) {
                            let cx = corpus.content_types[ct.fields[x].cross_reference_type];
                            for (let y = 0; y < cx.fields.length; y++) {
                                if (cx.fields[y].in_lists && cx.fields[y].type !== 'cross_reference') {
                                    search_settings_menu.append(`
                                        <a class="dropdown-item ct-${ct.name}-search-setting" id="ct-${ct.name}-search-setting-${ct.fields[x].name + '.' + cx.fields[y].name}" href="#">${ct.fields[x].label} -> ${cx.fields[y].label}</a>
                                    `);
                                }
                            }
                        }
                    }
                }
            }

            // event for selecting a specific field to search
            $(`.ct-${ct.name}-search-setting`).click(function (event) {
                event.preventDefault();
                let field = event.target.id.replace(`ct-${ct.name}-search-setting-`, '');
                let label = $(this).text();
                let search_type_menu = $(`#ct-${ct.name}-search-type-menu`);

                if (field === 'default') {
                    search_type_menu.html(`
                        <span class="p-2">Select a specific field from the dropdown to the right in order to choose a different search type.</span>
                    `);
                } else {
                    search_type_menu.html(`
                        <a class="dropdown-item ct-${ct.name}-search-type" id="ct-${ct.name}-search-type-default" href="#">Text Search</a>
                        <a class="dropdown-item ct-${ct.name}-search-type" id="ct-${ct.name}-search-type-exact" href="#">Exact Search</a>
                        <a class="dropdown-item ct-${ct.name}-search-type" id="ct-${ct.name}-search-type-term" href="#">Term Search</a>
                        <a class="dropdown-item ct-${ct.name}-search-type" id="ct-${ct.name}-search-type-phrase" href="#">Phrase Search</a>
                        <a class="dropdown-item ct-${ct.name}-search-type" id="ct-${ct.name}-search-type-wildcard" href="#">Wildcard Search</a>
                        <a class="dropdown-item ct-${ct.name}-search-type" id="ct-${ct.name}-search-type-range" href="#">Range Search</a>
                    `);
                }

                // event for selecting a search type
                $(`.ct-${ct.name}-search-type`).click(function (event) {
                    event.preventDefault();
                    let search_type = event.target.id.replace(`ct-${ct.name}-search-type-`, '');
                    let label = $(this).text();

                    $(`#ct-${ct.name}-search-type-selection`).text(label);
                    $(`#ct-${ct.name}-search-type-value`).val(search_type);
                });

                $(`#ct-${ct.name}-search-setting-selection`).text(label);
                $(`#ct-${ct.name}-search-setting-value`).val(field);
            });

            // setup page selector events
            $(`#ct-${ct.name}-page-selector`).on("change", function () {
                search.page = parseInt($(`#ct-${ct.name}-page-selector`).val());
                corpora.list_content(corpus_id, ct.name, search, function(content){ sender.load_content(content); });
            });

            $(`#ct-${ct.name}-per-page-selector`).on("change", function () {
                search['page-size'] = parseInt($(`#ct-${ct.name}-per-page-selector`).val());
                search['page'] = 1;
                corpora.list_content(corpus_id, ct.name, search, function(content){ sender.load_content(content); });
            });

            // setup search events
            $(`#ct-${ct.name}-search-box`).keypress(function (e) {
                let key = e.which;
                if (key === 13) {
                    let query = $(`#ct-${ct.name}-search-box`).val();
                    let field = $(`#ct-${ct.name}-search-setting-value`).val();
                    let search_type = $(`#ct-${ct.name}-search-type-value`).val();
                    let search_type_map = {
                        default: 'q',
                        exact: 'f',
                        term: 't',
                        phrase: 'p',
                        wildcard: 'w',
                        range: 'r',
                    };

                    if (field === 'default') {
                        search.q = query;
                    } else {
                        let param_prefix = search_type_map[search_type];
                        search[`${param_prefix}_${field}`] = query;
                    }

                    $(`#ct-${ct.name}-search-clear-button`).removeClass('d-none');
                    corpora.list_content(corpus_id, ct.name, search, function(content){ sender.load_content(content); });
                }
            });

            $(`#ct-${ct.name}-search-clear-button`).click(function (event) {
                $(`#ct-${ct.name}-search-box`).val('');
                for (let param in search) {
                    if (search.hasOwnProperty(param)) {
                        if (param === 'q' || ['q_', 'f_', 't_', 'p_', 'w_', 'r_'].includes(param.slice(0, 2))) {
                            delete search[param];
                        }
                    }
                }
                search.page = 1;
                $(`#ct-${ct.name}-search-setting-selection`).text("All Fields");
                $(`#ct-${ct.name}-search-setting-value`).val('default');

                corpora.list_content(corpus_id, ct.name, search, sender.load_content);
            });

            $(`#ct-${ct.name}-selection-action-go-button`).click(function() {
                let id_parts = this.id.split('-');
                let ct_name = id_parts[1];
                let action = $(`#ct-${ct.name}-selection-action-selector`).val();
                let multi_form = $('#multiselect-form');
                $('#multiselect-content-ids').val(selected_content.ids.join(','));

                if (action === 'explore') {
                    multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/explore/`);
                    multi_form.submit();
                } else if (action === 'merge') {
                    multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/merge/`);
                    multi_form.submit();
                } else if (action === 'create_view') {
                    let steps_counter = 0;
                    let ct_options = '';
                    for (let ct_name in corpus.content_types) {
                        ct_options += `<option value="${ct_name}">${corpus.content_types[ct_name].plural_name}</option>\n`;
                    }
                    $('#exploration-start-ct').html(ct_options);
                    $('#exploration-end-ct').html(ct_options);
                    $('#exploration-end-ct').val(ct_name);

                    $('#exploration-end-uris').prop('checked', true);
                    $('#exploration-end-uris-div').html('');

                    selected_content.ids.map(id => {
                        let exp_uri = `/corpus/${corpus_id}/${ct_name}/${id}`;
                        $('#exploration-end-uris-div').append(`
                            <iframe class="exploration-uri" src="${exp_uri}/?popup=y" frameborder="0" width="200px" height="200px" data-uri="${exp_uri}"></iframe>
                        `);
                    });

                    $('#exploration-steps-div').html('');
                    $('#exploration-steps-add-button').off('click').on('click', function() {
                        $('#exploration-steps-div').append(`
                            <div id="exploration-step-${steps_counter}">
                                <select class="exploration-step form-control-sm btn-primary">${ct_options}</select>
                                <button id="exploration-step-${steps_counter}-remove-button" role="button" class="btn btn-sm btn-primary">-</button>
                            </div>
                        `);
                        $(`#exploration-step-${steps_counter}-remove-button`).click(function() {
                            $(`#exploration-step-${steps_counter}`).remove();
                        });
                    });

                    $('#find-connected-modal').modal();
                } else if (action === 'delete') {
                    $('#deletion-confirmation-modal-message').html(`
                        Are you sure you want to delete the selected ${corpus.content_types[ct_name].plural_name}?
                    `);
                    multi_form.append(`
                        <input type='hidden' name='content-type' value='${ct_name}'/>
                    `);
                    $('#deletion-confirmation-modal').modal();
                } else {
                    multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/bulk-job-manager/`);
                    multi_form.append(`
                        <input type='hidden' name='task-id' value='${action}'/>
                    `);
                    if (selected_content.all) {
                        multi_form.append(`<input id='multiselect-content-query' type='hidden' name='content-query'>`);
                        $('#multiselect-content-query').val(JSON.stringify(search));
                    }
                    multi_form.submit();
                }
            });

            // perform initial query of content based on search settings
            corpora.list_content(corpus_id, ct.name, search, function(content){ sender.load_content(content); });

            // populate content targeted tasks
            corpora.get_tasks(ct.name, function(tasks_data) {
                if (tasks_data.length > 0) {
                    let task_selection_html = '<optgroup label="Launch Job">';
                    tasks_data.map(task => {
                        if (role === 'Admin' || available_tasks.includes(_id(task))) {
                            task_selection_html += `<option value="${_id(task)}">${task.name}</option>`;
                        }
                    });
                    task_selection_html += '</optgroup>';
                    $(`#ct-${ct.name}-selection-action-selector`).append(task_selection_html);
                }
            });
        }
    }
    
    load_content(content) {
        let corpora = this.corpora;
        let corpus = this.corpus;
        let ct = corpus.content_types[content.meta.content_type];
        let search = this.search;
        let selected_content = this.selected_content;
        let sender = this;

        // instantiate some variables to keep track of elements
        let ct_table_body = $(`#ct-${ct.name}-table-body`); // <-- the table body for listing results
        let page_selector = $(`#ct-${ct.name}-page-selector`); // <-- the page select box
        let per_page_selector = $(`#ct-${ct.name}-per-page-selector`); // <-- the page size select box
        let current_search_div = $(`#ct-${ct.name}-current-search-div`); // <-- the search criteria div

        // clear the table body, page selector, and search criteria div
        ct_table_body.html('');
        page_selector.html('');
        current_search_div.html('');

        // add the total number of results to the search criteria div
        current_search_div.append(`
            <span id="ct-${ct.name}-total-badge" class="badge badge-primary p-2 mr-2" data-total="${content.meta.total}" style="font-size: 12px;">
                Total: ${content.meta.total.toLocaleString('en-US')}
            </span>
        `);

        // add existing search criteria to the div
        let has_filtering_criteria = false;
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
                };
                let setting_type = setting_type_map[search_setting.slice(0, 1)];
                let field = "";
                let field_name = "";
                let search_value = `${search[search_setting]}`;

                if (search_setting !== 'q') {
                    field = search_setting.substring(2);
                    let subfield = "";
                    if (field.includes('.')) {
                        let field_parts = field.split('.');
                        field = field_parts[0];
                        subfield = field_parts[1];
                    }

                    for (let x = 0; x < ct.fields.length; x++) {
                        if (ct.fields[x].name === field) {
                            field_name = ct.fields[x].label;

                            if (subfield !== "" && ct.fields[x].type === 'cross_reference' && corpus.content_types.hasOwnProperty(ct.fields[x].cross_reference_type)) {
                                let cx = corpus.content_types[ct.fields[x].cross_reference_type];
                                for (let y = 0; y < cx.fields.length; y++) {
                                    if (cx.fields[y].name === subfield) {
                                        field_name += " -> " + cx.fields[y].label;
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
                        <a class="text-white ${ct.name}-remove-search-param" data-search-param="${search_setting}"><i class="far fa-times-circle"></i></a>
                    </span>
                `);
            }
        }

        // setup view selector if views for this ct exist
        if (corpus.hasOwnProperty('views')) {
            let ct_views = [];
            corpus.views.map(view => {
                if (view.primary_ct === ct.name) {
                    ct_views.push(`
                        <option value="${view.name}">${view.label}</option>
                    `);
                }
            });
            if (ct_views.length) {
                current_search_div.append(`
                    <div class="form-inline ml-auto">
                        <select id="${ct.name}-view-selector" class="form-control form-control-sm btn-primary">
                            <option value="NONE">Default View</option>
                            ${ct_views.join('\n')}
                        </select>
                    </div>
                `);
                let view_selector = $(`#${ct.name}-view-selector`);
                if (search.hasOwnProperty('exploration')) {
                    view_selector.val(search.exploration);
                }
                view_selector.change(function() {
                    if (view_selector.val() === 'NONE') {
                        sender.remove_search_param('exploration');
                    } else {
                        search['exploration'] = view_selector.val();
                        corpora.list_content(corpus_id, ct.name, search, function(content){ sender.load_content(content); });
                    }
                });
            }
        }

        // remove search param event
        $(`.${ct.name}-remove-search-param`).click(function() {
            sender.remove_search_param($(this).data('search-param'));
        });

        // if there are no search results, show a default message
        if (content.records.length < 1) {
            let no_records_msg = `There are currently no ${ct.plural_name} in this corpus. Click the "New ${ct.name}" button above to create one.`;
            if (has_filtering_criteria) {
                no_records_msg = `No ${ct.plural_name} in this corpus match your search criteria.`;
            }

            let num_cols = 1;
            for (let x = 0; x < ct.fields.length; x++) {
                if (ct.fields[x].in_lists) {
                    num_cols += 1;
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
            `;
            ct_table_body.append(row_html);

            page_selector.addClass("d-none");
            per_page_selector.addClass("d-none");

        // records exist, so populate the content type table with a page of results
        } else {
            // setup the page selector based on total # of pages within 50 page range
            let min_page = content.meta.page - 50;
            let max_page = content.meta.page + 50;
            let first_pg_msg = '';
            let last_pg_msg = '';

            if (min_page < 1) { min_page = 1; }
            if (max_page > content.meta.num_pages) { max_page = content.meta.num_pages; }
            if (min_page > 1) { first_pg_msg = ' and below'; }
            if (max_page < content.meta.num_pages) { last_pg_msg = ' and above'; }

            for (let x = min_page; x <= max_page; x++) {
                let option_html = `<option value="${x}">Page ${x}</option>`;

                if (x === content.meta.page) { option_html = option_html.replace('">', '" selected>'); }
                if (x === min_page) { option_html = option_html.replace('</', `${first_pg_msg}</`); }
                else if (x === max_page) { option_html = option_html.replace('</', `${last_pg_msg}</`); }

                page_selector.append(option_html);
            }
            page_selector.removeClass("d-none");
            per_page_selector.removeClass("d-none");
            per_page_selector.val(search['page-size'].toString());

            // iterate through the records, adding a row for each one
            content.records.forEach(item => {
                let selected = '';
                if (selected_content.all) {
                    selected = "checked disabled";
                } else if (selected_content.ids.includes(item.id)) {
                    selected = "checked";
                }

                let row_html = `
                    <tr>
                        <td class="ct-selection-cell">
                            <input type="checkbox" id="ct_${ct.name}_${item.id}_selection-box" class="ct-${ct.name}-selection-box" ${selected}>
                            <a href="${item.uri}" target="_blank">
                                <span class="badge">Open <span class="fas fa-external-link-square-alt"></span></span>
                            </a>
                        </td>
                `;

                ct.fields.map(field => {
                    if (field.in_lists) {
                        let value = '';
                        if (item.hasOwnProperty(field.name)) {
                            value = item[field.name];

                            if (field.cross_reference_type && value) {
                                if (field.multiple) {
                                    let multi_value = '';
                                    for (let y in value) {
                                        multi_value += `, <a href="${value[y].uri}" target="_blank">${sender.strip_tags(value[y].label)}</a>`;
                                    }
                                    if (multi_value) {
                                        multi_value = multi_value.substring(2);
                                    }
                                    value = multi_value;
                                } else {
                                    value = `<a href="${value.uri}" target="_blank">${sender.strip_tags(value.label)}</a>`;
                                }
                            } else if (field.multiple) {
                                if (field.type === 'text' || field.type === 'large_text' || field.type === 'keyword') {
                                    value = value.join(' ');
                                } else {
                                    let multi_value = '';
                                    for (let y in value) {
                                        if (field.type === 'date') {
                                            multi_value += `, ${corpora.date_string(value[y])}`;
                                        }
                                        else {
                                            multi_value += `, ${value[y]}`;
                                        }
                                    }
                                    if (multi_value) {
                                        multi_value = multi_value.substring(2);
                                    }
                                    value = multi_value;
                                }
                            }
                            else if (field.type === 'date') {
                                value = corpora.date_string(value);
                            } else if (field.type === 'iiif-image') {
                                value = `<img src='${value}/full/,100/0/default.png' />`
                            } else if (field.type === 'large_text') {
                                value = value.slice(0, 500) + '...'
                            }
                        }

                        row_html += `
                            <td style="width: auto;">
                                <div class="corpora-content-cell">
                                    ${value}
                                </div>
                            </td>`;
                    }
                });

                row_html += "</tr>";
                ct_table_body.append(row_html);
            });
        }

        // handle checking/unchecking content selection boxes
        $(`.ct-${ct.name}-selection-box`).change(function() {
            let id_parts = this.id.split('_');
            let ct_name = id_parts[1];
            let content_id = id_parts[2];
            let go_button = $(`#ct-${ct_name}-selection-action-go-button`);

            if($(this).is(':checked')) {
                selected_content.ids.push(content_id);
            } else {
                selected_content.ids = selected_content.ids.filter(id => id !== content_id);
            }

            if (selected_content.ids.length > 0) { go_button.removeAttr('disabled'); }
            else { go_button.attr('disabled', true); }
        });
    }


    order_by(field) {
        let key = "s_" + field;
        if (this.search.hasOwnProperty(key)) {
            if (this.search[key] === 'asc') {
                this.search[key] = 'desc';
            } else {
                this.search[key] = 'asc';
            }
        } else {
            this.search[key] = 'asc';
        }
        let sender = this;

        this.corpora.list_content(this.corpus.id, this.content_type, this.search, function(content){ sender.load_content(content); });
    }


    remove_search_param(param) {
            if (this.search.hasOwnProperty(param)) {
                delete this.search[param];
                let sender = this;

                this.corpora.list_content(this.corpus.id, this.content_type, this.search, function(content){ sender.load_content(content); });
            }
    }

    strip_tags(label) {
        return label.replace(/(<([^>]+)>)/gi, "");
    }
}

class ContentGraph {
    constructor(corpora, corpus, vis_div_id, vis_legend_id, config={}) {
        this.corpora = corpora;
        this.corpus = corpus;
        this.corpus_id = corpus.id;
        this.corpus_uri = `/corpus/${this.corpus.id}`;
        this.nodes = new vis.DataSet([]);
        this.edges = new vis.DataSet([]);
        this.groups = {};
        this.selected_uris = [];
        this.collapsed_relationships = [];
        this.hidden_cts = ['Corpus', 'File'];
        this.extruded_nodes = [];
        this.panes_displayed = {};
        this.seed_uris = [];
        this.sprawls = [];
        this.sprawl_timer = null;
        this.per_type_limit = 'per_type_limit' in config ? config['per_type_limit'] : 20;
        this.vis_div_id = vis_div_id;
        this.vis_div = $(`#${vis_div_id}`);
        this.vis_legend_id = vis_legend_id;
        this.width = 'width' in config ? config['width'] : this.vis_div.width();
        this.height = 'height' in config ? config['height'] : this.vis_div.height();
        this.min_link_thickness = 'min_link_thickness' in config ? config['min_link_thickness'] : 1;
        this.max_link_thickness = 'max_link_thickness' in config ? config['max_link_thickness'] : 15;
        this.default_link_thickness = 'default_link_thickness' in config ? config['default_link_thickness'] : 1;
        this.label_display = 'label_display' in config ? config['label_display'] : 'full';
        this.last_action = 'explore';
        this.first_start = true;
        let sender = this;

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
            `);

            // SETUP EXPLORE CT MODAL COLLAPSE SELECTORS AND EVENTS
            let from_ct_selector = $('#from_ct_selector');
            let to_ct_selector = $('#to_ct_selector');
            let add_ct_selector = $('#addproxy_ct_selector');
            for (let ct_name in this.corpus.content_types) {
                let option = `<option value='${ct_name}'>${ct_name}</option>`;
                from_ct_selector.append(option);
                to_ct_selector.append(option);
                add_ct_selector.append(option);
            }

            add_ct_selector.change(function() {
                let ct_to_add = add_ct_selector.val();
                if (ct_to_add !== 'None') {
                    let cts_added = $('.modal-proxy-ct').html();
                    $('.modal-proxy-ct').html(cts_added + '.' + ct_to_add);
                }
            });

            $('#collapse-add-button').click(function() {
                let proxy_ct = $('.modal-proxy-ct').html();

                sender.collapsed_relationships.push({
                    from_ct: $('#from_ct_selector').val(),
                    proxy_ct: proxy_ct,
                    to_ct: $('#to_ct_selector').val()
                });

                sender.reset_graph();

                $('#explore-ct-modal').modal('hide');
            });

            $('#explore-ct-hide-button').click(function() {
                let hide_ct = $('.modal-proxy-ct').html();
                sender.hidden_cts.push(hide_ct);
                sender.reset_graph();
                $('#explore-ct-modal').modal('hide');
            });

            $('#explore-ct-sprawl-button').click(function() {
                let sprawl_ct = $('.modal-proxy-ct').html();
                sender.nodes.map(n => {
                    if (n.id.includes(`/${sprawl_ct}/`)) {
                        sender.sprawl_node(n.id);
                    }
                });
                $('#explore-ct-modal').modal('hide');
            });
        }

        // ENSURE MULTISELECT FORM EXISTS
        if (!$('#multiselect-form').length) {
            $('body').append(`
                <form id="multiselect-form" method="post" action="/not/set">
                    <input type="hidden" name="csrfmiddlewaretoken" value="${this.corpora.csrf_token}">
                    <input id="multiselect-content-ids" name="content-ids" type="hidden" value="">
                </form>
            `);
        }

        // ADD INITIAL CONTENT TO GRAPH
        if ('seeds' in config) {
            config.seeds.map(seed => {
                this.seed_uris.push(seed);
            });
        }

        // SETUP LEGEND
        this.setup_legend();

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
                    font: {
                        background: "white"
                    }
                },
                groups: this.groups,
                interaction: {
                    zoomSpeed: 0.4,
                    hover: true,
                    tooltipDelay: this.label_display === 'full' ? 3600000 : 100
                },
                physics: {
                    solver: 'repulsion',
                    forceAtlas2Based: {
                        springConstant: .04,
                        gravitationalConstant: -10,
                        damping: 0.9,
                        avoidOverlap: 1
                    },
                    stabilization: {
                        enabled: false,
                        fit: true
                    },
                },
                layout: {
                    improvedLayout: false
                }
            }
        );

        this.network.on("click", function(params) {
            sender.remove_unpinned_panes();

            if (params.nodes.length > 0) {
                let clicked_uri = params.nodes[0];
                let clicked_node = sender.nodes.get(clicked_uri);
                let pane_id = `${clicked_uri.replace(/\//g, '-')}-pane`;
                let canvas_offset = sender.vis_div.offset();
                let pane_x = params.pointer.DOM.x + canvas_offset.left;
                let pane_y = params.pointer.DOM.y + canvas_offset.top;

                if (!$(`#${pane_id}`).length) {
                    $('body').append(`
                        <div id="${pane_id}"
                            class="content-pane"
                            style="background-color: rgba(255, 255, 255, .8);
                                width: 200px;
                                height: 225px;
                                position: absolute;
                                top: ${pane_y}px;
                                left: ${pane_x}px;
                                pointer-events: auto;"
                            data-uri="${clicked_uri}">
    
                            <div style="height: 25px;">
                                <span id="${pane_id}-select" title="Select" data-uri="${clicked_uri}" class="popup-button far fa-check-square" ${sender.selected_uris.includes(clicked_uri) ? "style='color: #EF3E36;'" : ''}></span>
                                <span id="${pane_id}-pin" title="Pin" data-uri="${clicked_uri}" class="popup-button fas fa-thumbtack"></span>
                                <span id="${pane_id}-sprawl" title="Sprawl" data-uri="${clicked_uri}" class="popup-button fas fa-expand-arrows-alt"></span>
                                <span id="${pane_id}-extrude" title="Hide" data-uri="${clicked_uri}" class="popup-button far fa-eye-slash"></span>
                                <a href="${clicked_uri}/" target="_blank"><span title="Open" class="popup-button float-right fas fa-external-link-square-alt"></span></a>
                            </div>
                            <iframe src="${clicked_uri}/?popup=y" frameBorder="0" width="200px" height="200px" />
                        </div>
                    `);

                    $(`#${pane_id}-select`).click(function() {
                        let uri = $(this).data('uri');
                        let node = sender.nodes.get(uri);

                        if (!sender.selected_uris.includes(uri)) {
                            sender.selected_uris.push(uri);
                            $(this).css('color', '#EF3E36');
                            node.font = {
                                background: '#EF3E36',
                                color: "white"
                            };
                        } else {
                            sender.selected_uris = sender.selected_uris.filter(val => val !== uri);
                            $(this).css('color', '#091540');
                            node.font = {
                                background: 'white',
                                color: "black"
                            };
                        }
                        sender.nodes.update(node);
                        sender.setup_legend();
                    });

                    $(`#${pane_id}-pin`).click(function() {
                        sender.pin_node($(this).data('uri'));
                    });

                    $(`#${pane_id}-sprawl`).click(function() {
                        sender.sprawl_node($(this).data('uri'));
                    });

                    $(`#${pane_id}-extrude`).click(function() {
                        sender.extrude_node($(this).data('uri'), true);
                    });

                    sender.panes_displayed[clicked_uri] = {pinned: false};
                    sender.make_draggable(document.getElementById(pane_id));
                }
            }
        });

        this.network.on("dragStart", function(params){
            params.nodes.map(id => {
                let n = sender.nodes.get(id);
                n.fixed = false;
                //affix_node_label(n);
                sender.nodes.update(n);
            });
        });

        this.network.on("dragEnd", function(params){
            params.nodes.map(id => {
                sender.nodes.update([{ id: id, fixed: true }]);
            });
        });

        this.seed_uris.map(uri => this.sprawl_node(uri, true));
        this.normalize_collapse_thickness();
    }

    setup_legend() {
        let sender = this;
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
        ];
        let group_color_cursor = 0;

        // ensure the first content type in seeds receives the first color
        if (this.seed_uris.length) {
            let seed_group = this.seed_uris[0].split('/')[3];
            this.groups[seed_group] = {color:group_colors[group_color_cursor]};
            group_color_cursor++;
        }

        let group_names = Object.keys(this.corpus.content_types).map(ct => ct);
        group_names.map(group_name => {
            if (group_name !== 'Corpus' && !Object.keys(this.groups).includes(group_name)) {
                this.groups[group_name] = {
                    color: group_colors[group_color_cursor]
                };
                group_color_cursor++;
                if (group_color_cursor >= group_colors.length) group_color_cursor = 0;
            }
        });

        let legend = $(`#${this.vis_legend_id}`);
        legend.html('');
        for (let group_name in this.groups) {
            let action_links = "";

            this.collapsed_relationships.map(col_rel => {
                if (group_name === col_rel['proxy_ct']) {
                    action_links += `<a href="#" class="uncollapse-link mr-2" data-collapse="${col_rel.proxy_ct}">uncollapse</a>`;
                }
            });

            this.hidden_cts.map(hidden => {
                if (group_name === hidden) {
                    action_links += `<a href="#" class="unhide-link mr-2" data-hidden="${hidden}">unhide</a>`;
                }
            });

            legend.append(`
                <span class="badge mr-1 p-1 ct-legend-badge" style="background-color: ${this.groups[group_name].color}; color: #FFFFFF; cursor: pointer;">${group_name}</span>${action_links}
            `);
        }

        // LABEL OPTIONS
        legend.append(`
            <select id="explore-label-opt" class="mr-2">
                <option value="full" ${sender.label_display === 'full' ? 'selected' : ''}>Show full label</option>
                <option value="trunc" ${sender.label_display === 'trunc' ? 'selected' : ''}>Show truncated label</option>
                <option value="hover" ${sender.label_display === 'hover' ? 'selected' : ''}>Show label only on hover</option>
            </select>
        `);

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
            `);

            $('#explore-selected-action-button').click(function() {
                let action = $('#explore-selected-action').val();
                let ct_name = sender.selected_uris[0].split('/')[3];
                let multi_form = $('#multiselect-form');

                if (action === 'explore') {
                    multi_form.append(`
                        <input type='hidden' name='content-uris' value='${sender.selected_uris.join(',')}'/>
                    `);
                    multi_form.attr('action', `/corpus/${sender.corpus_id}/${ct_name}/explore/?popup=y`);
                    multi_form.attr('target', '_blank');
                    multi_form.submit();
                    multi_form.removeAttr('target');
                } else if (action === 'merge') {
                    let content_ids = [];
                    let cts_valid = true;

                    sender.selected_uris.map(uri => {
                        let uri_parts = uri.split('/');
                        if (uri_parts[3] === ct_name) {
                            content_ids.push(uri_parts[4]);
                        } else {
                            cts_valid = false;
                        }
                    });

                    if (cts_valid) {
                        $('#multiselect-content-ids').val(content_ids.join(','));
                        multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/merge/`);
                        multi_form.submit();
                    } else {
                        alert("In order to merge content, all selected nodes must be of the same content type!");
                    }
                } else if (action === 'hide') {
                    sender.selected_uris.map(uri => sender.extrude_node(uri, true));
                    sender.selected_uris = [];
                    sender.setup_legend();
                } else if (action === 'sprawl') {
                    sender.selected_uris.map(uri => sender.sprawl_node(uri));
                }

                sender.last_action = action;
            });
        }

        $('.ct-legend-badge').click(function() {
            let explore_ct = $(this).html();
            $('#explore-ct-modal-label').html(`${explore_ct} Options`);
            $('.modal-proxy-ct').html(explore_ct);

            let collapsible = true;
            let hideable = !sender.hidden_cts.includes(explore_ct);

            sender.collapsed_relationships.map(col_rel => {
                if (col_rel.proxy_ct === explore_ct) {
                    collapsible = false;
                }
            });

            if (collapsible) {
                $('#explore-ct-modal-already-collapsed-div').addClass('d-none');
                $('#explore-ct-modal-collapse-div').removeClass('d-none');
            } else {
                $('#explore-ct-modal-already-collapsed-div').removeClass('d-none');
                $('#explore-ct-modal-collapse-div').addClass('d-none');
            }

            if (hideable) {
                $('#explore-ct-hide-button').attr('disabled', false);
            } else {
                $('#explore-ct-hide-button').attr('disabled', true);
            }

            $('#explore-ct-modal').modal();
        });

        $('.uncollapse-link').click(function(e) {
            e.preventDefault();
            let col_proxy = $(this).data('collapse');
            for (let cl_index = 0; cl_index < sender.collapsed_relationships.length; cl_index++) {
                if (sender.collapsed_relationships[cl_index].proxy_ct === col_proxy) {
                    sender.collapsed_relationships.splice(cl_index, 1);
                    break;
                }
            }
            sender.reset_graph();
        });

        $('.unhide-link').click(function(e) {
            e.preventDefault();
            let hid_index = sender.hidden_cts.indexOf($(this).data('hidden'));
            sender.hidden_cts.splice(hid_index, 1);
            sender.reset_graph();
        });

        $('#explore-label-opt').change(function() {
            let option = $('#explore-label-opt').val();
            sender.label_display = option;
            if (option === 'full') {
                sender.network.setOptions({interaction:{tooltipDelay:3600000}});
            } else {
                sender.network.setOptions({interaction:{tooltipDelay:100}});
            }

            sender.nodes.map(n => {
                sender.format_label(n);
                sender.nodes.update(n);
            });
        });
    }

    format_label(n) {
        if (this.label_display === 'full') {
            n.label = n.label_data;
            n.title = null;
        } else if (this.label_display === 'trunc') {
            n.label = n.label_data.slice(0, 20);
            n.title = n.label_data;
        } else {
            n.label = '';
            n.title = n.label_data;
        }
    }

    sprawl_node(uri, sprawl_children=false) {
        let sender = this;
        let node_ct = uri.split('/').slice(-2)[0];
        let node_id = uri.split('/').slice(-1)[0];
        let skip = 0;

        let sprawl_node = this.nodes.get(uri);
        if (sprawl_node && sprawl_node.hasOwnProperty('skip')) {
            skip = sprawl_node.skip;
        }

        let net_json_params = {
            per_type_skip: skip,
            per_type_limit: this.per_type_limit
        };

        let collapse_param = this.collapsed_relationships.map(rel => `${rel.from_ct}-${rel.proxy_ct}-${rel.to_ct}`).join(',');
        if (collapse_param) { net_json_params['collapses'] = collapse_param; }

        let hidden_param = this.hidden_cts.join(',');
        if (hidden_param) { net_json_params['hidden'] = hidden_param; }

        this.sprawls.push(false);
        clearTimeout(this.sprawl_timer);
        this.sprawl_timer = setTimeout(this.await_sprawls.bind(this), 1000);
        let sprawl_index = this.sprawls.length - 1;

        this.corpora.get_network_json(this.corpus_id, node_ct, node_id, net_json_params, function(net_json) {
            let children = [];

            net_json.nodes.map(n => {
                if (n.id !== sender.corpus_uri && !sender.nodes.get(n.id) && !sender.extruded_nodes.includes(n.id)) {
                    n.label_data = unescape(n.label);
                    sender.format_label(n);
                    sender.nodes.add(n);
                    if (sprawl_children) {
                        children.push(n.id);
                    }
                }
            });

            net_json.edges.map(e => {
                e.id = `${e.from}-${e.to}`;
                if (!sender.extruded_nodes.includes(e.from) && !sender.extruded_nodes.includes(e.to) && !sender.edges.get(e.id)) {
                    sender.edges.add(e);
                }
            });

            if (sprawl_children) {
                children.map(child_uri => sender.sprawl_node(child_uri));
            }
        });

        if (sprawl_node) {
            sprawl_node.skip = skip += this.per_type_limit;
            sender.nodes.update(sprawl_node);
        }

        sender.sprawls[sprawl_index] = true;

        if (this.first_start) {
            this.first_start = false;
        }
    }

    await_sprawls() {
        clearTimeout(this.sprawl_timer);
        if (this.sprawls.includes(false)) {
            this.sprawl_timer = setTimeout(this.await_sprawls.bind(this), 1000);
        } else {
            this.sprawls = [];
            this.normalize_collapse_thickness();
            this.setup_legend();
        }
    }

    reset_graph() {
        this.edges.clear();
        this.nodes.clear();
        this.first_start = true;

        this.seed_uris.map(uri => {
            this.sprawl_node(uri, true);
        });
    }

    extrude_node(uri, remove_isolated=false) {
        let sender = this;
        this.extruded_nodes.push(uri);
        let edge_ids = this.network.getConnectedEdges(uri);
        edge_ids.map(edge_id => this.edges.remove(edge_id));
        this.nodes.remove(uri);

        if (remove_isolated) {
            let isolated_nodes = new vis.DataView(this.nodes, {
                filter: function (node) {
                    let connEdges = sender.edges.get({
                        filter: function (edge) {
                            return (
                                (edge.to == node.id) || (edge.from == node.id));
                        }
                    });
                    return connEdges.length == 0;
                }
            });

            isolated_nodes.map(i => this.extrude_node(i.id, false));
        }
    }

    pin_node(uri) {
        if (!this.panes_displayed[uri].pinned) {
            this.panes_displayed[uri].pinned = true;
            let pin_id = `${uri.replace(/\//g, '-')}-pane-pin`;
            $(`#${pin_id}`).css('color', '#EF3E36');
        } else {
            this.panes_displayed[uri].pinned = false;
            this.remove_unpinned_panes();
        }
    }

    normalize_collapse_thickness() {
        this.collapsed_relationships.map(col_rel => {
            let title_a = `has${col_rel.to_ct}via${col_rel.proxy_ct}`;
            let title_b = `has${col_rel.from_ct}via${col_rel.proxy_ct}`;

            let redundant_edges = this.edges.get({
                filter: function(edge) {
                    return edge.title === title_b;
                }
            });

            redundant_edges.map(r => {
                let id_parts = r.id.split('-');
                let inverse_id = `${id_parts[1]}-${id_parts[0]}`;
                let inverse_edge = this.edges.get(inverse_id);
                if (inverse_edge === null) {
                    this.edges.add({
                        id: inverse_id,
                        from: id_parts[1],
                        to: id_parts[0],
                        title: title_a,
                        freq: r.freq
                    });
                }
                this.edges.remove(r.id);
            });

            let col_edges = this.edges.get({
                filter: function(edge) {
                    return edge.title === title_a;
                }
            });

            let min_freq = 9999999999999999999999;
            let max_freq = 1;
            col_edges.map(e => {
                if (e.freq < min_freq) { min_freq = e.freq; }
                if (e.freq > max_freq) { max_freq = e.freq; }
            });

            let updated_edges = [];
            col_edges.map(e => {
                let mx = (e.freq - min_freq) / (max_freq - min_freq);
                let preshiftNorm = mx * (this.max_link_thickness - this.min_link_thickness);
                updated_edges.push({
                    id: e.id,
                    value: parseInt(preshiftNorm + this.min_link_thickness)
                });
            });
            this.edges.update(updated_edges);
        });
    }

    remove_unpinned_panes() {
        for (let pane_uri in this.panes_displayed) {
            if (!this.panes_displayed[pane_uri].pinned) {
                let pane_id = `${pane_uri.replace(/\//g, '-')}-pane`;
                $(`#${pane_id}`).remove();
                delete this.panes_displayed[pane_uri];
            }
        }
    }

    make_draggable(elmnt) {
        var pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
        if (document.getElementById(elmnt.id + "header")) {
            // if present, the header is where you move the DIV from:
            document.getElementById(elmnt.id + "header").onmousedown = dragMouseDown;
        } else {
            // otherwise, move the DIV from anywhere inside the DIV:
            elmnt.onmousedown = dragMouseDown;
        }

        function dragMouseDown(e) {
            e = e || window.event;
            e.preventDefault();
            // get the mouse cursor position at startup:
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            // call a function whenever the cursor moves:
            document.onmousemove = elementDrag;
        }

        function elementDrag(e) {
            e = e || window.event;
            e.preventDefault();
            // calculate the new cursor position:
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            // set the element's new position:
            elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
            elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
        }

        function closeDragElement() {
            // stop moving when mouse button is released:
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }
}

