function renderTimespanField(target) {
    target = elFromEventOrEl(target)
    setTimespanValue(target)
}

function setTimespanValue(target) {
    target = elFromEventOrEl(target)
    let id_prefix = target.dataset.id_prefix
    let value_input = getEl(`${id_prefix}-value`)
    let start_input = getEl(`${id_prefix}-editor-start`)
    let end_input = getEl(`${id_prefix}-editor-end`)
    let uncertain_input = getEl(`${id_prefix}-editor-uncertain`)
    let granularity_input = getEl(`${id_prefix}-editor-granularity`)
    let time_div = getEl(`${id_prefix}-editor-time-row`)
    let start_time_input = getEl(`${id_prefix}-editor-start-time`)
    let end_time_input = getEl(`${id_prefix}-editor-end-time`)
    let alert_div = getEl(`${id_prefix}-alert`)

    if (getVal(start_input).length) {
        let timespan = {
            start: getVal(start_input),
            end: null,
            uncertain: false,
            granularity: 'Day'
        }

        if (end_input && getVal(end_input)) timespan.end = getVal(end_input)
        if (uncertain_input && uncertain_input.checked) timespan.uncertain = true
        if (granularity_input && getVal(granularity_input)) timespan.granularity = getVal(granularity_input)
        if (timespan.granularity === 'Time') {
            showEl(time_div)
            if (start_time_input && getVal(start_time_input)) timespan.start = `${timespan.start} ${getVal(start_time_input)}`
            if (timespan.end && end_time_input && getVal(end_time_input)) timespan.end = `${timespan.end} ${getVal(end_time_input)}`
        } else hideEl(time_div)

        if (timespan.end != null) {
            setElVisible(alert_div, timespan.start > timespan.end)
        }

        setVal(value_input, JSON.stringify(timespan))
    } else
        setVal(value_input, null)
}
