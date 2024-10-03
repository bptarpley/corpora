function renderTextField(target) {
    if (target.hasOwnProperty('target')) target = target.target
    target.parentNode.setAttribute('data-replicated_value', target.value)
}