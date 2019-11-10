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
            "/api/corpora/",
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
            `/api/corpus/${corpus_id}/documents/`,
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
}