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

        if (this.corpora && this.corpus && this.content_type && !getEl('content-selection-modal')) {
            prependToEl(document.body, `
                <div class="modal fade" id="content-selection-modal" tabindex="-1" role="dialog" aria-labelledby="content-selection-modal-label" aria-hidden="true">
                    <div class="modal-dialog" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="content-selection-modal-label">Select ContentType</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close">
                                </button>
                            </div>
                            <div class="modal-body">
                                <div class="alert alert-light">
                                    <div class="mb-2">
                                        <input type="text" class="form-control" id="content-selection-modal-filter-box" aria-placeholder="Search" placeholder="Search">
                                    </div>
                                    <table class="table table-striped">
                                        <thead class="thead-dark">
                                            <th scope="col" id="content-selection-modal-table-header" class="text-white">ContentType</th>
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
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            </div>
                        </div>
                    </div>
                </div>
            `)
        }
    }

    // resolved on demand rather than cached in the constructor, which used to look the
    // modal up before building it and so cached a miss.
    get modal() {
        return getEl('content-selection-modal')
    }

    load_content_selection() {
        this.corpora.list_content(this.corpus.id, this.content_type, this.content_selection_vars, data => {
            if (!data.meta || !data.records) return

            setDisabled(getEl('content-selection-modal-prev-page-button'), this.content_selection_vars.page <= 1)
            setDisabled(getEl('content-selection-modal-next-page-button'), !data.meta.has_next_page)

            getEl('content-selection-modal-label').innerHTML = `Select ${this.content_type}`
            getEl('content-selection-modal-table-header').innerHTML = this.content_type

            let table_body = getEl('content-selection-modal-table-body')
            clearEl(table_body)
            data.records.forEach(record => {
                appendToEl(table_body, `
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

            forElsMatching('.content-selection-item', item => {
                onlyOnEl(item, 'click', () => {
                    setVal(this.id_element, item.dataset.id)
                    setVal(this.label_element, item.dataset.label)
                    hideModal(this.modal)
                    if (this.previous_modal) showModal(this.previous_modal)
                })
            })
        })
    }

    rig_up_events() {
        let filter_box = getEl('content-selection-modal-filter-box')

        // onlyOnEl throughout: rig_up_events runs on every select(), and these used to
        // stack up. The shown.bs.modal handler in particular had no .off() at all.
        onlyOnEl(this.modal, 'shown.bs.modal', () => {
            setVal(filter_box, '')
            filter_box.focus()
        })

        onlyOnEl(filter_box, 'keyup', e => {
            let query = getVal(filter_box).replaceAll("'", ' ')
            this.content_selection_vars.q = query + '*'
            this.content_selection_vars['t_label'] = `${query}`
            this.content_selection_vars['operator'] = 'or'
            this.content_selection_vars.page = 1
            delete this.content_selection_vars['s_label']

            if (e.key === 'Enter') {
                this.load_content_selection()
            } else {
                clearTimeout(this.content_search_timer)
                this.content_search_timer = setTimeout(() => this.load_content_selection(), 500)
            }
        })

        onlyOnEl(getEl('content-selection-modal-prev-page-button'), 'click', () => {
            this.content_selection_vars.page -= 1
            this.load_content_selection()
        })

        onlyOnEl(getEl('content-selection-modal-next-page-button'), 'click', () => {
            this.content_selection_vars.page += 1
            this.load_content_selection()
        })

        onlyOnEl(getEl('content-create-new-button'), 'click', () => {
            let left = (screen.width / 2)
            let top = (screen.height / 2)
            let options = `top=${top},left=${left},popup=true`
            let creation_url = `/corpus/${this.corpus.id}/${this.content_type}/?popup=y`
            return window.open(creation_url, '_blank', options)
        })
    }

    select() {
        this.rig_up_events()
        this.load_content_selection()
        if (this.previous_modal) hideModal(this.previous_modal)
        showModal(this.modal)
    }
}
