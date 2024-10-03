function renderTimespan(target) {
    let timespan = {
        start: target.getAttribute('data-start'),
        end: target.getAttribute('data-end'),
        uncertain: target.getAttribute('data-uncertain') === "True" ? true : false,
        granularity: target.getAttribute('data-granularity'),
    }
    target.innerHTML = corpora.timespan_string(timespan)
}
