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
