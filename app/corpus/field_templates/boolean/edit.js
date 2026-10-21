function toggleBooleanField(target) {
    target = elFromEventOrEl(target)

    setVal(getEl(target.dataset.value_field), target.checked)
}
