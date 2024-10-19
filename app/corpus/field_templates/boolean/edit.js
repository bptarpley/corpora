function toggleBooleanField(target) {
    if (target.hasOwnProperty('target')) target = target.target
    target = $(target)

    let value_field = $(`#${target.data('value_field')}`)
    value_field.val(target[0].checked)
}