function renderRepoField(target) {
    if (target.hasOwnProperty('target')) target = target.target
    setRepoValueField(target)
}

function toggleRepoAuthCheckbox(target) {
    if (target.hasOwnProperty('target')) target = target.target
    let auth_box = $(target)
    let id_prefix = auth_box.data('id_prefix')
    let auth_div = $(`#${id_prefix}-credentials-div`)

    if (auth_box.is(':checked')) {
        auth_div.removeClass('d-none')
    }
    else {
        auth_div.addClass('d-none')
        $(`#${id_prefix}-user`).val('')
        $(`#${id_prefix}-pwd`).val('')
    }
}

function clickDeleteRepoButton(target) {
    if (target.hasOwnProperty('target')) target = target.target
    let button = $(target)
    let id_prefix = button.data('id_prefix')
    let repo_name = button.data('name')
    let field_name = button.data('field_name')

    corpora.make_request(
        '',
        'POST',
        {
            'delete-repo': 'y',
            'repo-name': repo_name,
            'field-name': field_name
        },
        function() {
            let deletion_div = $(`#${id_prefix}-deletion-div`)
            let name_box = $(`#${id_prefix}-name`)
            let url_box = $(`#${id_prefix}-url`)
            let auth_box = $(`#${id_prefix}-auth`)
            let branch_box = $(`#${id_prefix}-branch`)

            deletion_div.remove()
            name_box.val('')
            name_box.prop('disabled', false)
            url_box.val('')
            url_box.prop('disabled', false)
            auth_box.prop('disabled', false)
            branch_box.val('')
            branch_box.prop('disabled', false)
        }
    )

    return false
}

function setRepoValueField(target) {
    if (target.hasOwnProperty('target')) target = target.target
    let id_prefix = $(target).data('id_prefix')
    let value_field = $(`#${id_prefix}-value`)
    let name_box = $(`#${id_prefix}-name`)
    let url_box = $(`#${id_prefix}-url`)
    let auth_box = $(`#${id_prefix}-auth`)
    let user_box = $(`#${id_prefix}-user`)
    let pwd_box = $(`#${id_prefix}-pwd`)
    let branch_box = $(`#${id_prefix}-branch`)

    if (name_box.val()) {
        name_box.val(pep8_variable_format(name_box.val()))
    }

    if (name_box.val() && url_box.val() && branch_box.val()) {
        let value = {
            name: name_box.val(),
            url: url_box.val(),
            branch: branch_box.val()
        }

        if (auth_box.is(':checked')) {
            value['user'] = user_box.val()
            value['password'] = pwd_box.val()
        }

        value_field.val(JSON.stringify(value))
    } else {
        value_field.val(null)
    }
}