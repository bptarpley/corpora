REGISTRY = [
{
        "id": "",
        "name": "Editor",
        "plural_name": "Editors",
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "edit": {
                "html": "{% load static %}\n{% load extras %}\n<div id=\"content-template\" class=\"content-template Editor-edit card mt-4\">\n    <div class=\"card-header\">\n        <h2>{{ Editor.label|safe|default:'Create New' }}</h2>\n    </div>\n    <div class=\"card-body \">\n\n        <div class=\"row\">\n            <div class=\"col\">\n                <form id=\"Editor-form\" class=\"edit-form Editor-form\" method=\"post\">\n                    {% csrf_token %}\n                    <input type=\"hidden\" name=\"content_type\" value=\"Editor\">\n                    <input type=\"hidden\" name=\"id\" value=\"{{ Editor.id }}\">\n\n                    <div class=\"edit-field\">\n\n                        <div class=\"form-group\">\n                            <label class=\"edit-field-label Editor-name-label\" for=\"Editor-name\">{{ Editor.fields.name.label }}</label>\n                            <input type=\"text\" class=\"form-control\" id=\"Editor-name\" name=\"Editor-name\" value=\"{{ Editor.fields.name.value|safe|default:'' }}\">\n                        </div>\n\n                    </div>\n\n                    <div class=\"edit-field\">\n\n                        <div class=\"form-group\">\n                            <label class=\"edit-field-label Editor-role-label\" for=\"Editor-role\">{{ Editor.fields.role.label }}</label>\n                            <input type=\"text\" class=\"form-control\" id=\"Editor-role\" name=\"Editor-role\" value=\"{{ Editor.fields.role.value|safe|default:'' }}\">\n                        </div>\n\n                    </div>\n\n                    <div class=\"form-group\">\n                        {% if popup %}\n                        <button class=\"btn btn-primary\" id=\"Editor-form-submit-button\">Save</button>\n                        {% else %}\n                        <button type=\"submit\" class=\"btn btn-primary\" id=\"Editor-form-submit-button\">Save</button>\n                        {% endif %}\n                    </div>\n                </form>\n            </div>\n        </div>\n\n    </div>\n</div>",
                "js": "\n                {% load static %}\n                {% load extras %}\n                \n                <script type='application/javascript'>\n                    \n                {% if popup %}\n                $(document).ready(function() {\n                    window.resizeTo(450, 400);\n                });\n                {% endif %}\n            \n                </script>\n            "
            },
            "view": {
                "html": "{% load static %}\n{% load extras %}\n<div id=\"content-template\" class=\"content-template Editor-view card mt-4\">\n    <div class=\"card-header\">\n        <h2>{{ Editor.label|safe|default:'Create New' }}</h2>\n    </div>\n    <div class=\"card-body \">\n\n        <div class=\"row\">\n            <div class=\"col\">\n                <div class=\"Editor mb-3\">\n\n                    {% if Editor.fields.name.value %}\n                    <div class=\"row\">\n                        <div class=\"col-2 d-flex align-right view-field-label Editor-name-label\">\n                            {{ Editor.fields.name.label }}:\n                        </div>\n                        <div class=\"col-10 d-flex align-left view-field-value Editor-name-value\">\n                            {{ Editor.fields.name.value|safe }}\n                        </div>\n                    </div>\n                    {% endif %}\n\n                    {% if Editor.fields.role.value %}\n                    <div class=\"row\">\n                        <div class=\"col-2 d-flex align-right view-field-label Editor-role-label\">\n                            {{ Editor.fields.role.label }}:\n                        </div>\n                        <div class=\"col-10 d-flex align-left view-field-value Editor-role-value\">\n                            {{ Editor.fields.role.value|safe }}\n                        </div>\n                    </div>\n                    {% endif %}\n\n                    <a href=\"/edit/Editor/{{ Editor.id }}/\" role=\"button\" class=\"btn btn-sm btn-secondary\"><span class=\"fas fa-edit\"></span></a>\n                </div>\n            </div>\n        </div>\n\n    </div>\n</div>",
                "js": ""
            },
            "list": {
                "html": "{% load static %}\n{% load extras %}\n<div id=\"content-template\" class=\"content-template Editor-list card mt-4\">\n    <div class=\"card-header\">\n        <h2>Editors</h2>\n    </div>\n    <div class=\"card-body table-responsive\">\n\n        <!-- SEARCH / PAGING CONTROLS /-->\n        <div class=\"mb-3 d-flex\">\n            <div class=\"flex-grow-1\">\n                <input type=\"text\" class=\"form-control\" id=\"Editor-filter-box\" aria-placeholder=\"Search\" placeholder=\"Search\">\n            </div>\n\n            <div class=\"ml-2 flex-nowrap align-self-center\">\n                <span class=\"Editor-start-record\">1</span>-<span class=\"Editor-end-record\">50</span> out of <span class=\"Editor-total-records\">100</span>\n            </div>\n\n            <div class=\"ml-2 flex-nowrap form-inline\">\n                <button type=\"button\" class=\"btn btn-primary Editor-prev-page-button\"><span class=\"fas fa-angle-left\"></span></button>\n                <select class=\"form-control Editor-page-selector\"></select>\n                <button type=\"button\" class=\"btn btn-primary Editor-next-page-button\"><span class=\"fas fa-angle-right\"></span></button>\n            </div>\n        </div>\n        <table id=\"Editor-list-table\" class=\"table table-striped\">\n            <thead class=\"thead-dark\">\n                <th scope=\"col\" class=\"list-field-header\"></th>\n\n                <th scope=\"col\" id=\"Editor-name-table-header\" class=\"list-field-header\">\n                    Name\n                    <button id=\"Editor-name-table-settings\" type=\"button\" class=\"btn btn-sm text-white\" data-toggle=\"popover\"><span class=\"fas fa-sliders-h\"></span></button>\n                </th>\n\n                <th scope=\"col\" id=\"Editor-role-table-header\" class=\"list-field-header\">\n                    Role\n                    <button id=\"Editor-role-table-settings\" type=\"button\" class=\"btn btn-sm text-white\" data-toggle=\"popover\"><span class=\"fas fa-sliders-h\"></span></button>\n                </th>\n\n            </thead>\n            <tbody id=\"Editor-table-body\">\n                <tr>\n                    <td colspan=\"3\">Loading...</td>\n                </tr>\n            </tbody>\n        </table>\n        <div id=\"Editor-name-toolbar\" class=\"d-none\"><a role=\"button\" id=\"Editor-name-sort-button\" href=\"javascript:sort_Editor_table('name');\" class=\"btn btn-sm btn-secondary\">Sort <span class=\"fas fa-sort-amount-up\"></span></a></div>\n        <div id=\"Editor-role-toolbar\" class=\"d-none\"><a role=\"button\" id=\"Editor-role-sort-button\" href=\"javascript:sort_Editor_table('role');\" class=\"btn btn-sm btn-secondary\">Sort <span class=\"fas fa-sort-amount-up\"></span></a></div>\n        <!-- PAGING CONTROLS /-->\n        <div class=\"float-right\">\n            <button type=\"button\" class=\"btn btn-sm btn-primary Editor-prev-page-button\"><span class=\"fas fa-angle-left\"></span></button>\n            <select class=\"form-control-sm Editor-page-selector\" style=\"display: inline-flex;\"></select>\n            <button type=\"button\" class=\"btn btn-sm btn-primary Editor-next-page-button\"><span class=\"fas fa-angle-right\"></span></button>\n        </div>\n        <div>\n            <a role=\"button\" href=\"/edit/Editor/new/\" class=\"btn btn-primary\">Create</a>\n        </div>\n\n    </div>\n</div>",
                "js": "\n                {% load static %}\n                {% load extras %}\n                \n                <script type='application/javascript'>\n                    \n                var Editor_params = {\n                    current_page: 1,\n                    page_size: 50,\n                    query: {},\n                    search: '',\n                    sort: [],\n                    render_template: 'list',\n                    only: 'id,name,role',\n                }\n                var Editor_first_load = true;\n                var Editor_timer;\n                var Editor_filtering_field = '';\n                var Editor_field_stats = {};\n            \n                $(document).ready(function() {\n                    //determine_Editor_field_sizes();\n                    Editor_load_table();\n                    \n                    $('#Editor-filter-box').on('input', function(e){\n                        clearTimeout(Editor_timer);\n                        Editor_timer = setTimeout(function() {\n                            Editor_params.search = $('#Editor-filter-box').val() + '*';\n                            Editor_params.current_page = 1;\n                            Editor_params.sort = [];\n                            Editor_load_table();\n                        }, 1200);\n                    });\n                    \n                    $('.Editor-prev-page-button').click(function() {\n                        Editor_params.current_page -= 1;\n                        Editor_load_table();\n                    });\n                    \n                    $('.Editor-next-page-button').click(function() {\n                        Editor_params.current_page += 1;\n                        Editor_load_table();\n                    });\n                    \n                    $('.Editor-page-selector').change(function() {\n                        Editor_params.current_page = parseInt(this.value);\n                        Editor_load_table();\n                    });\n                    \n                    $.get('/stats/Editor/', function(data) {\n                        Editor_field_stats = data;\n                        \n                        $('#Editor-name-table-settings').popover({\n                            placement: 'top',\n                            html: true,\n                            sanitize: false,\n                            title: 'Field Options',\n                            template: '<div class=\"popover\" role=\"tooltip\"><div class=\"arrow\"></div><h3 id=\"Editor-name-popover-header\" class=\"popover-header\"></h3><div id=\"Editor-name-popover\" class=\"popover-body\"></div></div>',\n                        });\n                        $('#Editor-name-table-settings').on('shown.bs.popover', function() {\n                            let toolbar = $('#Editor-name-toolbar').detach();\n                            toolbar.appendTo('#Editor-name-popover');\n                            toolbar.removeClass('d-none');\n                            $('#Editor-name-table-settings').popover('update');\n                        });\n                        $('#Editor-name-table-settings').on('hide.bs.popover', function() {\n                            let toolbar = $('#Editor-name-toolbar').detach();\n                            toolbar.appendTo($(document.body));\n                            toolbar.addClass('d-none');\n                        });\n                    \n                        $('#Editor-role-table-settings').popover({\n                            placement: 'top',\n                            html: true,\n                            sanitize: false,\n                            title: 'Field Options',\n                            template: '<div class=\"popover\" role=\"tooltip\"><div class=\"arrow\"></div><h3 id=\"Editor-role-popover-header\" class=\"popover-header\"></h3><div id=\"Editor-role-popover\" class=\"popover-body\"></div></div>',\n                        });\n                        $('#Editor-role-table-settings').on('shown.bs.popover', function() {\n                            let toolbar = $('#Editor-role-toolbar').detach();\n                            toolbar.appendTo('#Editor-role-popover');\n                            toolbar.removeClass('d-none');\n                            $('#Editor-role-table-settings').popover('update');\n                        });\n                        $('#Editor-role-table-settings').on('hide.bs.popover', function() {\n                            let toolbar = $('#Editor-role-toolbar').detach();\n                            toolbar.appendTo($(document.body));\n                            toolbar.addClass('d-none');\n                        });\n                    \n                    });\n                });\n                \n                function Editor_load_table() {\n                    let table_body = $('#Editor-table-body');\n                    let get_params = Object.assign({}, Editor_params);\n                    \n                    if (typeof Editor_initial_params !== 'undefined' && Editor_first_load) {\n                        get_params = Object.assign(get_params, Editor_initial_params);\n                        Editor_first_load = false;\n                    }\n                    \n                    get_params.sort = get_params.sort.join(',');\n                    //get_params.search = encodeURI(get_params.search);\n                    $.get('/api/corpus/5dec13c7d5648e141bf68b0b/type/Editor/', get_params, function(data){\n                        $('#Editor-table-body').html('');\n                        let meta = data.meta;\n                        for (let x = 0; x < data.data.length; x++) {\n                            let row_html = '<tr>';\n                            row_html += '<td><a href=\"/corpus/5dec13c7d5648e141bf68b0b/type/Editor/view/' + data.data[x].id + '/\" class=\"content-open-link\" target=\"_blank\"><span class=\"fas fa-external-link-square-alt\"></span></a></td>';\n                            for (const field in data.data[x].fields) {\n                                row_html += data.data[x].fields[field]['_template'];\n                            }\n                            table_body.append(row_html + '</tr>');\n                        }\n                        \n                        if (meta) {\n                            let prev_button = $('.Editor-prev-page-button');\n                            let next_button = $('.Editor-next-page-button');\n                            let page_selector = $('.Editor-page-selector');\n                        \n                            let total = meta['count'];\n                            let page_size = meta['page_size'];\n                            let total_pages = Math.ceil(total / page_size);\n                            let current_page = meta['current_page'];\n                            let start_record = 1 + ((current_page - 1) * page_size);\n                            let end_record = current_page * page_size;\n                            let has_next = meta['has_next_page'];\n                            \n                            if (end_record > total) { end_record = total; }\n                            if (current_page > 1) { prev_button.prop('disabled', false); } else { prev_button.prop('disabled', true); }\n                            if (current_page < total_pages) { next_button.prop('disabled', false); } else { next_button.prop('disabled', true); }\n                            \n                            page_selector.html('');\n                            for (let x = 1; x < total_pages + 1; x++) {\n                                let option = '<option';\n                                if (x == current_page) { option += ' selected'; }\n                                option += '>' + x.toString() + '</option>';\n                                page_selector.append(option);\n                            }\n                            \n                            $('.Editor-start-record').html(start_record);\n                            $('.Editor-end-record').html(end_record);\n                            $('.Editor-total-records').html(total);\n                        }\n                    });\n                }\n                \n                function sort_Editor_table(field) {\n                    let asc_field_index = Editor_params.sort.indexOf('+' + field);\n                    let desc_field_index = Editor_params.sort.indexOf('-' + field);\n                    \n                    if (asc_field_index !== -1) {\n                        Editor_params.sort[asc_field_index] = '-' + field;\n                        $('#Editor-' + field + '-sort-button').html('Sort <span class=\"fas fa-sort-amount-up\"></span>');\n                    } else if (desc_field_index !== -1) {\n                        Editor_params.sort[desc_field_index] = '+' + field;\n                        $('#Editor-' + field + '-sort-button').html('Sort <span class=\"fas fa-sort-amount-down\"></span>');\n                    } else {\n                        Editor_params.sort.push('+' + field);\n                        $('#Editor-' + field + '-sort-button').html('Sort <span class=\"fas fa-sort-amount-down\"></span>');\n                    }\n                    Editor_page = 1;\n                    Editor_apply_field_settings(field);\n                }\n                \n                function Editor_select_xref_filter(field, content_type) {\n                    Editor_filtering_field = field;\n                    $('#Editor-' + field + '-table-settings').popover('hide');\n                    select_content(content_type, Editor_apply_xref_filter);\n                }\n                \n                function Editor_apply_xref_filter(id, label) {\n                    Editor_params[Editor_filtering_field] = label;\n                    Editor_params.current_page = 1;\n                    Editor_apply_field_settings(Editor_filtering_field);\n                }\n                \n                function Editor_apply_field_settings(field) {\n                    if (!$('#Editor-' + field + '-reset-button').length) {\n                        $('#Editor-' + field + '-toolbar').append('<a role=\"button\" id=\"Editor-' + field + '-reset-button\" href=\"javascript:Editor_reset_field_settings(\\'' + field + '\\');\" class=\"btn btn-sm btn-danger ml-1\">Reset</a>');\n                        $('#Editor-' + field + '-table-settings').removeClass('text-white');\n                        $('#Editor-' + field + '-table-settings').addClass('text-info');\n                    }\n                    $('#Editor-' + field + '-table-settings').popover('hide');\n                    Editor_load_table();\n                }\n                \n                function Editor_reset_field_settings(field) {\n                    let asc_field_index = Editor_params.sort.indexOf('+' + field);\n                    let desc_field_index = Editor_params.sort.indexOf('-' + field);\n                    \n                    if (asc_field_index !== -1) {\n                        Editor_params.sort.splice(asc_field_index, 1);\n                    } else if (desc_field_index !== -1) {\n                        Editor_params.sort.splice(desc_field_index, 1);\n                    }\n                    \n                    delete Editor_params[field];\n                    Editor_params.current_page = 1;\n                \n                    $('#Editor-' + field + '-reset-button').remove();\n                    $('#Editor-' + field + '-table-settings').removeClass('text-info');\n                    $('#Editor-' + field + '-table-settings').addClass('text-white');\n                    $('#Editor-' + field + '-table-settings').popover('hide');\n                    Editor_load_table();\n                }\n            \n                </script>\n            "
            },
            "label": {
                "html": "{{ Editor.fields.name.value }}",
                "js": ""
            },
            "field_templates": {
                "name": "\n                        <td class=\"Editor-name list-field\">\n                            {% if Editor.fields.name.value %}\n                                {{ Editor.fields.name.value|safe }}\n                            {% endif %}\n                        </td>\n                    ",
                "role": "\n                        <td class=\"Editor-role list-field\">\n                            {% if Editor.fields.role.value %}\n                                {{ Editor.fields.role.value|safe }}\n                            {% endif %}\n                        </td>\n                    "
            }
        },
        "fields": [
            {
                "name": "name",
                "label": "Name",
                "in_lists": True,
                "indexed": False,
                "indexed_with": [],
                "unique": False,
                "unique_with": [],
                "multiple": False,
                "type": "text",
                "cross_reference_type": ""
            },
            {
                "name": "role",
                "label": "Role",
                "in_lists": True,
                "indexed": False,
                "indexed_with": [],
                "unique": False,
                "unique_with": [],
                "multiple": False,
                "type": "text",
                "cross_reference_type": ""
            }
        ]
    }
]