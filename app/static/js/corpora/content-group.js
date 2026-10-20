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

        this.editing = false
        this.contentTypesDivID = null
    }

    render(groupContainer, ctContainerID) {
        this.contentTypesDivID = ctContainerID
        let editButtonHTML = ''
        if (this.canEdit) {
            editButtonHTML = `
                <button id="ct-group-${this.index}-edit-button" class="btn btn-sm btn-primary" data-bs-toggle="tooltip" data-bs-placement="top" title="Edit">
                    <span class="fas fa-edit"></span>
                </button>
            `
        }

        appendToEl(groupContainer, `
            <div id="ct-group-${this.index}" class="alert alert-info content-type-group mt-4 pb-4" data-title="${this.title}">
                <h2 class="content-type-group-header d-flex justify-content-between">${this.title}${editButtonHTML}</h2>
                <div id="ct-group-${this.index}-controls-div" class="d-none my-2 justify-content-between align-bottom">
                    <span>
                        <button id="ct-group-${this.index}-delete-button" type="button" class="btn btn-danger me-4" data-title="${this.title}" data-bs-toggle="tooltip" title="Delete Group">
                            <span class="fas fa-trash-alt"></span>
                        </button>
                        <button id="ct-group-${this.index}-cancel-button" type="button" class="btn btn-secondary me-1">Cancel</button>
                        <button id="ct-group-${this.index}-save-button" type="button" class="btn btn-primary">Save Changes</button>
                    </span>
                    <span class="text-muted" style="align-self: flex-end;">Deleting a Content Type group will not delete its Content Types.</span>
                </div>
                <div id="ct-group-${this.index}-description" class="content-type-group-description ${this.description ? 'mt-2 alert alert-info' : ''}">${this.description ? this.description : ''}</div>
                <div id="ct-group-${this.index}-ct-selector-div" class="d-none mt-2">
                    <label for="ct-group-${this.index}-ct-selector" class="form-label">Select a Content Type to add to this group:</label>
                    <select id="ct-group-${this.index}-ct-selector" class="form-select-sm bg-primary ms-1 me-1"></select>
                    <button type="button" class="btn btn-sm btn-secondary" id="ct-group-${this.index}-ct-add-button">Go</button>
                </div>
                <div id="ct-group-${this.index}-members-div"></div>
            </div>
        `)
        this.renderMembers()

        let ctSelector = getEl(`ct-group-${this.index}-ct-selector`)
        let ctgCancelButton = getEl(`ct-group-${this.index}-cancel-button`)

        onEl(getEl(`ct-group-${this.index}-edit-button`), 'click', () => this.edit())

        onEl(getEl(`ct-group-${this.index}-ct-add-button`), 'click', () => {
            this.members.push({
                name: getVal(ctSelector),
                display_preference: 'full'
            })
            this.save(response => {
                if (response.success) {
                    this.renderMembers()
                    this.edit()
                }
            })
        })

        onEl(ctgCancelButton, 'click', () => {
            if (!this.editing) return

            let descBoxID = `ct-group-${this.index}-description`

            getEl(`ct-group-${this.index}-ct-selector-div`).classList.add('d-none')
            let controlsDiv = getEl(`ct-group-${this.index}-controls-div`)
            controlsDiv.classList.remove('d-flex')
            controlsDiv.classList.add('d-none')
            forElsMatching('.content-type-group-member-controls', el => el.classList.add('d-none'))
            getEl(`ct-group-${this.index}-edit-button`).classList.remove('d-none')

            tinymce.get(descBoxID).remove()
            getEl(descBoxID).innerHTML = this.description

            this.editing = false
        })

        onEl(getEl(`ct-group-${this.index}-save-button`), 'click', () => {
            this.save(response => {
                if (response.success) ctgCancelButton.click()
            })
        })

        onEl(getEl(`ct-group-${this.index}-delete-button`), 'click', () => this.delete())

        initTooltips(getEl(`ct-group-${this.index}`))
    }

    scrollTo() {
        getEl(`ct-group-${this.index}`).scrollIntoView({behavior: 'smooth'})
    }

    renderMembers(scrollToContentType=null) {
        let membersDiv = getEl(`ct-group-${this.index}-members-div`)
        let contentTypesDiv = getEl(this.contentTypesDivID)
        let scrollToControl = null

        // park any tables we already own back in the main container before re-laying
        // out, so they survive membersDiv being emptied (appendChild moves the node
        // and keeps its listeners).
        membersDiv.querySelectorAll('.corpora-content-table[data-content-type]').forEach(ctTable => {
            contentTypesDiv.appendChild(ctTable)
        })

        clearEl(membersDiv)
        if (!this.members.length) return

        this.members.forEach((member, memberIndex) => {
            let ctTableRow = contentTypesDiv.querySelector(`.corpora-content-table[data-content-type="${member.name}"]`)
            let ctContainer = membersDiv

            if (member.display_preference === 'half') {
                ctContainer = getElWithQuery(`.ct-group-${this.index}-member-col.open`)
                if (!ctContainer) {
                    appendToEl(membersDiv, `
                        <div class="row">
                            <div class="col-md-6 ct-group-${this.index}-member-col open"></div>
                            <div class="col-md-6 ct-group-${this.index}-member-col open"></div>
                        </div>
                    `)
                    ctContainer = getElWithQuery(`.ct-group-${this.index}-member-col.open`)
                }
                ctContainer.classList.remove('open')
            } else if (member.display_preference === 'minimized') {
                appendToEl(membersDiv, `
                    <details id="ct-group-${this.index}-member-detail-${memberIndex}" class="content-type-group-member-minimized">
                    <summary><h4>${this.corpus.content_types[member.name].plural_name}</h4></summary>
                    </details>
                `)
                ctContainer = getEl(`ct-group-${this.index}-member-detail-${memberIndex}`)
            }

            if (!ctTableRow) return

            appendToEl(ctContainer, `
                <div class="content-type-group-member-controls ${this.editing ? '' : 'd-none'}">
                    <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                        data-ct="${member.name}" data-action="move-up"
                        data-bs-toggle="tooltip" title="Move up" ${memberIndex === 0 ? 'disabled' : ''}>
                        <span class="fas fa-sort-up"></span></button>
                    <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                        data-ct="${member.name}" data-action="move-down"
                        data-bs-toggle="tooltip" title="Move down" ${memberIndex === (this.members.length - 1) ? 'disabled' : ''}>
                        <span class="fas fa-sort-down"></span></button>
                    <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                        data-ct="${member.name}" data-action="minimize"
                        data-bs-toggle="tooltip" title="Minimize" ${member.display_preference === 'minimized' ? 'disabled' : ''}>
                        <span class="far fa-window-minimize"></span></button>
                    <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                        data-ct="${member.name}" data-action="maximize"
                        data-bs-toggle="tooltip" title="Maximize" ${member.display_preference === 'full' ? 'disabled' : ''}>
                        <span class="far fa-window-maximize"></span></button>
                    <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                        data-ct="${member.name}" data-action="half-size"
                        data-bs-toggle="tooltip" title="Make half-sized" ${member.display_preference === 'half' ? 'disabled' : ''}>
                        <span class="fas fa-columns"></span></button>
                    <button class="btn btn-sm btn-primary ct-group-${this.index}-member-control"
                        data-ct="${member.name}" data-action="remove"
                        data-bs-toggle="tooltip" title="Remove from group">
                        <span class="fas fa-trash-alt"></span></button>
                </div>
            `)

            ctContainer.appendChild(ctTableRow)
            if (scrollToContentType === member.name) {
                scrollToControl = member.display_preference === 'full' ? ctTableRow : ctContainer
            }
        })

        forElsMatching(`.ct-group-${this.index}-member-control`, button => {
            onlyOnEl(button, 'click', () => {
                hideTooltip(button)
                this.changeMember(button.dataset.ct, button.dataset.action)
            })
        })
        initTooltips(membersDiv)

        if (scrollToControl) setTimeout(() => scrollToControl.scrollIntoView({behavior: 'smooth'}), 500)
    }

    edit() {
        if (!this.canEdit) return

        let ctSelector = getEl(`ct-group-${this.index}-ct-selector`)
        let ctgControlsDiv = getEl(`ct-group-${this.index}-controls-div`)

        clearEl(ctSelector)
        forElsMatching(`#${this.contentTypesDivID} .corpora-content-table`, ctTable => {
            let ctName = ctTable.dataset.contentType
            appendToEl(ctSelector, `<option value="${ctName}">${ctName}</option>`)
        })

        getEl(`ct-group-${this.index}-edit-button`).classList.add('d-none')
        getEl(`ct-group-${this.index}-ct-selector-div`).classList.remove('d-none')
        ctgControlsDiv.classList.remove('d-none')
        ctgControlsDiv.classList.add('d-flex')
        forElsMatching('.content-type-group-member-controls', el => el.classList.remove('d-none'))

        if (!this.editing) {
            tinymce.init(tinymceConfig({
                selector: `#ct-group-${this.index}-description`
            }))
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
                this.save(response => {
                    if (response.success) this.renderMembers(contentType)
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

        // previously this just fell through silently, so a failed validation looked
        // to the user like the save button did nothing.
        if (!valid) {
            this.corpora.confirm_action(
                () => this.corpora.cancel_action(),
                'Unable to Save Content Group',
                message,
                'Okay',
                false
            )
            return
        }

        if (this.editing) this.description = tinymce.get(`ct-group-${this.index}-description`).getContent()

        this.corpora.make_request(
            `/api/corpus/${this.corpus.id}/content-group/`,
            'POST',
            {'content-group-json': this.toJSON(), 'action': this.editing ? 'edit' : 'create'},
            response => {
                if (callback != null) callback(response)
            }
        )
    }

    delete() {
        this.corpora.confirm_action(
            () => {
                this.members = []
                this.renderMembers()
                this.corpora.make_request(
                    `/api/corpus/${this.corpus.id}/content-group/`,
                    'POST',
                    {'content-group-json': this.toJSON(), 'action': 'delete'},
                    response => {
                        if (response.success) removeEl(getEl(`ct-group-${this.index}`))
                    }
                )
            },
            'Confirm Content Group Deletion',
            `Are you sure you want to delete the "${this.title}" Content Type Group? Deleting the group
                will not delete the content types belonging to it.`,
            'Delete',
            true
        )
    }
}

