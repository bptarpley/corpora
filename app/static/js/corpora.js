const FIELD_TYPE_LABELS = {
    text: 'Text',
    html: 'HTML',
    choice: 'Choice',
    number: 'Number',
    date: 'Date',
    file: 'File',
    image: 'Image',
    link: 'Link',
    cross_reference: 'Cross Reference'
};

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

    make_request(path, type, params={}, callback) {
        let req = {
            type: type,
            url: `${this.host}${path}`,
            dataType: 'json',
            data: params,
            success: callback
        };
        if (this.auth_token) {
            req['beforeSend'] = function(xhr) { xhr.setRequestHeader("Authorization", `Token ${sender.auth_token}`); }
        } else if (type === 'POST' && this.csrf_token) {
            req['data'] = Object.assign({}, req['data'], {'csrfmiddlewaretoken': this.csrf_token});
        }

        let sender = this;
        $.ajax(req);
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

    get_corpus_jobs(corpus_id, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/jobs/`,
            "GET",
            {},
            callback
        );
    }

    get_documents(corpus_id, search={}, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/document/`,
            "GET",
            search,
            callback
        );
    }

    get_document(corpus_id, document_id, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/document/${document_id}/`,
            "GET",
            {},
            callback
        );
    }

    get_document_page_file_collections(corpus_id, document_id, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/document/${document_id}/page-file-collections/`,
            "GET",
            {},
            callback
        );
    }

    get_document_jobs(corpus_id, document_id, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/document/${document_id}/jobs/`,
            "GET",
            {},
            callback
        );
    }

    get_document_kvp(corpus_id, document_id, key, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/document/${document_id}/kvp/${key}/`,
            "GET",
            {},
            callback
        );
    }

    set_document_kvp(corpus_id, document_id, key, value, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/document/${document_id}/kvp/${key}/`,
            "POST",
            {value: value},
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

    get_tasks(callback) {
        this.make_request(
            `/api/tasks/`,
            "GET",
            {},
            callback
        );
    }

    get_content_types(corpus_id, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/type/`,
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
            `/api/corpus/${corpus_id}/type/${content_type}/${content_id}`,
            "GET",
            {},
            callback
        );
    }

    list_content(corpus_id, content_type, search={}, callback) {
        this.make_request(
            `/api/corpus/${corpus_id}/type/${content_type}/`,
            "GET",
            search,
            callback
        );
    }

    edit_content(corpus_id, content_type, fields={}) {
        this.make_request(
            `/api/corpus/${corpus_id}/type/${content_type}/`,
            "POST",
            fields,
            callback
        )
    }
}

class TypeManager {
    constructor(div_id, corpus_id, content_types=[], template_formats=[]) {
        this.div = $(`#${div_id}`);
        this.corpus_id = corpus_id;
        if (this.div.length) {
            this.div_id = div_id;
            this.content_types = [];
            this.div.addClass('tm');
            this.div.addClass('card');
            this.ct_div = $('#tm-ct-group');

            // SETUP TEMPLATE FORMATS/EDITORS
            this.template_formats = template_formats;
            $('#template-format-modal-table-body').html('');
            for (let x = 0; x < this.template_formats.length; x++) {
                let label = this.template_formats[x].label;
                let extension = this.template_formats[x].extension;
                let mode = this.template_formats[x].ace_editor_mode;
                let mime_type = this.template_formats[x].mime_type;

                // ADD FORMAT TAB
                $('#template-modal-tablist').append(`
                    <li class="nav-item">
                        <a class="nav-link ${(x == 0) ? 'active' : ''}" id="template-${extension}-tab" data-toggle="tab" href="#template-${extension}-div" role="tab" aria-controls="template-${extension}-div" aria-selected="true">${label}</a>
                    </li>
                `);
                $('#template-modal-tabs').append(`
                    <div class="tab-pane fade ${(x == 0) ? 'show active' : ''}" id="template-${extension}-div" role="tabpanel" aria-labelledby="template-${extension}-tab">
                        <div id="template-${extension}-editor" style="height: 400px;"></div>
                    </div>
                `);

                // INSTANTIATE FORMAT EDITOR
                template_editors[extension] = ace.edit(`template-${extension}-editor`);
                template_editors[extension].setTheme("ace/theme/monokai");
                template_editors[extension].getSession().setMode(`ace/mode/${mode}`);

                // ADD ROW TO MANAGE TEMPLATE FORMAT TABLE
                $('#template-format-modal-table-body').append(`
                    <tr><td>${label}</td><td>${extension}</td><td>${mime_type}</td></tr>
                `);
            }

            let sender = this;

            // NEW CONTENT TYPE BUTTON CLICK
            $('#new-ct-button').click(function() {
                $('#new-ct-index').val('new');
                $('#new-ct-name-box').prop('disabled', false);
                $('#new-ct-name-box').val('');
                $('#new-ct-plural-name-box').val('');
                $('#new-ct-nav-checkbox').prop('checked', true);
                $('#new-ct-proxy-field-selector').val('');
                $('#new-ct-proxy-field-div').addClass('d-none');
                $('#new-ct-modal').modal();
            });

            // PEP8 CLASS FORMAT CONTENT TYPE NAME
            $('#new-ct-name-box').focusout(function() {
                $('#new-ct-name-box').val(pep8_class_format(pep8_variable_format($('#new-ct-name-box').val())));
            });

            // PEP8 VARIABLE FORMAT FIELD NAME
            $('#new-f-name-box').focusout(function() {
                $('#new-f-name-box').val(pep8_variable_format($('#new-f-name-box').val()));
            });

            // CREATE CONTENT TYPE BUTTON CLICK
            $('#new-ct-create-button').click(function() {
                let ct_index = $('#new-ct-index').val();
                if (ct_index == 'new') {
                    let content_type = {
                        id: '',
                        name: $('#new-ct-name-box').val(),
                        plural_name: $('#new-ct-plural-name-box').val(),
                        show_in_nav: $('#new-ct-nav-checkbox').is(':checked'),
                        proxy_field: '',
                        templates: {
                            edit: {},
                            view: {},
                            list: {},
                            label: {}
                        },
                        fields: []
                    };
                    sender.add_content_type(null, content_type);
                } else {
                    ct_index = parseInt(ct_index);
                    sender.content_types[ct_index].plural_name = $('#new-ct-plural-name-box').val();
                    sender.content_types[ct_index].show_in_nav = $('#new-ct-nav-checkbox').is(':checked');
                    sender.content_types[ct_index].proxy_field = $('#new-ct-proxy-field-selector').val();
                }
                $('#new-ct-modal').modal('hide');
            });

            // TYPE SELECTION CHANGE
            $('#new-f-type-box').change(function() {
                let selection = $(this).val();

                if (selection == 'cross_reference') {
                    $('#new-f-cross-reference-box').removeClass('d-none');
                } else {
                    $('#new-f-cross-reference-box').addClass('d-none');
                }
            });

            // INDEXED CHECK CHANGE
            $('#new-f-indexed-checkbox').change(function() {
                if (this.checked && $('#new-f-indexed-with-box option').length > 0) {
                    $('#new-f-indexed-with-div').removeClass('d-none');
                    $('#new-f-indexed-with-div').addClass('d-flex');
                } else {
                    $('#new-f-indexed-with-div').removeClass('d-flex');
                    $('#new-f-indexed-with-div').addClass('d-none');
                }
            });

            // UNIQUE CHECK CHANGE
            $('#new-f-unique-checkbox').change(function() {
                if (this.checked && $('#new-f-unique-with-box option').length > 0) {
                    $('#new-f-unique-with-div').removeClass('d-none');
                    $('#new-f-unique-with-div').addClass('d-flex');
                } else {
                    $('#new-f-unique-with-div').removeClass('d-flex');
                    $('#new-f-unique-with-div').addClass('d-none');
                }
            });

            // CREATE FIELD BUTTON CLICK
            $('#new-f-create-button').click(function() {
                let cross_reference_type = '';
                if ($('#new-f-type-box').val() == 'cross_reference') {
                    cross_reference_type = $('#new-f-cross-reference-box').val();
                }

                let field = {
                    name: $('#new-f-name-box').val(),
                    label: $('#new-f-label-box').val(),
                    in_lists: $('#new-f-in-lists-checkbox').is(':checked'),
                    indexed: $('#new-f-indexed-checkbox').is(':checked'),
                    indexed_with: $('#new-f-indexed-with-box').val(),
                    unique: $('#new-f-unique-checkbox').is(':checked'),
                    unique_with: $('#new-f-unique-with-box').val(),
                    multiple: $('#new-f-multiple-checkbox').is(':checked'),
                    cross_reference_type: cross_reference_type,
                    type: $('#new-f-type-box').val(),
                    views: {}
                };

                let ct_index = parseInt($('#new-f-ct-id').val());
                let f_index = $('#new-f-f-id').val();
                let action = $('#new-f-action').val();

                if (action == 'create' && f_index == 'new') {
                    if(!(typeof sender.content_types[ct_index] === 'undefined')) {
                        sender.content_types[ct_index].add_field(null, field);
                    }
                } else {
                    f_index = parseInt(f_index);
                    if(!(typeof sender.content_types[ct_index] === 'undefined') && !(typeof sender.content_types[ct_index].fields[f_index] === 'undefined')) {
                        sender.content_types[ct_index].fields[f_index].edit(field);
                    }
                }

                $('#new-f-modal').modal('hide');
            });

            // TEMPLATE REGENERATE BUTTON
            $(`#template-regenerate-button`).click(function (){
                let ct_index = parseInt($('#template-ct-id').val());
                let template_type = $('#template-type').val();
                template_editors.html.setValue(sender.content_types[ct_index].default_template(template_type).html);
                template_editors.js.setValue(sender.content_types[ct_index].default_template(template_type).js);
            });

            // TEMPLATE SAVE BUTTON
            $(`#template-save-button`).click(function (){
                let ct_index = parseInt($('#template-ct-id').val());
                let template_type = $('#template-type').val();

                for (let x = 0; x < sender.template_formats.length; x++) {
                    let extension = sender.template_formats[x].extension;
                    sender.content_types[ct_index].templates[template_type][extension] = template_editors[extension].getValue();
                }
                $('#template-modal').modal('hide');
            });

            // ADD CONTENT TYPES
            if (!(content_types === undefined || content_types.length == 0)) {
                for (let x = 0; x < content_types.length; x++) {
                    this.add_content_type(x, content_types[x]);
                }
            }
        } else {
            console.log('div for type manager does not exist!');
        }
    }

    add_content_type(ct_index=null, content_type={}) {
        if (!(this.content_types === undefined)) {

            // SETUP INDEX, DIV NAMES
            let new_ct_index = ct_index;
            if (new_ct_index == null) { new_ct_index = this.content_types.length; }
            if (new_ct_index == 0) { this.ct_div.html(''); }
            let new_ct_div_id = `tm-ct${new_ct_index}`;
            let new_ct_name = 'New Content Type';
            if (!$.isEmptyObject(content_type)) { new_ct_name = content_type.name; }

            // APPEND MAIN CONTENT TYPE DIV
            this.ct_div.append(`
                <div id="${new_ct_div_id}-container" class="list-group-item content-type">
                    <button id="${new_ct_div_id}-button" class="btn btn-sm btn-link" data-toggle="collapse" data-target="#${new_ct_div_id}" aria-expanded="false" aria-controls="${new_ct_div_id}">
                        <span id="${new_ct_div_id}-indicator" class="fas fa-caret-right"></span>
                        <h5 id="${new_ct_div_id}-name" style="display: inline;">${new_ct_name}</h5>
                    </button>
                    <span class="float-right">
                        <button id="${new_ct_div_id}-edit-button" class="btn btn-sm btn-primary"><span class="fas fa-edit"></span></button>
                        <button id="${new_ct_div_id}-delete-button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></span></button>
                    </span>
                    <div id="${new_ct_div_id}" class="alert alert-info collapse p-3 mt-2" aria-labelledby="${new_ct_div_id}-container" data-parent="#tm-ct-group">
                        <h5>Fields</h5>
                        <table class="table table-striped">
                            <thead class="thead-dark">
                                <th scope="col">Name</th>
                                <th scope="col">Label</th>
                                <th scope="col">Type</th>
                                <th scope="col">In Lists?</th>
                                <th scope="col">Indexed?</th>
                                <th scope="col">Unique?</th>
                                <th scope="col">Multiple?</th>
                                <th scope="col"></th>
                            </thead>
                            <tbody id="${new_ct_div_id}-f-table">
                                <tr><td colspan="7">No fields have been defined.</td></tr>
                            </tbody>
                        </table>
                        <button type="button" class="btn btn-primary" id="${new_ct_div_id}-new-f-button">New Field</button>
                        <span class="ml-2">
                            Edit Template: <select id="${new_ct_div_id}-edit-template-selector"></select>
                            <button type="button" class="btn btn-sm btn-secondary ml-2" id="${new_ct_div_id}-edit-template-button">Go</button>
                            <button type="button" class="btn btn-sm btn-secondary ml-2" id="${new_ct_div_id}-regenerate-templates-button">Regenerate All Templates</button>
                        </span>
                    </div>
                </div>
            `);

            // SETUP TEMPLATE SELECTION FOR TEMPLATE EDITOR
            for (let template in content_type.templates) {
                if(template != "field_templates") {
                    $(`#${new_ct_div_id}-edit-template-selector`).append(`
                        <option value="${template}">${pep8_class_format(template)}</option>
                    `);
                }
            }

            // ADD CONTENT TYPE OBJECT
            this.content_types.push(
                new ContentType(new_ct_index, new_ct_div_id, this.corpus_id, content_type)
            );
            let sender = this;

            // SETUP COLLAPSE ICONS
            $(`#${new_ct_div_id}`).on('show.bs.collapse', function (event) {
                let indicator = $(`#${new_ct_div_id}-indicator`);
                indicator.removeClass("fa-caret-right");
                indicator.addClass("fa-caret-down");
            });
            $(`#${new_ct_div_id}`).on('hidden.bs.collapse', function (event) {
                let indicator = $(`#${new_ct_div_id}-indicator`);
                indicator.removeClass("fa-caret-down");
                indicator.addClass("fa-caret-right");
            });

            // ADD CONTENT TYPE TO CROSS REFERENCE OPTIONS
            $('#new-f-cross-reference-box').append(`
                <option value='${new_ct_name}'>${new_ct_name}</option>
            `);

            // EDIT CONTENT TYPE BUTTON
            $(`#${new_ct_div_id}-edit-button`).click(function() {
                $('#new-ct-index').val(new_ct_index);
                $('#new-ct-name-box').val(sender.content_types[new_ct_index].name);
                $('#new-ct-name-box').prop('disabled', true);
                $('#new-ct-plural-name-box').val(sender.content_types[new_ct_index].plural_name);
                $('#new-ct-nav-checkbox').prop('checked', sender.content_types[new_ct_index].show_in_nav);

                let has_xrefs = false;
                let proxy_field_selector = $('#new-ct-proxy-field-selector');
                let proxy_field_div = $('#new-ct-proxy-field-div');
                proxy_field_selector.html('');
                proxy_field_selector.append(`
                    <option value=''>None</option>
                `);
                for (let x = 0; x < sender.content_types[new_ct_index].fields.length; x++) {
                    if (sender.content_types[new_ct_index].fields[x].type == 'cross_reference') {
                        has_xrefs = true;
                        proxy_field_selector.append(`
                            <option value='${sender.content_types[new_ct_index].fields[x].name}'>${sender.content_types[new_ct_index].fields[x].label}</option>
                        `);
                    }
                }
                proxy_field_selector.val(sender.content_types[new_ct_index].proxy_field);
                if (has_xrefs) { proxy_field_div.removeClass('d-none'); } else { proxy_field_div.addClass('d-none'); }

                $('#new-ct-modal').modal();
            });

            // DELETE CONTENT TYPE BUTTON
            $(`#${new_ct_div_id}-delete-button`).click(function() {
                $('#confirmation-ct-index').val(new_ct_index);
                $('#confirmation-ct-name').val(sender.content_types[new_ct_index].name);
                $('#confirmation-field-index').val('');
                $('#confirmation-field-name').val('');
                $('#confirmation-action').val('delete');
                $('#confirmation-confirm-button').attr('disabled', false);

                let message = `You are attempting to delete the <b>${sender.content_types[new_ct_index].name}</b> content type.
                Upon doing so, <b>all content of this type will be irreversibly deleted</b>. Some templates may also need to be
                regenerated or manually adjusted. Are you sure you want to proceed?`;

                let referencing_fields = [];
                for (let x = 0; x < sender.content_types.length; x++) {
                    for (let y = 0; y < sender.content_types[x].fields.length; y++) {
                        if (sender.content_types[x].fields[y].cross_reference_type == sender.content_types[new_ct_index].name) {
                            referencing_fields.push(`${sender.content_types[x].name} -> ${sender.content_types[x].fields[y].name}`);
                        }
                    }
                }

                if (referencing_fields.length > 0) {
                    message = `
                        You are attempting to delete the ${sender.content_types[new_ct_index].name} content type.
                        This is currently not possible, as the following fields reference this content type:<ul class="mt-2">
                    `;
                    referencing_fields.map(x => message += `<li>${x}</li>`);
                    message += `
                        </ul>If you still wish to delete the ${sender.content_types[new_ct_index].name} content type,
                        you must first delete the above fields.
                    `;
                    $('#confirmation-confirm-button').attr('disabled', true);
                }

                $('#confirmation-modal-message').html(message);
                $('#confirmation-modal').modal();
            });

            // NEW FIELD BUTTON
            $(`#${new_ct_div_id}-new-f-button`).click(function (){
                $('#new-f-modal-label').html('Create New Field');
                $('#new-f-ct-id').val(new_ct_index);
                $('#new-f-f-id').val('new');
                $('#new-f-action').val('create');
                $('#new-f-name-box').val('');
                $('#new-f-name-box').prop('disabled', false);
                $('#new-f-label-box').val('');
                $('#new-f-type-box').val('text');
                $('#new-f-in-lists-checkbox').prop('checked', true);
                $('#new-f-indexed-checkbox').prop('checked', false);
                $('#new-f-unique-checkbox').prop('checked', false);
                $('#new-f-multiple-checkbox').prop('checked', false);
                $('#new-f-create-button').html('Create');

                $('.f-with').html('');
                for (let x = 0; x < sender.content_types[new_ct_index].fields.length; x++) {
                    $('.f-with').append(`
                        <option value='${sender.content_types[new_ct_index].fields[x].name}'>${sender.content_types[new_ct_index].fields[x].label}</option>
                    `);
                }

                $('#new-f-indexed-with-box').val([]);
                $('#new-f-indexed-with-div').removeClass('d-flex');
                $('#new-f-indexed-with-div').addClass('d-none');
                $('#new-f-unique-with-box').val([]);
                $('#new-f-unique-with-div').removeClass('d-flex');
                $('#new-f-unique-with-div').addClass('d-none');
                $('#new-f-cross-reference-box').addClass('d-none');

                $('#new-f-create-button').html('Create');
                $('#new-f-modal').modal();
            });

            // EDIT TEMPLATE BUTTON
            $(`#${new_ct_div_id}-edit-template-button`).click(function (){
                let template_type = $(`#${new_ct_div_id}-edit-template-selector`).val();
                $('#template-ct-id').val(new_ct_index);
                $('#template-type').val(template_type);

                for (let x = 0; x < sender.template_formats.length; x++) {
                    let extension = sender.template_formats[x].extension;
                    if (!sender.content_types[new_ct_index].templates[template_type].hasOwnProperty(extension)) {
                        if (extension == 'js' || extension == 'html') {
                            sender.content_types[new_ct_index].templates[template_type][extension] = sender.content_types[new_ct_index].default_template(template_type)[extension];
                        } else {
                            sender.content_types[new_ct_index].templates[template_type][extension] = '';
                        }
                    }
                    template_editors[extension].setValue(sender.content_types[new_ct_index].templates[template_type][extension]);
                }
                $('#template-modal').modal();
            });

            // REGENERATE ALL TEMPLATES BUTTON
            $(`#${new_ct_div_id}-regenerate-templates-button`).click(function() {
                let template_types = ['edit', 'view', 'list', ];
                for (let x = 0; x < template_types.length; x++) {
                    sender.content_types[new_ct_index].templates[template_types[x]].html = sender.content_types[ct_index].default_template(template_types[x]).html;
                    sender.content_types[new_ct_index].templates[template_types[x]].js = sender.content_types[ct_index].default_template(template_types[x]).js;
                }
            });
        }
    }

    to_object() {
        return this.content_types.map(x => x.to_object())
    }

    to_json() {
        return JSON.stringify(this.to_object());
    }
}

class ContentType {
    constructor(index, div_id, corpus_id, content_type={}) {
        this.corpus_id = corpus_id;
        if ($(`#${div_id}`).length) {
            this.index = index;
            this.div_id = div_id;
            this.div = $(`#${div_id}`);
            this.f_div_id = `${this.div_id}-f-table`;
            this.f_div = $(`#${this.f_div_id}`);
            this.fields = [];

            if ($.isEmptyObject(content_type)) {
                this.id = '';
                this.name = 'NewType';
                this.plural_name = 'NewTypes';
                this.show_in_nav = true;
                this.proxy_field = '';
                this.templates = {
                    edit: {},
                    view: {},
                    list: {},
                    label: {}
                };
            } else {
                this.id = content_type.id;
                this.name = content_type.name;
                this.plural_name = content_type.plural_name;
                this.show_in_nav = content_type.show_in_nav;
                this.proxy_field = content_type.proxy_field;
                this.templates = content_type.templates;
                for (let x = 0; x < content_type.fields.length; x++) {
                    this.add_field(x, content_type.fields[x])
                }
            }
        } else {
            console.log('div for new content type does not exist!');
        }
    }

    add_field(index=null, field) {
        if (!(this.fields === undefined)) {
            let new_f_index = index;
            if (index == null) { new_f_index = this.fields.length; }
            if (new_f_index == 0) { this.f_div.html(''); }
            let new_f_div_id = `ct${this.index}-f${new_f_index}`;

            let field_type_display = '';
            switch(field.type) {
                case 'cross_reference':
                    field_type_display = field.cross_reference_type;
                    break;
                default:
                    field_type_display = FIELD_TYPE_LABELS[field.type];
                    break;
            }

            let indexed_display = field.indexed ? 'Y' : 'N';
            if (field.indexed_with.length > 0) {
                indexed_display += '['
                for (let x = 0; x < field.indexed_with.length; x ++) {
                    indexed_display += field.indexed_with[x] + ', ';
                }
                indexed_display = indexed_display.slice(0, -2) + ']';
            }

            let unique_display = field.unique ? 'Y' : 'N';
            if (field.unique_with.length > 0) {
                unique_display += '['
                for (let x = 0; x < field.unique_with.length; x ++) {
                    unique_display += field.unique_with[x] + ', ';
                }
                unique_display = unique_display.slice(0, -2) + ']';
            }

            this.f_div.append(`
                <tr id="${new_f_div_id}-row">
                    <td id="${new_f_div_id}-name" class="font-weight-bold">${field.name}</td>
                    <td id="${new_f_div_id}-label">${field.label}</td>
                    <td id="${new_f_div_id}-type">${field_type_display}</td>
                    <td id="${new_f_div_id}-in-lists">${field.in_lists ? 'Y' : 'N'}</td>
                    <td id="${new_f_div_id}-indexed">${indexed_display}</td>
                    <td id="${new_f_div_id}-unique">${unique_display}</td>
                    <td id="${new_f_div_id}-multiple">${field.multiple ? 'Y' : 'N'}</td>
                    <td id="${new_f_div_id}-actions">
                        <div class="d-flex flex-wrap flex-row-reverse">
                            <button type="button" class="btn btn-sm btn-primary m-1" id="${new_f_div_id}-edit-button"><span class="fas fa-edit"></span></button>
                            <button type="button" class="btn btn-sm btn-primary m-1" id="${new_f_div_id}-template-button"><span class="fas fa-file-code"></span></button>
                            <button type="button" class="btn btn-sm btn-danger m-1" id="${new_f_div_id}-delete-button"><span class="fas fa-trash-alt"></span></button>
                            <button type="button" class="btn btn-sm btn-danger m-1" id="${new_f_div_id}-shift-up-button"><span class="fas fa-caret-up"></span></button>
                        </div>
                    </td>
                </tr>
            `);

            this.fields.push(
                new Field(this.name, new_f_div_id, this.corpus_id, field)
            );
            let sender = this;

            // EDIT FIELD BUTTON CLICK
            $(`#${new_f_div_id}-edit-button`).click(function() {
                $('#new-f-modal-label').html('Edit Field');
                $('#new-f-ct-id').val(sender.index);
                $('#new-f-f-id').val(new_f_index);
                $('#new-f-action').val('edit');
                $('#new-f-name-box').val(sender.fields[new_f_index].name);
                $('#new-f-name-box').prop('disabled', true);
                $('#new-f-label-box').val(sender.fields[new_f_index].label);
                $('#new-f-type-box').val(sender.fields[new_f_index].type);
                if(sender.fields[new_f_index].type == 'cross_reference') {
                    $('#new-f-cross-reference-box').removeClass('d-none');
                    $('#new-f-cross-reference-box').val(sender.fields[new_f_index].cross_reference_type);
                } else {
                    $('#new-f-cross-reference-box').addClass('d-none');
                }

                $('.f-with').html('');
                for (let x = 0; x < sender.fields.length; x++) {
                    if (sender.fields[x].name != field.name) {
                        $('.f-with').append(`
                            <option value='${sender.fields[x].name}'>${sender.fields[x].label}</option>
                        `);
                    }
                }

                $('#new-f-indexed-checkbox').prop('checked', sender.fields[new_f_index].indexed);
                $('#new-f-indexed-with-box').val(sender.fields[new_f_index].indexed_with);
                if (sender.fields[new_f_index].indexed) {
                    $('#new-f-indexed-with-div').addClass('d-flex');
                    $('#new-f-indexed-with-div').removeClass('d-none');
                } else {
                    $('#new-f-indexed-with-div').removeClass('d-flex');
                    $('#new-f-indexed-with-div').addClass('d-none');
                }

                $('#new-f-unique-checkbox').prop('checked', sender.fields[new_f_index].unique);
                $('#new-f-unique-with-box').val(sender.fields[new_f_index].unique_with);
                if (sender.fields[new_f_index].unique) {
                    $('#new-f-unique-with-div').addClass('d-flex');
                    $('#new-f-unique-with-div').removeClass('d-none');
                } else {
                    $('#new-f-unique-with-div').removeClass('d-flex');
                    $('#new-f-unique-with-div').addClass('d-none');
                }

                $('#new-f-in-lists-checkbox').prop('checked', sender.fields[new_f_index].in_lists);
                $('#new-f-multiple-checkbox').prop('checked', sender.fields[new_f_index].multiple);
                $('#new-f-create-button').html('Edit');
                $('#new-f-modal').modal();
            });

            // FIELD TEMPLATE BUTTON CLICK
            $(`#${new_f_div_id}-template-button`).click(function() {
                console.log("Edit HTML:");
                console.log(sender.fields[new_f_index].default_template('edit').html);
                console.log("Edit JS:");
                console.log(sender.fields[new_f_index].default_template('edit').js);
                console.log("View HTML:");
                console.log(sender.fields[new_f_index].default_template('view').html);
                console.log("View JS:");
                console.log(sender.fields[new_f_index].default_template('view').js);
                console.log("List HTML:");
                console.log(sender.fields[new_f_index].default_template('list').html);
                console.log("List JS:");
                console.log(sender.fields[new_f_index].default_template('list').js);
            });

            // FIELD DELETE BUTTON CLICK
            $(`#${new_f_div_id}-delete-button`).click(function() {
                $('#confirmation-ct-index').val(sender.index);
                $('#confirmation-ct-name').val(sender.name);
                $('#confirmation-field-index').val(new_f_index);
                $('#confirmation-field-name').val(sender.fields[new_f_index].name);
                $('#confirmation-action').val('delete');
                $('#confirmation-confirm-button').attr('disabled', false);

                let message = `You are attempting to delete the <b>${sender.name} -> ${sender.fields[new_f_index].name}</b> field.
                Upon doing so, <b>all content stored in this field will be irreversibly deleted</b>. Some templates may also need to be
                regenerated or manually adjusted. Are you sure you want to proceed?`;

                if (sender.fields.length == 1) {
                    message = `You are attempting to delete the <b>${sender.name} -> ${sender.fields[new_f_index].name}</b> field.
                    This is currently not possible, as all content types must have at least one field. Please create another field for
                    this content type before deleting this field.`;
                    $('#confirmation-confirm-button').attr('disabled', true);
                }

                $('#confirmation-modal-message').html(message);
                $('#confirmation-modal').modal();
            });

            // FIELD SHIFT UP BUTTON
            $(`#${new_f_div_id}-shift-up-button`).click(function() {
                $('#confirmation-ct-index').val(sender.index);
                $('#confirmation-ct-name').val(sender.name);
                $('#confirmation-field-index').val(new_f_index);
                $('#confirmation-field-name').val(sender.fields[new_f_index].name);
                $('#confirmation-action').val('shift_up');
                $('#confirmation-confirm-button').attr('disabled', false);

                let message = `You are attempting to shift the <b>${sender.name} -> ${sender.fields[new_f_index].name}</b> field up
                in position. This will affect the order in which fields appear in lists, views, etc. Are you sure you want to proceed?`;

                if (new_f_index == 0) {
                    message = `You are attempting to shift the <b>${sender.name} -> ${sender.fields[new_f_index].name}</b> field up
                    in position. This is currently not possible, as that field already occupies the first position.`;
                    $('#confirmation-confirm-button').attr('disabled', true);
                }

                $('#confirmation-modal-message').html(message);
                $('#confirmation-modal').modal();
            });
        }
    }

    default_template(template_type) {
        let header_label = `{{ ${this.name}.label|safe|default:'Create New' }}`;
        let responsive_class = '';

        if (template_type == 'list') {
            header_label = this.plural_name;
            responsive_class = 'table-responsive';
        }

        let template = `
            {% load static %}
            {% load extras %}
            <div id="content-template" class="content-template ${this.name}-${template_type} card mt-4">
                <div class="card-header">
                    <h2>${header_label}</h2>
                </div>
                <div class="card-body ${responsive_class}">
        `;
        let javascript = '';

        let default_templates = this.fields.map(x => x.default_template(template_type));
        let field_scripts = '';
        let field_templates = '';
        for (let x = 0; x < default_templates.length; x++) {
            field_templates += default_templates[x].html;
            field_scripts += default_templates[x].js;
        }

        if (template_type == 'view') {
            template += `
                <div class="row">
                    <div class="col">
                        <div class="${this.name} mb-3">
                            ${field_templates}
                            <a href="/edit/${this.name}/{{ ${this.name}.id }}/" role="button" class="btn btn-sm btn-secondary"><span class="fas fa-edit"></span></a>
                        </div>
                    </div>
                </div>
            `;
        } else if (template_type == 'list') {
            template += `
                <!-- SEARCH / PAGING CONTROLS /-->
                <div class="mb-3 d-flex">
                    <div class="flex-grow-1">
                        <input type="text" class="form-control" id="${this.name}-filter-box" aria-placeholder="Search" placeholder="Search">
                    </div>
                    
                    <div class="ml-2 flex-nowrap align-self-center">
                        <span class="${this.name}-start-record">1</span>-<span class="${this.name}-end-record">50</span> out of <span class="${this.name}-total-records">100</span>
                    </div>
                    
                    <div class="ml-2 flex-nowrap form-inline">
                        <button type="button" class="btn btn-primary ${this.name}-prev-page-button"><span class="fas fa-angle-left"></span></button>
                        <select class="form-control ${this.name}-page-selector"></select>
                        <button type="button" class="btn btn-primary ${this.name}-next-page-button"><span class="fas fa-angle-right"></span></button>
                    </div>
                </div>
                <table id="${this.name}-list-table" class="table table-striped">
                    <thead class="thead-dark">
                        <th scope="col" class="list-field-header"></th>
            `;

            let header_counter = 0;
            let only_string = 'id';
            let toolbars = '';
            let toolbar_initiators = '';
            for (let x = 0; x < this.fields.length; x++) {
                if (this.fields[x].in_lists) {
                    template += `
                        <th scope="col" id="${this.name}-${this.fields[x].name}-table-header" class="list-field-header">
                            ${this.fields[x].label}
                            <button id="${this.name}-${this.fields[x].name}-table-settings" type="button" class="btn btn-sm text-white" data-toggle="popover"><span class="fas fa-sliders-h"></span></button>
                        </th>
                    `;

                    toolbars += `<div id="${this.name}-${this.fields[x].name}-toolbar" class="d-none">`;

                    if (this.fields[x].cross_reference_type) {
                        toolbars += `
                            <a role="button" href="javascript:${this.name}_select_xref_filter('${this.fields[x].name}', '${this.fields[x].cross_reference_type}');" class="btn btn-sm btn-secondary">Filter</a>
                        `;
                    } else if(this.fields[x].type == 'number') {
                        toolbars += `
                            <div id="${this.name}-${this.fields[x].name}-range" style="width: 250px;"></div><br />
                            <span id="${this.name}-${this.fields[x].name}-range-label"></span>
                            <button type="button" id="${this.name}-${this.fields[x].name}-apply-button" class="btn btn-sm btn-secondary">Apply Filter</button>
                        `;
                    }

                    toolbars += `<a role="button" id="${this.name}-${this.fields[x].name}-sort-button" href="javascript:sort_${this.name}_table('${this.fields[x].name}');" class="btn btn-sm btn-secondary">Sort <span class="fas fa-sort-amount-up"></span></a></div>`;

                    toolbar_initiators += `
                        $('#${this.name}-${this.fields[x].name}-table-settings').popover({
                            placement: 'top',
                            html: true,
                            sanitize: false,
                            title: 'Field Options',
                            template: '<div class="popover" role="tooltip"><div class="arrow"></div><h3 id="${this.name}-${this.fields[x].name}-popover-header" class="popover-header"></h3><div id="${this.name}-${this.fields[x].name}-popover" class="popover-body"></div></div>',
                        });
                        $('#${this.name}-${this.fields[x].name}-table-settings').on('shown.bs.popover', function() {
                            let toolbar = $('#${this.name}-${this.fields[x].name}-toolbar').detach();
                            toolbar.appendTo('#${this.name}-${this.fields[x].name}-popover');
                            toolbar.removeClass('d-none');
                            $('#${this.name}-${this.fields[x].name}-table-settings').popover('update');
                        });
                        $('#${this.name}-${this.fields[x].name}-table-settings').on('hide.bs.popover', function() {
                            let toolbar = $('#${this.name}-${this.fields[x].name}-toolbar').detach();
                            toolbar.appendTo($(document.body));
                            toolbar.addClass('d-none');
                        });
                    `;

                    if (this.fields[x].type == 'number') {
                        toolbar_initiators += `
                        $('#${this.name}-${this.fields[x].name}-range').slider({
                            range: true,
                            min: ${this.name}_field_stats.${this.fields[x].name}.min,
                            max: ${this.name}_field_stats.${this.fields[x].name}.max,
                            values: [${this.name}_field_stats.${this.fields[x].name}.min, ${this.name}_field_stats.${this.fields[x].name}.max],
                            slide: function(event, ui) {
                                $('#${this.name}-${this.fields[x].name}-range-label').html(ui.values[ 0 ] + " - " + ui.values[ 1 ]);
                            }
                        });
                        $('#${this.name}-${this.fields[x].name}-range-label').html($("#${this.name}-${this.fields[x].name}-range").slider("values", 0) + " - " + $("#${this.name}-${this.fields[x].name}-range").slider("values", 1));
                        $('#${this.name}-${this.fields[x].name}-apply-button').click(function() {
                            let range_lower = $("#${this.name}-${this.fields[x].name}-range").slider("values", 0);
                            let range_higher = $("#${this.name}-${this.fields[x].name}-range").slider("values", 1);
                            let range_filter = '[' + range_lower + ' TO ' + range_higher + ']';
                            ${this.name}_params['${this.fields[x].name}'] = range_filter;
                            ${this.name}_params.current_page = 1;
                            ${this.name}_apply_field_settings('${this.fields[x].name}');
                        });
                        `;
                    }

                    only_string += ',' + this.fields[x].name;
                    header_counter ++;
                }
            }

            template += `
                    </thead>
                    <tbody id="${this.name}-table-body">
                        <tr><td colspan="${header_counter + 1}">Loading...</td></tr>
                    </tbody>
                </table>
                ${toolbars}
                <!-- PAGING CONTROLS /-->
                <div class="float-right">
                    <button type="button" class="btn btn-sm btn-primary ${this.name}-prev-page-button"><span class="fas fa-angle-left"></span></button>
                    <select class="form-control-sm ${this.name}-page-selector" style="display: inline-flex;"></select>
                    <button type="button" class="btn btn-sm btn-primary ${this.name}-next-page-button"><span class="fas fa-angle-right"></span></button>
                </div>
                <div>
                    <a role="button" href="/edit/${this.name}/new/" class="btn btn-primary">Create</a>
                </div>
            `;



            field_scripts = `
                var ${this.name}_params = {
                    current_page: 1,
                    page_size: 50,
                    query: {},
                    search: '',
                    sort: [],
                    render_template: 'list',
                    only: '${only_string}',
                }
                var ${this.name}_first_load = true;
                var ${this.name}_timer;
                var ${this.name}_filtering_field = '';
                var ${this.name}_field_stats = {};
            
                $(document).ready(function() {
                    //determine_${this.name}_field_sizes();
                    ${this.name}_load_table();
                    
                    $('#${this.name}-filter-box').on('input', function(e){
                        clearTimeout(${this.name}_timer);
                        ${this.name}_timer = setTimeout(function() {
                            ${this.name}_params.search = $('#${this.name}-filter-box').val() + '*';
                            ${this.name}_params.current_page = 1;
                            ${this.name}_params.sort = [];
                            ${this.name}_load_table();
                        }, 1200);
                    });
                    
                    $('.${this.name}-prev-page-button').click(function() {
                        ${this.name}_params.current_page -= 1;
                        ${this.name}_load_table();
                    });
                    
                    $('.${this.name}-next-page-button').click(function() {
                        ${this.name}_params.current_page += 1;
                        ${this.name}_load_table();
                    });
                    
                    $('.${this.name}-page-selector').change(function() {
                        ${this.name}_params.current_page = parseInt(this.value);
                        ${this.name}_load_table();
                    });
                    
                    $.get('/stats/${this.name}/', function(data) {
                        ${this.name}_field_stats = data;
                        ${toolbar_initiators}
                    });
                });
                
                function ${this.name}_load_table() {
                    let table_body = $('#${this.name}-table-body');
                    let get_params = Object.assign({}, ${this.name}_params);
                    
                    if (typeof ${this.name}_initial_params !== 'undefined' && ${this.name}_first_load) {
                        get_params = Object.assign(get_params, ${this.name}_initial_params);
                        ${this.name}_first_load = false;
                    }
                    
                    get_params.sort = get_params.sort.join(',');
                    //get_params.search = encodeURI(get_params.search);
                    $.get('/api/corpus/${this.corpus_id}/type/${this.name}/', get_params, function(data){
                        $('#${this.name}-table-body').html('');
                        let meta = data.meta;
                        for (let x = 0; x < data.data.length; x++) {
                            let row_html = '<tr>';
                            row_html += '<td><a href="/corpus/${corpus_id}/type/${this.name}/view/' + data.data[x].id + '/" class="content-open-link" target="_blank"><span class="fas fa-external-link-square-alt"></span></a></td>';
                            for (const field in data.data[x].fields) {
                                row_html += data.data[x].fields[field]['_template'];
                            }
                            table_body.append(row_html + '</tr>');
                        }
                        
                        if (meta) {
                            let prev_button = $('.${this.name}-prev-page-button');
                            let next_button = $('.${this.name}-next-page-button');
                            let page_selector = $('.${this.name}-page-selector');
                        
                            let total = meta['count'];
                            let page_size = meta['page_size'];
                            let total_pages = Math.ceil(total / page_size);
                            let current_page = meta['current_page'];
                            let start_record = 1 + ((current_page - 1) * page_size);
                            let end_record = current_page * page_size;
                            let has_next = meta['has_next_page'];
                            
                            if (end_record > total) { end_record = total; }
                            if (current_page > 1) { prev_button.prop('disabled', false); } else { prev_button.prop('disabled', true); }
                            if (current_page < total_pages) { next_button.prop('disabled', false); } else { next_button.prop('disabled', true); }
                            
                            page_selector.html('');
                            for (let x = 1; x < total_pages + 1; x++) {
                                let option = '<option';
                                if (x == current_page) { option += ' selected'; }
                                option += '>' + x.toString() + '</option>';
                                page_selector.append(option);
                            }
                            
                            $('.${this.name}-start-record').html(start_record);
                            $('.${this.name}-end-record').html(end_record);
                            $('.${this.name}-total-records').html(total);
                        }
                    });
                }
                
                function sort_${this.name}_table(field) {
                    let asc_field_index = ${this.name}_params.sort.indexOf('+' + field);
                    let desc_field_index = ${this.name}_params.sort.indexOf('-' + field);
                    
                    if (asc_field_index !== -1) {
                        ${this.name}_params.sort[asc_field_index] = '-' + field;
                        $('#${this.name}-' + field + '-sort-button').html('Sort <span class="fas fa-sort-amount-up"></span>');
                    } else if (desc_field_index !== -1) {
                        ${this.name}_params.sort[desc_field_index] = '+' + field;
                        $('#${this.name}-' + field + '-sort-button').html('Sort <span class="fas fa-sort-amount-down"></span>');
                    } else {
                        ${this.name}_params.sort.push('+' + field);
                        $('#${this.name}-' + field + '-sort-button').html('Sort <span class="fas fa-sort-amount-down"></span>');
                    }
                    ${this.name}_page = 1;
                    ${this.name}_apply_field_settings(field);
                }
                
                function ${this.name}_select_xref_filter(field, content_type) {
                    ${this.name}_filtering_field = field;
                    $('#${this.name}-' + field + '-table-settings').popover('hide');
                    select_content(content_type, ${this.name}_apply_xref_filter);
                }
                
                function ${this.name}_apply_xref_filter(id, label) {
                    ${this.name}_params[${this.name}_filtering_field] = label;
                    ${this.name}_params.current_page = 1;
                    ${this.name}_apply_field_settings(${this.name}_filtering_field);
                }
                
                function ${this.name}_apply_field_settings(field) {
                    if (!$('#${this.name}-' + field + '-reset-button').length) {
                        $('#${this.name}-' + field + '-toolbar').append('<a role="button" id="${this.name}-' + field + '-reset-button" href="javascript:${this.name}_reset_field_settings(\\'' + field + '\\');" class="btn btn-sm btn-danger ml-1">Reset</a>');
                        $('#${this.name}-' + field + '-table-settings').removeClass('text-white');
                        $('#${this.name}-' + field + '-table-settings').addClass('text-info');
                    }
                    $('#${this.name}-' + field + '-table-settings').popover('hide');
                    ${this.name}_load_table();
                }
                
                function ${this.name}_reset_field_settings(field) {
                    let asc_field_index = ${this.name}_params.sort.indexOf('+' + field);
                    let desc_field_index = ${this.name}_params.sort.indexOf('-' + field);
                    
                    if (asc_field_index !== -1) {
                        ${this.name}_params.sort.splice(asc_field_index, 1);
                    } else if (desc_field_index !== -1) {
                        ${this.name}_params.sort.splice(desc_field_index, 1);
                    }
                    
                    delete ${this.name}_params[field];
                    ${this.name}_params.current_page = 1;
                
                    $('#${this.name}-' + field + '-reset-button').remove();
                    $('#${this.name}-' + field + '-table-settings').removeClass('text-info');
                    $('#${this.name}-' + field + '-table-settings').addClass('text-white');
                    $('#${this.name}-' + field + '-table-settings').popover('hide');
                    ${this.name}_load_table();
                }
            `;
        } else if (template_type == 'edit') {
            template += `
                <div class="row">
                    <div class="col">
                        <form id="${this.name}-form" class="edit-form ${this.name}-form" method="post">
                            {% csrf_token %}
                            <input type="hidden" name="content_type" value="${this.name}">
                            <input type="hidden" name="id" value="{{ ${this.name}.id }}">
            `;

            for (let x = 0; x < default_templates.length; x++) {
                template += `
                            <div class="edit-field">
                                ${default_templates[x].html}
                            </div>
                `;
            }

            template += `
                            <div class="form-group">
                                {% if popup %}
                                    <button class="btn btn-primary" id="${this.name}-form-submit-button">Save</button>
                                {% else %}
                                    <button type="submit" class="btn btn-primary" id="${this.name}-form-submit-button">Save</button>
                                {% endif %}
                            </div>
                        </form>
                    </div>
                </div>
            `;

            field_scripts += `
                {% if popup %}
                $(document).ready(function() {
                    window.resizeTo(450, 400);
                });
                {% endif %}
            `;
        } else if (template_type == 'label') {
            if (this.fields.length > 0) {
                if (this.fields[0].type == 'cross_reference') {
                    template = `{{ ${this.name}.fields.${this.fields[0].name}.value.label }}`;
                } else {
                    template = `{{ ${this.name}.fields.${this.fields[0].name}.value }}`;
                }
            } else {
                template = `${this.name}`;
            }
        }

        if (template_type != 'label') {
            template += `
                    </div>
                </div>
            `;
            template = html_beautify(template);
        }

        if (field_scripts.trim()) {
            let field_types = this.fields.map(x => x.type);
            let additional_scripts = '';
            if (template_type == 'edit') {
                if (field_types.includes('html')) {
                    additional_scripts += `<script src="{% static 'js/tinymce/tinymce.min.js' %}"></script>`;
                }
            }
            javascript += `
                {% load static %}
                {% load extras %}
                ${additional_scripts}
                <script type='application/javascript'>
                    ${field_scripts}
                </script>
            `;
        }

        return {
            html: template,
            js: javascript
        };
    }

    to_object() {
        for (let template in this.templates) {
            if ($.isEmptyObject(this.templates[template])) {
                this.templates[template] = this.default_template(template);
            }
        }

        this.templates['field_templates'] = {};
        this.fields.map(x => this.templates['field_templates'][x.name] = x.default_template('list').html);
        if(!this.proxy_field){this.proxy_field = '';}

        return {
            id: this.id,
            name: this.name,
            plural_name: this.plural_name,
            show_in_nav: this.show_in_nav,
            proxy_field: this.proxy_field,
            templates: this.templates,
            fields: this.fields.map(x => x.to_object())
        }
    }
}

class Field {
    constructor(ct_name, div_id, corpus_id, field={}) {
        this.corpus_id = corpus_id;
        if ($(`#${div_id}-row`).length) {
            this.div_id = div_id;
            this.ct_name = ct_name;

            if ($.isEmptyObject(field)) {
                this.name = 'NewField';
                this.label = 'New Field';
                this.in_lists = true;
                this.indexed = false;
                this.indexed_with = [];
                this.unique = false;
                this.unique_with = [];
                this.multiple = false;
                this.type = 'text';
                this.choices = [];
                this.cross_reference_type = '';
                this.views = {};
            } else {
                this.name = field.name;
                this.label = field.label;
                this.in_lists = field.in_lists;
                this.indexed = field.indexed;
                this.indexed_with = field.indexed_with;
                this.unique = field.unique;
                this.unique_with = field.unique_with;
                this.multiple = field.multiple;
                this.type = field.type;
                this.choices = field.choices;
                this.cross_reference_type = field.cross_reference_type;
                this.views = field.views;
            }
        } else {
            console.log('div for new field does not exist!');
        }
    }

    edit(field) {
        if(!$.isEmptyObject(field)) {
            this.name = field.name;
            this.label = field.label;
            this.in_lists = field.in_lists;
            this.indexed = field.indexed;
            this.indexed_with = field.indexed_with;
            this.unique = field.unique;
            this.unique_with = field.unique_with;
            this.multiple = field.multiple;
            this.type = field.type;
            this.cross_reference_type = field.cross_reference_type;

            let field_type_display = '';
            switch(this.type) {
                case 'cross_reference':
                    field_type_display = this.cross_reference_type;
                    break;
                default:
                    field_type_display = FIELD_TYPE_LABELS[this.type];
                    break;
            }

            let indexed_display = field.indexed ? 'Y' : 'N';
            if (this.indexed_with.length > 0) {
                indexed_display += '['
                for (let x = 0; x < this.indexed_with.length; x ++) {
                    indexed_display += this.indexed_with[x] + ', ';
                }
                indexed_display = indexed_display.slice(0, -2) + ']';
            }

            let unique_display = this.unique ? 'Y' : 'N';
            if (this.unique_with.length > 0) {
                unique_display += '['
                for (let x = 0; x < this.unique_with.length; x ++) {
                    unique_display += this.unique_with[x] + ', ';
                }
                unique_display = unique_display.slice(0, -2) + ']';
            }

            $(`#${this.div_id}-name`).html(this.name);
            $(`#${this.div_id}-label`).html(this.label);
            $(`#${this.div_id}-type`).html(field_type_display);
            $(`#${this.div_id}-indexed`).html(indexed_display);
            $(`#${this.div_id}-unique`).html(unique_display);
            $(`#${this.div_id}-in-lists`).html(this.in_lists ? 'Y' : 'N');
            $(`#${this.div_id}-multiple`).html(this.multiple ? 'Y' : 'N');
        }
    }

    default_template(template_type) {
        let template = '';
        let javascript = '';
        switch(this.type) {
            // ----------- //
            // TEXT TYPE   //
            // ----------- //
            case "text":
                if (template_type == "edit") {
                    if (this.multiple) {
                        template = `
                            <label class="edit-field-label ${this.ct_name}-${this.name}-label">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                            <div class="ml-2 mb-2">
                                <div id="${this.ct_name}-${this.name}-values">
                                    {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                        <div id="${this.ct_name}-${this.name}-{{ forloop.counter0 }}" class="form-group mb-2">
                                            <div class="row">
                                                <div class="col-11">
                                                    <input type="text" class="form-control ${this.ct_name}-${this.name}-value" name="${this.ct_name}-${this.name}-{{ forloop.counter0 }}" value="{{ ${this.name}|safe|default:'' }}">
                                                </div>
                                                <div class="col-1">
                                                    <a href="javascript:${this.ct_name}_${this.name}_remove_value({{ forloop.counter0 }});" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a>
                                                </div>
                                            </div>
                                        </div>
                                    {% endfor %}
                                </div>
                                <button type="button" class="btn btn-sm btn-secondary" id="${this.ct_name}-${this.name}-add-button">+</button>
                            </div>
                        `;

                        javascript = `
                            $(document).ready(function() {
                                $('#${this.ct_name}-${this.name}-add-button').click(function() {
                                    let count = 0;
                                    $('.${this.ct_name}-${this.name}-value').each(function() {
                                        count += 1;
                                    });
                                    let new_field_value_name = '${this.ct_name}-${this.name}-' + count.toString();
                                    $('#${this.ct_name}-${this.name}-values').append('<div id="' + new_field_value_name + '" class="form-group mb-2"><div class="row"><div class="col-11"><input type="text" class="form-control ${this.ct_name}-${this.name}-value" name="' + new_field_value_name + '"></div><div class="col-1"><a href="javascript:${this.ct_name}_${this.name}_remove_value(' + count.toString() + ');" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a></div></div></div>');
                                });
                            });
                            
                            function ${this.ct_name}_${this.name}_remove_value(index) {
                                $('#${this.ct_name}-${this.name}-' + index.toString()).remove();
                            }
                        `;
                    } else {
                        template = `
                            <div class="form-group">
                                <label class="edit-field-label ${this.ct_name}-${this.name}-label" for="${this.ct_name}-${this.name}">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                                <input type="text" class="form-control" id="${this.ct_name}-${this.name}" name="${this.ct_name}-${this.name}" value="{{ ${this.ct_name}.fields.${this.name}.value|safe|default:'' }}">
                            </div>
                        `;
                    }
                } else if (template_type == "list" && this.in_lists) {
                    let display = `{{ ${this.ct_name}.fields.${this.name}.value|safe }}`;
                    if (this.multiple) {
                        display = `
                            {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                {{ ${this.name}|safe }}{% if not forloop.last %}, {% endif %}
                            {% endfor %}
                        `;
                    }

                    template = `
                        <td class="${this.ct_name}-${this.name} list-field">
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                                ${display}
                            {% endif %}
                        </td>
                    `;
                } else {
                    if (this.multiple) {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    {% if not forloop.first %}
                                        <div class="col-2">&nbsp;</div>
                                    {% endif %}
                                    <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                        {{ ${this.name}|safe }}
                                    </div>
                                {% endfor %}
                            </div>
                            {% endif %}
                        `;
                    }
                    else {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                    {{ ${this.ct_name}.fields.${this.name}.value|safe }}
                                </div>
                            </div>
                            {% endif %}
                        `;
                    }
                }
                break;
            // ----------- //
            // HTML TYPE   //
            // ----------- //
            case "html":
                if (template_type == "edit") {
                    if (this.multiple) {
                        template = `
                            <label class="edit-field-label ${this.ct_name}-${this.name}-label">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                            <div class="ml-2 mb-2">
                                <div id="${this.ct_name}-${this.name}-values">
                                    {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                        <div id="${this.ct_name}-${this.name}-{{ forloop.counter0 }}" class="form-group mb-2">
                                            <div class="row">
                                                <div class="col-11">
                                                    <textarea class="form-control ${this.ct_name}-${this.name}-value html-field" name="${this.ct_name}-${this.name}-{{ forloop.counter0 }}">
                                                        {{ ${this.name} }}
                                                    </textarea>
                                                </div>
                                                <div class="col-1">
                                                    <a href="javascript:${this.ct_name}_${this.name}_remove_value({{ forloop.counter0 }});" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a>
                                                </div>
                                            </div>
                                        </div>
                                    {% endfor %}
                                </div>
                                <button type="button" class="btn btn-sm btn-secondary" id="${this.ct_name}-${this.name}-add-button">+</button>
                            </div>
                        `;

                        javascript = `
                            $(document).ready(function() {
                                tinymce.init({selector: '.html-field'});
                            
                                $('#${this.ct_name}-${this.name}-add-button').click(function() {
                                    let count = 0;
                                    $('.${this.ct_name}-${this.name}-value').each(function() {
                                        count += 1;
                                    });
                                    let new_field_value_name = '${this.ct_name}-${this.name}-' + count.toString();
                                    $('#${this.ct_name}-${this.name}-values').append('<div id="' + new_field_value_name + '" class="form-group mb-2"><div class="row"><div class="col-11"><textarea class="form-control ${this.ct_name}-${this.name}-value html-field" name="' + new_field_value_name + '"></textarea></div><div class="col-1"><a href="javascript:${this.ct_name}_${this.name}_remove_value(' + count.toString() + ');" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a></div></div></div>');
                                    tinymce.init({selector: '.html-field'});
                                });
                            });
                            
                            function ${this.ct_name}_${this.name}_remove_value(index) {
                                $('#${this.ct_name}-${this.name}-' + index.toString()).remove();
                            }
                        `;
                    } else {
                        template = `
                            <div class="form-group">
                                <label class="edit-field-label ${this.ct_name}-${this.name}" for="${this.ct_name}-${this.name}">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                                <textarea id="${this.ct_name}-${this.name}" class="${this.ct_name}-${this.name}-editor html-field" name="${this.ct_name}-${this.name}">
                                    {% if ${this.ct_name}.fields.${this.name}.value %}{{ ${this.ct_name}.fields.${this.name}.value|safe }}{% endif %}
                                </textarea>
                            </div>
                        `;

                        javascript = `
                            $(document).ready(function() {
                                tinymce.init({selector: '#${this.ct_name}-${this.name}'});
                            });
                        `;
                    }
                } else if (template_type == "list" && this.in_lists) {
                    let display = `{{ ${this.ct_name}.fields.${this.name}.value|safe }}`;
                    if (this.multiple) {
                        display = `
                            {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                {{ ${this.name} }}|safe{% if not forloop.last %}, {% endif %}
                            {% endfor %}
                        `;
                    }

                    template = `
                        <td class="${this.ct_name}-${this.name} list-field">
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                                ${display}
                            {% endif %}
                        </td>
                    `;
                } else {
                    if (this.multiple) {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    {% if not forloop.first %}
                                        <div class="col-2">&nbsp;</div>
                                    {% endif %}
                                    <div class="col-10 d-flex flex-column align-left ${this.ct_name}-${this.name}">
                                        {% autoescape off %}{{ ${this.name} }}{% endautoescape %}
                                    </div>
                                {% endfor %}
                            </div>
                            {% endif %}
                        `;
                    } else {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                <div class="col-10 d-flex flex-column align-left view-field-value ${this.ct_name}-${this.name}-value">
                                    {% autoescape off %}{{ ${this.ct_name}.fields.${this.name}.value }}{% endautoescape %}
                                </div>
                            </div>
                            {% endif %}
                        `;
                    }
                }
                break;
            // ----------- //
            // NUMBER TYPE   //
            // ----------- //
            case "number":
                if (template_type == "edit") {
                    if (this.multiple) {
                        template = `
                            <label class="edit-field-label ${this.ct_name}-${this.name}-label">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                            <div class="ml-2 mb-2">
                                <div id="${this.ct_name}-${this.name}-values">
                                    {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                        <div id="${this.ct_name}-${this.name}-{{ forloop.counter0 }}" class="form-group mb-2">
                                            <div class="row">
                                                <div class="col-11">
                                                    <input type="number" class="form-control ${this.ct_name}-${this.name}-value" name="${this.ct_name}-${this.name}-{{ forloop.counter0 }}" value="{{ ${this.name}|default:'' }}">
                                                </div>
                                                <div class="col-1">
                                                    <a href="javascript:${this.ct_name}_${this.name}_remove_value({{ forloop.counter0 }});" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a>
                                                </div>
                                            </div>
                                        </div>
                                    {% endfor %}
                                </div>
                                <button type="button" class="btn btn-sm btn-secondary" id="${this.ct_name}-${this.name}-add-button">+</button>
                            </div>
                        `;

                        javascript = `
                            $(document).ready(function() {
                                $('#${this.ct_name}-${this.name}-add-button').click(function() {
                                    let count = 0;
                                    $('.${this.ct_name}-${this.name}-value').each(function() {
                                        count += 1;
                                    });
                                    let new_field_value_name = '${this.ct_name}-${this.name}-' + count.toString();
                                    $('#${this.ct_name}-${this.name}-values').append('<div id="' + new_field_value_name + '" class="form-group mb-2"><div class="row"><div class="col-11"><input type="number" class="form-control ${this.ct_name}-${this.name}-value" name="' + new_field_value_name + '"></div><div class="col-1"><a href="javascript:${this.ct_name}_${this.name}_remove_value(' + count.toString() + ');" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a></div></div></div>');
                                });
                            });
                            
                            function ${this.ct_name}_${this.name}_remove_value(index) {
                                $('#${this.ct_name}-${this.name}-' + index.toString()).remove();
                            }
                        `;
                    } else {
                        template = `
                            <div class="form-group">
                                <label class="edit-field-label ${this.ct_name}-${this.name}-label" for="${this.ct_name}-${this.name}">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                                <input type="number" class="form-control" id="${this.ct_name}-${this.name}" name="${this.ct_name}-${this.name}" value="{{ ${this.ct_name}.fields.${this.name}.value|default:'' }}">
                            </div>
                        `;
                    }
                } else if (template_type == "list" && this.in_lists) {
                    let display = `{{ ${this.ct_name}.fields.${this.name}.value }}`;
                    if (this.multiple) {
                        display = `
                            {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                {{ ${this.name} }}{% if not forloop.last %}, {% endif %}
                            {% endfor %}
                        `;
                    }

                    template = `
                        <td class="${this.ct_name}-${this.name} list-field">
                            {% if not ${this.ct_name}.fields.${this.name}.value == None %}
                                ${display}
                            {% endif %}
                        </td>
                    `;
                } else {
                    if (this.multiple) {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    {% if not forloop.first %}
                                        <div class="col-2">&nbsp;</div>
                                    {% endif %}
                                    <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                        {{ ${this.name} }}
                                    </div>
                                {% endfor %}
                            </div>
                            {% endif %}
                        `;
                    }
                    else {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                    {{ ${this.ct_name}.fields.${this.name}.value }}
                                </div>
                            </div>
                            {% endif %}
                        `;
                    }
                }
                break;
            // ----------- //
            // DATE TYPE   //
            // ----------- //
            case "date":
                if (template_type == "edit") {
                    if (this.multiple) {
                        template = `
                            <label class="edit-field-label ${this.ct_name}-${this.name}-label">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                            <div class="ml-2 mb-2">
                                <div id="${this.ct_name}-${this.name}-values">
                                    {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                        <div id="${this.ct_name}-${this.name}-{{ forloop.counter0 }}" class="form-group mb-2">
                                            <div class="row">
                                                <div class="col-11">
                                                    <input type="date" class="form-control ${this.ct_name}-${this.name}-value" name="${this.ct_name}-${this.name}-{{ forloop.counter0 }}" value="{{ ${this.name}|format_date:'%Y-%m-%d' }}">
                                                </div>
                                                <div class="col-1">
                                                    <a href="javascript:${this.ct_name}_${this.name}_remove_value({{ forloop.counter0 }});" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a>
                                                </div>
                                            </div>
                                        </div>
                                    {% endfor %}
                                </div>
                                <button type="button" class="btn btn-sm btn-secondary" id="${this.ct_name}-${this.name}-add-button">+</button>
                            </div>
                        `;

                        javascript = `
                            $(document).ready(function() {
                                $('#${this.ct_name}-${this.name}-add-button').click(function() {
                                    let count = 0;
                                    $('.${this.ct_name}-${this.name}-value').each(function() {
                                        count += 1;
                                    });
                                    let new_field_value_name = '${this.ct_name}-${this.name}-' + count.toString();
                                    $('#${this.ct_name}-${this.name}-values').append('<div id="' + new_field_value_name + '" class="form-group mb-2"><div class="row"><div class="col-11"><input type="date" class="form-control ${this.ct_name}-${this.name}-value" name="' + new_field_value_name + '"></div><div class="col-1"><a href="javascript:${this.ct_name}_${this.name}_remove_value(' + count.toString() + ');" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a></div></div></div>');
                                });
                            });
                            
                            function ${this.ct_name}_${this.name}_remove_value(index) {
                                $('#${this.ct_name}-${this.name}-' + index.toString()).remove();
                            }
                        `;
                    } else {
                        template = `
                            <div class="form-group">
                                <label class="edit-field-label ${this.ct_name}-${this.name}-label" for="${this.ct_name}-${this.name}">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                                <input type="date" class="form-control" id="${this.ct_name}-${this.name}" name="${this.ct_name}-${this.name}" value="{{ ${this.ct_name}.fields.${this.name}.value|format_date:'%Y-%m-%d' }}">
                            </div>
                        `;
                    }
                } else if (template_type == "list" && this.in_lists) {
                    let display = `{{ ${this.ct_name}.fields.${this.name}.value|format_date:'%m/%d/%Y' }}`;
                    if (this.multiple) {
                        display = `
                            {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                {{ ${this.name}|format_date:'%m/%d/%Y' }}{% if not forloop.last %}, {% endif %}
                            {% endfor %}
                        `;
                    }

                    template = `
                        <td class="${this.ct_name}-${this.name} list-field">
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                                ${display}
                            {% endif %}
                        </td>
                    `;
                } else {
                    if (this.multiple) {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    {% if not forloop.first %}
                                        <div class="col-2">&nbsp;</div>
                                    {% endif %}
                                    <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                        {{ ${this.name}|format_date:'%m/%d/%Y' }}
                                    </div>
                                {% endfor %}
                            </div>
                            {% endif %}
                        `;
                    }
                    else {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                    {{ ${this.ct_name}.fields.${this.name}.value|format_date:'%m/%d/%Y' }}
                                </div>
                            </div>
                            {% endif %}
                        `;
                    }
                }
                break;
            // ----------- //
            // FILE TYPE   //
            // ----------- //
            case "file":
                if (template_type == "edit") {
                    if (this.multiple) {
                        template = `
                            <label class="edit-field-label ${this.ct_name}-${this.name}-label">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                            <div class="ml-2 mb-2">
                                <div id="${this.ct_name}-${this.name}-values"></div>
                                <a href="javascript:select_file(${this.ct_name}_${this.name}_add_value);" role="button" class="btn btn-sm btn-secondary">+</a>
                            </div>
                        `;

                        javascript = `  
                            function ${this.ct_name}_${this.name}_remove_value(index) {
                                $('#${this.ct_name}-${this.name}-' + index.toString()).remove();
                            }
                            
                            function ${this.ct_name}_${this.name}_add_value(file) {
                                let index = $('.${this.ct_name}-${this.name}-value').length;
                                $('#${this.ct_name}-${this.name}-values').append('\
                                    <div id="${this.ct_name}-${this.name}-' + index + '" class="form-group mb-2 ${this.ct_name}-${this.name}-value">\
                                        <div class="row">\
                                            <div class="col-11">\
                                                <input type="hidden" name="${this.ct_name}-${this.name}-' + index + '" value="' + file + '">\
                                                <a href="' + file + '" target="_blank">' + file + '</a>\
                                            </div>\
                                            <div class="col-1">\
                                                <a href="javascript:${this.ct_name}_${this.name}_remove_value(' + index + ');" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a>\
                                            </div>\
                                        </div>\
                                    </div>\
                                ');
                            }
                            
                            $(document).ready(function() {
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    ${this.ct_name}_${this.name}_add_value('{{ ${this.name} }}');
                                {% endfor %}
                            });
                        `;
                    } else {
                        template = `
                            <div class="form-group">
                                <label class="edit-field-label ${this.ct_name}-${this.name}-label" for="${this.ct_name}-${this.name}">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                                <div class="row">
                                    <div class="col-12">
                                        <div class="input-group">
                                            <input type="text" class="form-control" id="${this.ct_name}-${this.name}" name="${this.ct_name}-${this.name}" value="{{ ${this.ct_name}.fields.${this.name}.value|default:'' }}">
                                            <span class="input-group-btn btn-sm ml-1"><a href="javascript:select_file(${this.ct_name}_${this.name}_add_value);" role="button" class="btn btn-sm btn-secondary">Select</a></span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;

                        javascript = `
                            function ${this.ct_name}_${this.name}_add_value(file) {
                                $('#${this.ct_name}-${this.name}').val(file);   
                            }
                        `;
                    }
                } else if (template_type == "list" && this.in_lists) {
                    let display = `<a href="{{ ${this.ct_name}.fields.${this.name}.value }}" target="_blank" download>{{ ${this.ct_name}.fields.${this.name}.value|get_basename }}</a>`;
                    if (this.multiple) {
                        display = `
                            {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                <a href="{{ ${this.name} }}" target="_blank" download>{{ ${this.name}|get_basename }}</a>{% if not forloop.last %}, {% endif %}
                            {% endfor %}
                        `;
                    }

                    template = `
                        <td class="${this.ct_name}-${this.name} list-field">
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                                ${display}
                            {% endif %}
                        </td>
                    `;
                } else {
                    if (this.multiple) {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    {% if not forloop.first %}
                                        <div class="col-2">&nbsp;</div>
                                    {% endif %}
                                    <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                        <a href="{{ ${this.name} }}" target="_blank" download>{{ ${this.name}|get_basename }}</a>
                                    </div>
                                {% endfor %}
                            </div>
                            {% endif %}
                        `;
                    }
                    else {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                    <a href="{{ ${this.ct_name}.fields.${this.name}.value }}" target="_blank" download>{{ ${this.ct_name}.fields.${this.name}.value|get_basename }}</a>
                                </div>
                            </div>
                            {% endif %}
                        `;
                    }
                }
                break;
            // ----------- //
            // IMAGE TYPE   //
            // ----------- //
            case "image":
                if (template_type == "edit") {
                    if (this.multiple) {
                        template = `
                            <label class="edit-field-label ${this.ct_name}-${this.name}-label">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                            <div class="ml-2 mb-2">
                                <div id="${this.ct_name}-${this.name}-values"></div>
                                <a href="javascript:select_file(${this.ct_name}_${this.name}_add_value);" role="button" class="btn btn-sm btn-secondary">+</a>
                            </div>
                        `;

                        javascript = `  
                            function ${this.ct_name}_${this.name}_remove_value(index) {
                                $('#${this.ct_name}-${this.name}-' + index.toString()).remove();
                            }
                            
                            function ${this.ct_name}_${this.name}_add_value(file) {
                                let index = $('.${this.ct_name}-${this.name}-value').length;
                                $('#${this.ct_name}-${this.name}-values').append('\
                                    <div id="${this.ct_name}-${this.name}-' + index + '" class="form-group mb-2 ${this.ct_name}-${this.name}-value">\
                                        <div class="row">\
                                            <div class="col-11">\
                                                <input type="hidden" name="${this.ct_name}-${this.name}-' + index + '" value="' + file + '">\
                                                <img src="' + file + '" class="image-field ${this.ct_name}-${this.name}" style="max-width: 100px; max-height: 100px;">\
                                            </div>\
                                            <div class="col-1">\
                                                <a href="javascript:${this.ct_name}_${this.name}_remove_value(' + index + ');" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a>\
                                            </div>\
                                        </div>\
                                    </div>\
                                ');
                            }
                            
                            $(document).ready(function() {
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    ${this.ct_name}_${this.name}_add_value('{{ ${this.name} }}');
                                {% endfor %}
                            });
                        `;
                    } else {
                        template = `
                            <div class="form-group">
                                <label class="edit-field-label" for="${this.ct_name}-${this.name}">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                                <input type="hidden" name="${this.ct_name}-${this.name}" value="{{ ${this.ct_name}.fields.${this.name}.value|default:'' }}">
                                <img id="${this.ct_name}-${this.name}-img" src="{{ ${this.ct_name}.fields.${this.name}.value }}" class="image-field ${this.ct_name}-${this.name} d-none" style="max-width: 100px; max-height: 100px;">
                                <a href="javascript:select_file(${this.ct_name}_${this.name}_add_value);" role="button" class="btn btn-sm btn-secondary">Select</a>
                            </div>
                        `;

                        javascript = `
                            function ${this.ct_name}_${this.name}_add_value(file) {
                                $('#${this.ct_name}-${this.name}').val(file);
                                $('#${this.ct_name}-${this.name}-img').attr('src', file);
                                $('#${this.ct_name}-${this.name}-img').removeClass('d-none');
                            }
                        `;
                    }
                } else if (template_type == "list" && this.in_lists) {
                    let display = `<img src="{{ ${this.name} }}" class="image-field ${this.ct_name}-${this.name}">`;
                    if (this.multiple) {
                        display = `
                            {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                               <img src="{{ ${this.name} }}" class="image-field ${this.ct_name}-${this.name}">{% if not forloop.last %}, {% endif %}
                            {% endfor %}
                        `;
                    }

                    template = `
                        <td class="${this.ct_name}-${this.name} list-field">
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                                ${display}
                            {% endif %}
                        </td>
                    `;
                } else {
                    if (this.multiple) {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    {% if not forloop.first %}
                                        <div class="col-2">&nbsp;</div>
                                    {% endif %}
                                    <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                        <img src="{{ ${this.name} }}" class="image-field ${this.ct_name}-${this.name}">
                                    </div>
                                {% endfor %}
                            </div>
                            {% endif %}
                        `;
                    } else {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                    <img src="{{ ${this.ct_name}.fields.${this.name}.value }}" class="image-field ${this.ct_name}-${this.name}">
                                </div>
                            </div>
                            {% endif %}
                        `;
                    }
                }
                break;
            // ----------- //
            // LINK TYPE   //
            // ----------- //
            case "link":
                if (template_type == "edit") {
                    if (this.multiple) {
                        template = `
                            <label class="edit-field-label ${this.ct_name}-${this.name}-label">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                            <div class="ml-2 mb-2">
                                <div id="${this.ct_name}-${this.name}-values">
                                    {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                        <div id="${this.ct_name}-${this.name}-{{ forloop.counter0 }}" class="form-group mb-2">
                                            <div class="row">
                                                <div class="col-11">
                                                    <input type="text" class="form-control ${this.ct_name}-${this.name}-value" name="${this.ct_name}-${this.name}-{{ forloop.counter0 }}" value="{{ ${this.name}|default:'' }}">
                                                </div>
                                                <div class="col-1">
                                                    <a href="javascript:${this.ct_name}_${this.name}_remove_value({{ forloop.counter0 }});" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a>
                                                </div>
                                            </div>
                                        </div>
                                    {% endfor %}
                                </div>
                                <button type="button" class="btn btn-sm btn-secondary" id="${this.ct_name}-${this.name}-add-button">+</button>
                            </div>
                        `;

                        javascript = `
                            $(document).ready(function() {
                                $('#${this.ct_name}-${this.name}-add-button').click(function() {
                                    let count = 0;
                                    $('.${this.ct_name}-${this.name}-value').each(function() {
                                        count += 1;
                                    });
                                    let new_field_value_name = '${this.ct_name}-${this.name}-' + count.toString();
                                    $('#${this.ct_name}-${this.name}-values').append('<div id="' + new_field_value_name + '" class="form-group mb-2"><div class="row"><div class="col-11"><input type="text" class="form-control ${this.ct_name}-${this.name}-value" name="' + new_field_value_name + '"></div><div class="col-1"><a href="javascript:${this.ct_name}_${this.name}_remove_value(' + count.toString() + ');" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a></div></div></div>');
                                });
                            });
                            
                            function ${this.ct_name}_${this.name}_remove_value(index) {
                                $('#${this.ct_name}-${this.name}-' + index.toString()).remove();
                            }
                        `;
                    } else {
                        template = `
                            <div class="form-group">
                                <label class="edit-field-label ${this.ct_name}-${this.name}-label" for="${this.ct_name}-${this.name}">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                                <input type="text" class="form-control" id="${this.ct_name}-${this.name}" name="${this.ct_name}-${this.name}" value="{{ ${this.ct_name}.fields.${this.name}.value|default:'' }}">
                            </div>
                        `;
                    }
                } else if (template_type == "list" && this.in_lists) {
                    let display = `<a href="{{ ${this.ct_name}.fields.${this.name}.value }}" class="link-field ${this.ct_name}-${this.name}-link">{{ ${this.ct_name}.fields.${this.name}.label }}</a>`;
                    if (this.multiple) {
                        display = `
                            {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                               <a href="{{ ${this.name} }}" class="link-field ${this.ct_name}-${this.name}-link">${this.ct_name}.fields.${this.name}.label</a>{% if not forloop.last %}, {% endif %}
                            {% endfor %}
                        `;
                    }

                    template = `
                        <td class="${this.ct_name}-${this.name} list-field">
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                                ${display}
                            {% endif %}
                        </td>
                    `;
                } else {
                    if (this.multiple) {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    {% if not forloop.first %}
                                        <div class="col-2">&nbsp;</div>
                                    {% endif %}
                                    <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                        <a href="{{ ${this.name} }}" class="link-field ${this.ct_name}-${this.name}-link">${this.ct_name}.fields.${this.name}.label</a>
                                    </div>
                                {% endfor %}
                            </div>
                            {% endif %}
                        `;
                    }
                    else {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                    <a href="{{ ${this.ct_name}.fields.${this.name}.value }}" class="link-field ${this.ct_name}-${this.name}-link">{{ ${this.ct_name}.fields.${this.name}.label }}</a>
                                </div>
                            </div>
                            {% endif %}
                        `;
                    }
                }
                break;
            // ----------- //
            // CX REF TYPE //
            // ----------- //
            case "cross_reference":
                if (template_type == "edit") {
                    if (this.multiple) {
                        template = `
                            <label class="edit-field-label ${this.ct_name}-${this.name}-label">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                            <div class="ml-2 mb-2">
                                <div id="${this.ct_name}-${this.name}-values"></div>
                                <a href="javascript:select_content('${this.cross_reference_type}', ${this.ct_name}_${this.name}_add_value);" role="button" class="btn btn-sm btn-secondary">+</a>
                            </div>
                        `;

                        javascript = `  
                            function ${this.ct_name}_${this.name}_remove_value(index) {
                                $('#${this.ct_name}-${this.name}-' + index.toString()).remove();
                            }
                            
                            function ${this.ct_name}_${this.name}_add_value(id, label) {
                                let index = $('.${this.ct_name}-${this.name}-value').length;
                                $('#${this.ct_name}-${this.name}-values').append('\
                                    <div id="${this.ct_name}-${this.name}-' + index + '" class="form-group mb-2 ${this.ct_name}-${this.name}-value">\
                                        <div class="row">\
                                            <div class="col-11">\
                                                <input type="hidden" name="${this.ct_name}-${this.name}-' + index + '" value="' + id + '">\
                                                <a href="/view/${this.cross_reference_type}/' + id + '/" target="_blank">' + label + '</a>\
                                            </div>\
                                            <div class="col-1">\
                                                <a href="javascript:${this.ct_name}_${this.name}_remove_value(' + index + ');" role="button" class="btn btn-sm btn-danger"><span class="fas fa-trash-alt"></a>\
                                            </div>\
                                        </div>\
                                    </div>\
                                ');
                            }
                            
                            $(document).ready(function() {
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    ${this.ct_name}_${this.name}_add_value('{{ ${this.name}.id }}', '{{ ${this.name}.label }}');
                                {% endfor %}
                            });
                        `;
                    } else {
                        template = `
                            <div class="form-group">
                                <label class="edit-field-label ${this.ct_name}-${this.name}-label" for="${this.ct_name}-${this.name}">{{ ${this.ct_name}.fields.${this.name}.label }}</label>
                                <div class="row">
                                    <div class="col-12">
                                        <div class="input-group">
                                            <input type="hidden" id="${this.ct_name}-${this.name}-value" name="${this.ct_name}-${this.name}" value="{{ ${this.ct_name}.fields.${this.name}.value.id|default:'' }}">
                                            <a id="${this.ct_name}-${this.name}-link" href="{{ ${this.ct_name}.fields.${this.name}.value.url }}" target="_blank" class="cross_reference_field ${this.ct_name}-${this.name} {% if not ${this.ct_name}.fields.${this.name}.value %}d-none{% endif %}">{{ ${this.ct_name}.fields.${this.name}.value.label|safe }}</a>
                                        </div>
                                        <span class="input-group-btn btn-sm ml-1"><a href="javascript:select_content('${this.cross_reference_type}', ${this.ct_name}_${this.name}_add_value);" role="button" class="btn btn-sm btn-secondary">Select</a></span>
                                    </div>
                                </div>
                            </div>
                        `;

                        javascript = `
                            function ${this.ct_name}_${this.name}_add_value(id, label) {
                                $('#${this.ct_name}-${this.name}-value').val(id);   
                                $('#${this.ct_name}-${this.name}-link').attr('href', '/view/${this.ct_name}/' + id + '/');
                                $('#${this.ct_name}-${this.name}-link').html(label);
                                $('#${this.ct_name}-${this.name}-link').removeClass('d-none');
                            }
                        `;
                    }
                } else if (template_type == "list" && this.in_lists) {
                    let display = `<a href="{{ ${this.ct_name}.fields.${this.name}.value.url }}" target="_blank">{{ ${this.ct_name}.fields.${this.name}.value.label|safe }}</a>`;
                    if (this.multiple) {
                        display = `
                            {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                               <a href="{{ ${this.name}.url }}" target="_blank">{{ ${this.name}.label }}</a>{% if not forloop.last %},<br />{% endif %}
                            {% endfor %}
                        `;
                    }

                    template = `
                        <td class="${this.ct_name}-${this.name} list-field">
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                                ${display}
                            {% endif %}
                        </td>
                    `;
                } else {
                    if (this.multiple) {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                {% for ${this.name} in ${this.ct_name}.fields.${this.name}.value %}
                                    {% if not forloop.first %}
                                        <div class="col-2">&nbsp;</div>
                                    {% endif %}
                                    <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                        <a href="{{ ${this.name}.url }}" target="_blank">{{ ${this.name}.label|safe }}</a>
                                    </div>
                                {% endfor %}
                            </div>
                            {% endif %}
                        `;
                    } else {
                        template = `
                            {% if ${this.ct_name}.fields.${this.name}.value %}
                            <div class="row">
                                <div class="col-2 d-flex align-right view-field-label ${this.ct_name}-${this.name}-label">
                                    {{ ${this.ct_name}.fields.${this.name}.label }}:
                                </div>
                                <div class="col-10 d-flex align-left view-field-value ${this.ct_name}-${this.name}-value">
                                    <a href="{{ ${this.ct_name}.fields.${this.name}.value.url }}" target="_blank">{{ ${this.ct_name}.fields.${this.name}.value.label|safe }}</a>
                                </div>
                            </div>
                            {% endif %}
                        `;
                    }
                }
                break;
        }

        return {
            html: template,
            js: javascript
        };
    }

    to_object() {
        return {
            name: this.name,
            label: this.label,
            in_lists: this.in_lists,
            indexed: this.indexed,
            indexed_with: this.indexed_with,
            unique: this.unique,
            unique_with: this.unique_with,
            multiple: this.multiple,
            type: this.type,
            cross_reference_type: this.cross_reference_type
        }
    }
}

