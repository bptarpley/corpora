function renderRepoField(target) {
    target = elFromEventOrEl(target)
    setRepoValueField(target)
}

function toggleRepoAuthCheckbox(target) {
    target = elFromEventOrEl(target)
    let id_prefix = target.dataset.id_prefix
    let auth_div = getEl(`${id_prefix}-credentials-div`)

    if (target.checked) {
        showEl(auth_div)
    }
    else {
        hideEl(auth_div)
        setVal(getEl(`${id_prefix}-user`), '')
        setVal(getEl(`${id_prefix}-pwd`), '')
    }
}

function clickDeleteRepoButton(target) {
    target = elFromEventOrEl(target)
    let id_prefix = target.dataset.id_prefix
    let repo_name = target.dataset.name
    let field_name = target.dataset.field_name

    corpora.make_request(
        '',
        'POST',
        {
            'delete-repo': 'y',
            'repo-name': repo_name,
            'field-name': field_name
        },
        function() {
            let name_box = getEl(`${id_prefix}-name`)
            let url_box = getEl(`${id_prefix}-url`)
            let auth_box = getEl(`${id_prefix}-auth`)
            let branch_box = getEl(`${id_prefix}-branch`)

            removeEl(getEl(`${id_prefix}-deletion-div`))
            setVal(name_box, '')
            setDisabled(name_box, false)
            setVal(url_box, '')
            setDisabled(url_box, false)
            setDisabled(auth_box, false)
            setVal(branch_box, '')
            setDisabled(branch_box, false)
        }
    )

    return false
}

function setRepoValueField(target) {
    target = elFromEventOrEl(target)
    let id_prefix = target.dataset.id_prefix
    let value_field = getEl(`${id_prefix}-value`)
    let name_box = getEl(`${id_prefix}-name`)
    let url_box = getEl(`${id_prefix}-url`)
    let auth_box = getEl(`${id_prefix}-auth`)
    let user_box = getEl(`${id_prefix}-user`)
    let pwd_box = getEl(`${id_prefix}-pwd`)
    let branch_box = getEl(`${id_prefix}-branch`)

    if (getVal(name_box)) {
        setVal(name_box, corpora.pep8_variable_format(getVal(name_box)))
    }

    if (getVal(name_box) && getVal(url_box) && getVal(branch_box)) {
        let value = {
            name: getVal(name_box),
            url: getVal(url_box),
            branch: getVal(branch_box)
        }

        if (auth_box.checked) {
            value['user'] = getVal(user_box)
            value['password'] = getVal(pwd_box)
        }

        setVal(value_field, JSON.stringify(value))
    } else {
        setVal(value_field, null)
    }
}
