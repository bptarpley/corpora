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

    get_corpus(id, callback) {
        this.make_request(
            `/api/corpus/${id}/`,
            "GET",
            {},
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
        console.log(this);
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
                                        multi_value += `, <a href="${value[y].uri}" target="_blank">${value[y].label}</a>`;
                                    }
                                    if (multi_value) {
                                        multi_value = multi_value.substring(2);
                                    }
                                    value = multi_value;
                                } else {
                                    value = `<a href="${value.uri}" target="_blank">${value.label}</a>`;
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
}