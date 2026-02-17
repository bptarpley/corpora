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
                                    <button type="button" class="btn-close" data-dismiss="modal" aria-label="Close">
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

