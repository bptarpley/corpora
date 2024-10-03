function renderTimespanField(target) {
    if (target.hasOwnProperty('target')) target = target.target
    setTimespanValue(target)
}

function setTimespanValue(target) {
    if (target.hasOwnProperty('target')) target = target.target
    let id_prefix = $(target).data('id_prefix')
    let value_input = $(`#${id_prefix}-value`)
    let start_input = $(`#${id_prefix}-editor-start`)
    let end_input = $(`#${id_prefix}-editor-end`)
    let uncertain_input = $(`#${id_prefix}-editor-uncertain`)
    let granularity_input = $(`#${id_prefix}-editor-granularity`)
    let time_div = $(`#${id_prefix}-editor-time-row`)
    let start_time_input = $(`#${id_prefix}-editor-start-time`)
    let end_time_input = $(`#${id_prefix}-editor-end-time`)
    let alert_div = $(`#${id_prefix}-alert`)

    if (start_input.val().length) {
        let timespan = {
            start: start_input.val(),
            end: null,
            uncertain: false,
            granularity: 'Day'
        }

        if (end_input.length && end_input.val()) timespan.end = end_input.val()
        if (uncertain_input.length && uncertain_input.is(':checked')) timespan.uncertain = true
        if (granularity_input.length && granularity_input.val()) timespan.granularity = granularity_input.val()
        if (timespan.granularity === 'Time') {
            time_div.removeClass('d-none')
            if (start_time_input.length && start_time_input.val()) timespan.start = `${timespan.start} ${start_time_input.val()}`
            if (timespan.end && end_time_input.length && end_time_input.val()) timespan.end = `${timespan.end} ${end_time_input.val()}`
        } else time_div.addClass('d-none')

        if (timespan.end != null) {
            if (timespan.start >= timespan.end) alert_div.removeClass('d-none')
            else alert_div.addClass('d-none')
        }

        value_input.val(JSON.stringify(timespan))
    } else
        value_input.val(null)
}