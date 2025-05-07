class ContentGroup {
    constructor(corpora, corpus, contentGroup, index) {
        this.corpora = corpora
        this.corpus = corpus
        this.canEdit = ['Admin', 'Editor'].includes(corpus.scholar_role)
        this.index = index
        this.title = 'title' in contentGroup ? contentGroup.title : null
        this.description = 'description' in contentGroup ? contentGroup.description : null
        this.members = []

        if ('members' in contentGroup) {
            this.members = contentGroup.members.map(member => member)
        }

        this.rendered = false
        this.editing = false
        this.contentTypesDivID = null
    }

    render(groupContainer, ctContainerID) {
        this.contentTypesDivID = ctContainerID
        let editButtonHTML = ''
        if (this.canEdit) {
            editButtonHTML = `
                <button id="ct-group-${this.index}-edit-button" class="btn btn-sm btn-primary" data-toggle="tooltip" data-placement="top" title="Edit">
                    <span class="fas fa-edit"></span>
                </button>
            `
        }

        groupContainer.append(`
            <div id="ct-group-${this.index}" class="alert alert-info content-type-group mt-4 pb-4" data-title="${this.title}">
                <h2 class="content-type-group-header">${this.title}${editButtonHTML}</h2>
                <div id="ct-group-${this.index}-controls-div" class="d-none my-2 justify-content-between align-bottom">
                    <span>
                        <button id="ct-group-${this.index}-delete-button" type="button" class="btn btn-danger mr-4" data-title="${this.title}" data-toggle="tooltip" title="Delete Group">
                            <span class="fas fa-trash-alt"></span>
                        </button>
                        <button id="ct-group-${this.index}-cancel-button" type="button" class="btn btn-secondary mr-1">Cancel</button>
                        <button id="ct-group-${this.index}-save-button" type="button" class="btn btn-primary">Save Changes</button>
                    </span>
                    <span class="text-muted" style="align-self: flex-end;">Deleting a Content Type group will not delete its Content Types.</span>
                </div>
                <div id="ct-group-${this.index}-description" class="content-type-group-description ${this.description ? 'mt-2 alert alert-info' : ''}">${this.description ? this.description : ''}</div>
                <div id="ct-group-${this.index}-ct-selector-div" class="d-none mt-2">
                    <label for="ct-group-${this.index}-ct-selector">Select a Content Type to add to this group:</label>
                    <select id="ct-group-${this.index}-ct-selector" class="form-control-sm btn-primary ml-1 mr-1"></select>
                    <button type="button" class="btn btn-sm btn-secondary" id="ct-group-${this.index}-ct-add-button">Go</button>
                </div>
                <div id="ct-group-${this.index}-members-div"></div>
            </div>
        `)
        this.renderMembers()

        let ctSelector = $(`#ct-group-${this.index}-ct-selector`)
        let ctSelectorGoButton = $(`#ct-group-${this.index}-ct-add-button`)
        let ctgEditButton = $(`#ct-group-${this.index}-edit-button`)
        let ctgCancelButton = $(`#ct-group-${this.index}-cancel-button`)
        let ctgDeleteButton = $(`#ct-group-${this.index}-delete-button`)
        let ctgSaveButton = $(`#ct-group-${this.index}-save-button`)

        let sender = this

        ctgEditButton.click(function() {
            sender.edit()
        })

        ctSelectorGoButton.click(function() {
            let membersDiv = $(`#ct-group-${this.index}-members-div`)
            let ctName = ctSelector.val()
            sender.members.push({
                name: ctName,
                display_preference: 'full'
            })
            sender.save(function(response) {
                if (response.success) {
                    sender.renderMembers()
                    sender.edit()
                }
            })
        })

        ctgCancelButton.click(function() {
            let descBoxID = `ct-group-${sender.index}-description`

            $(`#ct-group-${sender.index}-ct-selector-div`).addClass('d-none')
            $(`#ct-group-${sender.index}-controls-div`).removeClass('d-flex').addClass('d-none')
            $(`.content-type-group-member-controls`).addClass('d-none')

            tinymce.get(descBoxID).remove()
            $(`#${descBoxID}`).html(sender.description)

            sender.editing = false
        })

        ctgSaveButton.click(function() {
            sender.save(function(response) {
                if (response.success) ctgCancelButton.trigger('click')
            })
        })

        ctgDeleteButton.click(function() {
            sender.delete()
        })
    }

    scrollTo() {
        $(`#ct-group-${this.index}`)[0].scrollIntoView({behavior: 'smooth'})
    }

    renderMembers(scrollToContentType=null) {
        let membersDiv = $(`#ct-group-${this.index}-members-div`)
        let contentTypesDiv = $(`#${this.contentTypesDivID}`)
        let scrollToControl = null

        membersDiv.find(`.corpora-content-table[data-content-type]`).each(function() {
            let ctTable = $(this)
            ctTable.detach().appendTo(contentTypesDiv)
        })

        membersDiv.empty()

        if (this.members.length) {
            this.members.forEach((member, memberIndex) => {
                let ctTableRow = $(`#${this.contentTypesDivID} .corpora-content-table[data-content-type="${member.name}"]`)
                let ctContainer = membersDiv

                if (member.display_preference === 'half') {
                    ctContainer = $(`.ct-group-${this.index}-member-col.open`)
                    if (!ctContainer.length) {
                        membersDiv.append(`
                            <div class="row">
                                <div class="col-md-6 ct-group-${this.index}-member-col open"></div>
                                <div class="col-md-6 ct-group-${this.index}-member-col open"></div>
                            </div>
                        `)
                        ctContainer = $(`.ct-group-${this.index}-member-col.open`)
                    }
                    ctContainer = ctContainer.first()
                    ctContainer.removeClass('open')
                } else if (member.display_preference === 'minimized') {
                    membersDiv.append(`
                        <details id="ct-group-${this.index}-member-detail-${memberIndex}" class="content-type-group-member-minimized">
                        <summary><h4>${this.corpus.content_types[member.name].plural_name}</h4></summary>
                        </details>
                    `)
                    ctContainer = $(`#ct-group-${this.index}-member-detail-${memberIndex}`)
                }

                if (ctTableRow.length) {
                    ctContainer.append(`
                        <div class="content-type-group-member-controls ${this.editing ? '' : 'd-none'}">
                            <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                                data-ct="${member.name}" data-action="move-up"
                                data-toggle="tooltip" title="Move up" ${memberIndex === 0 ? 'disabled' : ''}>
                                <span class="fas fa-sort-up"></span></button>
                            <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                                data-ct="${member.name}" data-action="move-down"
                                data-toggle="tooltip" title="Move down" ${memberIndex === (this.members.length - 1) ? 'disabled' : ''}>
                                <span class="fas fa-sort-down"></span></button>
                            <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                                data-ct="${member.name}" data-action="minimize"
                                data-toggle="tooltip" title="Minimize" ${member.display_preference === 'minimized' ? 'disabled' : ''}>
                                <span class="far fa-window-minimize"></span></button>
                            <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                                data-ct="${member.name}" data-action="maximize"
                                data-toggle="tooltip" title="Maximize" ${member.display_preference === 'full' ? 'disabled' : ''}>
                                <span class="far fa-window-maximize"></span></button>
                            <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                                data-ct="${member.name}" data-action="half-size"
                                data-toggle="tooltip" title="Make half-sized" ${member.display_preference === 'half' ? 'disabled' : ''}>
                                <span class="fas fa-columns"></span></button>
                            <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                                data-ct="${member.name}" data-action="remove"
                                data-toggle="tooltip" title="Remove from group">
                                <span class="fas fa-trash-alt"></span></button>
                        </div>
                    `)

                    ctTableRow.detach().appendTo(ctContainer)
                    if (scrollToContentType === member.name) {
                        if (member.display_preference === 'full') scrollToControl = ctTableRow
                        else scrollToControl = ctContainer
                    }
                }
            })

            let sender = this
            let memberControls = $(`.ct-group-${this.index}-member-control`)

            memberControls.tooltip('update')
            memberControls.click(function () {
                let button = $(this)
                let ct = button.data('ct')
                let action = button.data('action')

                button.tooltip('hide')
                sender.changeMember(ct, action)
            })
            if (scrollToControl) setTimeout(() => scrollToControl[0].scrollIntoView({behavior: 'smooth'}), 500)
        }
    }

    edit() {
        let ctSelectorDiv = $(`#ct-group-${this.index}-ct-selector-div`)
        let ctSelector = $(`#ct-group-${this.index}-ct-selector`)
        let ctgControlsDiv = $(`#ct-group-${this.index}-controls-div`)
        let ctgMemberControls = $(`.content-type-group-member-controls`)

        ctSelector.empty()

        $(`#${this.contentTypesDivID} .corpora-content-table`).each(function() {
            let ctName = $(this).data('content-type')
            ctSelector.append(`<option value="${ctName}">${ctName}</option>`)
        })

        ctSelectorDiv.removeClass('d-none')
        ctgControlsDiv.removeClass('d-none')
        ctgControlsDiv.addClass('d-flex')
        ctgMemberControls.removeClass('d-none')

        if (!this.editing) {
            tinymce.init(
                {
                    selector: `#ct-group-${this.index}-description`,
                    width: '100%',
                    min_height: '200px',
                    plugins: 'autoresize link image media code table',
                    menubar: 'edit insert media view format table tools help',
                    image_advtab: true
                }
            )
        }

        this.editing = true
    }

    changeMember(contentType, action) {
        let memberIndex = -1
        for (let i = 0; i < this.members.length; i++) {
            if (this.members[i].name === contentType) memberIndex = i
        }
        if (memberIndex > -1) {
            let validMove = false

            switch(action) {
                case 'move-up':
                    if (memberIndex > 0) {
                        let prevMember = this.members[memberIndex - 1]
                        let currMember = this.members[memberIndex]

                        this.members[memberIndex - 1] = currMember
                        this.members[memberIndex] = prevMember



                        validMove = true
                    }
                    break
                case 'move-down':
                    if (memberIndex < this.members.length - 1) {
                        let nextMember = this.members[memberIndex + 1]
                        let currMember = this.members[memberIndex]
                        this.members[memberIndex + 1] = currMember
                        this.members[memberIndex] = nextMember
                        validMove = true
                    }
                    break
                case 'minimize':
                    this.members[memberIndex].display_preference = 'minimized'
                    validMove = true
                    break
                case 'maximize':
                    this.members[memberIndex].display_preference = 'full'
                    validMove = true
                    break
                case 'half-size':
                    this.members[memberIndex].display_preference = 'half'
                    validMove = true
                    break
                case 'remove':
                    this.members.splice(memberIndex, 1)
                    validMove = true
                    if (this.members.length) contentType = this.members[0].name
            }

            if (validMove) {
                let sender = this
                this.save(function(response) {
                    if (response.success) sender.renderMembers(contentType)
                })
            }
        }
    }

    validate() {
        let valid = true
        let message = ''
        if (!(this.title != null && this.title.length)) {
            valid = false
            message = "Content groups must have a title. "
        }

        if (valid) {
            let groupedContentTypes = []
            if ('content_type_groups' in this.corpus) {
                this.corpus.content_type_groups.forEach(contentGroup => {
                    if (contentGroup.title !== this.title) {
                        contentGroup.members.forEach(member => {
                            groupedContentTypes.push(member.name)
                        })
                    }
                })
            }
            this.members.forEach(member => {
                if (groupedContentTypes.includes(member.name)){
                    valid = false
                    message += `The same content type cannot belong to two content groups at once. ${member.name} already belongs to another content group.`
                }
            })
        }

        return [valid, message]
    }

    toJSON() {
        return JSON.stringify({
            title: this.title,
            description: this.description,
            members: this.members
        })
    }

    save(callback=null) {
        let [valid, message] = this.validate()
        if (valid) {
            if (this.editing) this.description = tinymce.get(`ct-group-${this.index}-description`).getContent()

            let sender = this
            this.corpora.make_request(
                `/api/corpus/${this.corpus.id}/content-group/`,
                'POST',
                {'content-group-json': this.toJSON(), 'action': sender.editing ? 'edit' : 'create'},
                function (response) {
                    if (callback != null) {
                        callback(response)
                    }
                }
            )
        }
    }

    delete() {
        let sender = this

        this.corpora.confirm_action(
            function() {
                sender.members = []
                sender.renderMembers()
                sender.corpora.make_request(
                    `/api/corpus/${sender.corpus.id}/content-group/`,
                    'POST',
                    {'content-group-json': sender.toJSON(), 'action': 'delete'},
                    function (response) {
                        if (response.success) {
                            $(`#ct-group-${sender.index}`).remove()
                        }
                    }
                )
            },
            'Confirm Content Group Deletion',
            `Are you sure you want to delete the "${sender.title}" Content Type Group? Deleting the group
                will not delete the content types belonging to it.`,
            'Delete',
            true
        )
    }
}

