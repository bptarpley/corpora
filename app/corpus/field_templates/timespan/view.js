function renderTimespan(target) {
    let timespan = {
        start: target.getAttribute('data-start'),
        end: target.getAttribute('data-end'),
        uncertain: target.getAttribute('data-uncertain') === "True" ? true : false,
        granularity: target.getAttribute('data-granularity'),
    }
    target.innerHTML = get_timespan_string(timespan)
}

function get_timespan_string(timespan) {
    let uncertain_prefix = ''
    let granularity = timespan.granularity ?? 'Day'
    let start_string = ''
    let end_string = ''
    let range_combinator = ''

    if (timespan.start) {
        start_string = get_date_string(timespan.start, granularity)
        if (timespan.uncertain) uncertain_prefix = 'Around '

        if (timespan.end) {
            end_string = get_date_string(timespan.end, granularity)

            if (start_string !== end_string) {
                range_combinator = ' - '
                if (timespan.uncertain) {
                    uncertain_prefix = 'Between '
                    range_combinator = ' and '
                }
            } else end_string = ''
        }
    }

    return `${uncertain_prefix}${start_string}${range_combinator}${end_string}`
}

function get_date_string(timestamp, granularity='Day', adjust_for_timezone=true) {
    let date = new Date(timestamp)
    if (granularity === 'Day')
        return date.toISOString().split('T')[0]
    else if (granularity === 'Year')
        return date.toLocaleString('default', { year: 'numeric' })
    else if (granularity === 'Month')
        return date.toLocaleString('default', { month: 'long', year: 'numeric' })
    else if (granularity === 'Time')
        return get_time_string(timestamp, false, false, adjust_for_timezone)
}

function get_time_string(timestamp, from_mongo=true, just_time=false, adjust_for_timezone=true) {
    let date = null
    if (from_mongo) date = new Date(timestamp*1000)
    else date = new Date(timestamp)

    let representation = null
    if (adjust_for_timezone) representation = date.toLocaleString('en-US', { timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone })
    else representation = date.toLocaleString('en-US')

    if (just_time) representation = representation.split(', ')[1]
    return representation
}