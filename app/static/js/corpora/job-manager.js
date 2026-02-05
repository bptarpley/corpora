class JobManager {
    constructor(config={}) {
        this.jobs_container = 'jobs_container' in config ? config.jobs_container : null
        this.provenance_container = 'provenance_container' in config ? config.provenance_container : null
        this.provenance = 'provenance' in config ? config.provenance : []
        this.corpora = 'corpora' in config ? config.corpora : null
        this.corpus = 'corpus' in config ? config.corpus : null
        this.content_type = 'content_type' in config ? config.content_type : null
        this.content_id = 'content_id' in config ? config.content_id : null
        this.scholar_id = 'scholar_id' in config ? config.scholar_id : null
        this.custom_parameter_types = 'custom_parameter_types' in config ? config.custom_parameter_types : {}
        this.scholar = null
        this.jobsites = []
        this.local_jobsite_id = null
        this.jobs_registered = new Set()
        this.job_modal = $('#job-modal')
        this.report_modal = $('#job-report-modal')
        this.job_report_timer = null

        let sender = this

        // get info about this scholar's relationship to the corpus.
        this.corpora.get_scholar(this.scholar_id, function(scholar) {
            sender.scholar = scholar
            sender.scholar.role = 'Viewer'
            if (sender.corpus.id in sender.scholar.available_corpora)
                sender.scholar.role = sender.scholar.available_corpora[sender.corpus.id]['role']

            // we only proceed setting things up if they are an admin or an editor
            if (['Admin', 'Editor'].includes(sender.scholar.role)) {
                // setup the job queue viewer
                if (sender.jobs_container) {
                    sender.jobs_container = $(`#${sender.jobs_container}`)
                    sender.corpora.get_jobs(sender.corpus.id, sender.content_type, sender.content_id, {}, function(jobs) {
                        if (jobs.records.length) {
                            jobs.records.forEach(job => {
                                sender.register_job(
                                    job.id,
                                    job.task_name,
                                    job.status,
                                    job.configuration.parameters ? job.configuration.parameters : null,
                                    job.report_path,
                                    job.submitted_time,
                                    null,
                                    job.percent_complete
                                )
                            })
                        } else {
                            sender.report_no_jobs()
                        }
                    })

                    // start listening to job events
                    sender.corpus.event_callbacks['job'] = function (job) {
                        sender.update_job(job)
                    }

                    // load provenance if provided
                    if (sender.provenance_container) {
                        sender.provenance_container = $(`#${sender.provenance_container}`)
                        if (sender.provenance.length) {
                            sender.provenance.forEach(prov => sender.register_job(
                                prov.job_id,
                                prov.task_name,
                                prov.status,
                                prov.task_configuration.parameters ? prov.task_configuration.parameters : null,
                                prov.report_path,
                                prov.submitted,
                                prov.completed,
                                null
                            ))
                        } else {
                            sender.report_no_jobs(true)
                        }

                        $('body').on('click', '.job-retry-button', function() {
                            let retry_button = $(this)
                            let job_id = retry_button.data('job-id')

                            if (sender.jobs_registered.has(job_id)) sender.jobs_registered.delete(job_id)
                            sender.corpora.retry_job(
                                sender.corpus.id,
                                retry_button.data('content-type'),
                                retry_button.data('content-id'),
                                retry_button.data('job-id'),
                                function(data) {
                                    $(`#provenance-${job_id}-div`).remove()
                                    if ($('.provenance-container').length === 0) {
                                        sender.report_no_jobs(true)
                                    }
                                }
                            )
                        })
                    }

                    $('body').on('click', '.job-report-button', function() {
                        sender.view_job_report($(this).data('job-id'))
                    })
                }
            }

            // we now have a scholar with "available" (in terms of permission to use) jobsites and tasks specified.
            // despite having permissions to run a given task on a jobsite, let's make sure these jobsites and tasks
            // exist so we can present them as potential jobs to enqueue
            sender.corpora.get_jobsites(function (jobsites) {
                let jobsite_selector_options = ''
                jobsites.forEach(js => { if (sender.scholar.available_jobsites.includes(js.id)) {
                    sender.jobsites.push(js)
                    if (js.name === 'Local') {
                        sender.local_jobsite_id = js.id
                    }
                    jobsite_selector_options += `
                        <option value="${js.id}" class="${js.type}" ${js.name === 'Local' ? 'selected' : ''}>
                            ${js.name}
                        </option>
                    `
                }})

                // now that we have jobsites that both exist and are available to the scholar, let's do the same for
                // tasks. the task API endpoint already filters tasks by permissions
                sender.corpora.get_tasks(null, function(tasks) {
                    tasks.forEach(task => {
                        for (let js_index = 0; js_index < sender.jobsites.length; js_index ++) {
                            if (task.name in sender.jobsites[js_index].task_registry) {
                                sender.jobsites[js_index].task_registry[task.name] = task
                            }
                        }
                    })

                    // now that we have a filtered list of jobsites and tasks, let's build the UI for launching and
                    // monitoring jobs
                    if (!sender.job_modal.length) {
                        $('body').prepend(`
                            <div class="modal fade" id="job-modal" tabindex="-1" role="dialog" aria-labelledby="job-modal-label" aria-hidden="true">
                                <div class="modal-dialog" role="document">
                                    <div class="modal-content">
                                            <input type="hidden" id="job-content-type">
                                            <input type="hidden" id="job-content-id">
                                            <div class="modal-header">
                                                <h5 class="modal-title" id="job-modal-label">Run a Job</h5>
                                                <button type="button" class="btn-close" data-dismiss="modal" aria-label="Close">
                                                </button>
                                            </div>
                                            <div class="modal-body">
                                                <div class="form-group">
                                                    <label for="jobsite-selector" class="form-label">Jobsite</label>
                                                    <select id="jobsite-selector" class="form-select" name="jobsite">
                                                        ${jobsite_selector_options}
                                                    </select>
                                                </div>
                                                <div id="task-selector-div" class="form-group">
                                                    <label for="task-selector" class="form-label">Task</label>
                                                    <select id="task-selector" class="form-select" name="task">
                                                    </select>
                                                </div>
                                                <div id="task-parameters-div">
                                                </div>
                                            </div>
                                            <div class="modal-footer">
                                                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                                                <button type="button" class="btn btn-primary" id="job-submit-button" disabled>Run</button>
                                            </div>
                                    </div>
                                </div>
                            </div>
                        `)
                        sender.job_modal = $('#job-modal')

                        $('#jobsite-selector').change(function() {
                            sender.load_tasks()
                        })

                        $('#task-selector').change(function() {
                            let task_id = $('#task-selector').val()
                            let jobsite_id = $('#jobsite-selector').val()

                            sender.jobsites.forEach(jobsite => {
                                if (jobsite.id === jobsite_id) {
                                    for (let task_name in jobsite.task_registry) {
                                        let task = jobsite.task_registry[task_name]
                                        if (task.id === task_id) {
                                            sender.load_task_parameters(task)
                                        }
                                    }
                                }
                            })
                        })

                        $('#job-submit-button').click(function () {
                            let job_submission = {
                                jobsite_id: $('#jobsite-selector').val(),
                                task_id: $('#task-selector').val(),
                                content_type: $('#job-content-type').val(),
                                content_id: $('#job-content-id').val() ? $('#job-content-id').val() : null,
                                parameters: {}
                            }

                            $('.job-parameter-value').each(function() {
                                let param = $(this)
                                if (param.attr('type') === 'checkbox')
                                    job_submission['parameters'][param.attr('name')] = param.is(':checked')
                                else
                                    job_submission['parameters'][param.attr('name')] = param.val()
                            })

                            sender.corpora.submit_jobs(sender.corpus.id, [job_submission], function() {
                                sender.job_modal.modal('hide')
                            })
                        })


                    }

                    if (!sender.report_modal.length) {
                        $('body').prepend(`
                            <div class="modal fade" id="job-report-modal" tabindex="-1" role="dialog" aria-labelledby="job-report-modal-label" aria-hidden="true">
                                <div class="modal-dialog modal-lg" role="document">
                                    <div class="modal-content">
                                        <div class="modal-header">
                                            <h5 class="modal-title">Job Report</h5>
                                            <button type="button" class="btn-close" data-dismiss="modal" aria-label="Close">
                                            </button>
                                        </div>
                                        <div class="modal-body">
                                            <pre id="job-report-div">Loading...</pre>
                                        </div>
                                        <div class="modal-footer">
                                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `)
                        sender.report_modal = $('#job-report-modal')
                    }
                })
            })
        })
    }

    load_tasks(content_type=null, selectedJobsiteId=null, selectedTaskId=null) {
        let jobsite_selector = $('#jobsite-selector')
        let task_selector = $('#task-selector')

        if (selectedJobsiteId !== null) jobsite_selector.val(selectedJobsiteId)
        task_selector.empty()

        let first = true
        this.jobsites.forEach(jobsite => {
            if (jobsite.id === jobsite_selector.val()) {
                for (let task_name in jobsite.task_registry) {
                    let task = jobsite.task_registry[task_name]

                    if ((!content_type || content_type === task.content_type) && task.track_provenance)
                    {
                        let selected = ''
                        if (selectedTaskId === task.id) selected = ' selected'

                        task_selector.append(`
                            <option class="job-task" value="${task.id}"${selected}>
                                ${task.name}
                            </option>
                        `)
                        if ((selectedTaskId === null && first) || (selectedTaskId !== null && selectedTaskId === task.id)) {
                            this.load_task_parameters(task)
                            first = false
                        }
                    }
                }
            }
        })

        if ($('option.job-task').length) {
            $(`#task-selector-div`).removeClass("d-none")
            $(`#job-submit-button`).attr('disabled', false)
        } else {
            $(`#task-selector-div`).addClass("d-none")
            $(`#job-submit-button`).attr('disabled', true)
        }
    }

    load_task_parameters(task) {
        let task_parameters_div = $('#task-parameters-div')
        let parameters = task['configuration']['parameters']

        task_parameters_div.empty()

        for (let parameter in parameters) {
            let parameter_html = ''

            if (parameters[parameter].hasOwnProperty('type')) {
                if (parameters[parameter].type in this.custom_parameter_types) {
                    parameter_html = this.custom_parameter_types[parameters[parameter].type](parameter, parameters[parameter])
                } else {
                    let note_html = ''
                    if (parameters[parameter].hasOwnProperty('note')) {
                        note_html = `<span class='text-muted'>${parameters[parameter]['note']}</span>`
                    }

                    if (parameters[parameter]['type'] === 'corpus_file') {
                        let select_options = ''
                        Object.keys(this.corpus.files).forEach(file_key => {
                            select_options += `<option value="${file_key}">${this.corpus.files[file_key].basename}</option>`
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-file-selector" class="form-label">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-file-selector" class="form-select job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'corpus_repo') {
                        let select_options = ''
                        Object.keys(this.corpus.repos).forEach(repo_name => {
                            select_options += `<option value="${repo_name}">${repo_name}</option>`
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-repo-selector" class="form-label">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-repo-selector" class="form-select job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'content_type') {
                        let select_options = ''
                        Object.keys(this.corpus.content_types).forEach(ct => {
                            select_options += `<option value="${ct}">${this.corpus.content_types[ct].name}</option>`
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-ct-selector" class="form-label">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-ct-selector" class="form-select job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'content_type_field') {
                        let select_options = ''
                        Object.keys(this.corpus.content_types).forEach(ct => {
                            this.corpus.content_types[ct].fields.map(f => {
                                select_options += `<option value="${ct}->${f.name}">${ct} -> ${f.label}</option>`
                            })
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-ct-field-selector" class="form-label">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-ct-field-selector" class="form-select job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'xref') {
                        parameter_html = `
                          <div class="form-group">
                            <label for="${parameter}-content-label" class="form-label">${parameters[parameter]['label']}</label>
                            <input id="${parameter}-content-label" type="text" readonly>
                            <button id="${parameter}-selection-button" class="btn btn-secondary">Select</button>
                            <input type="hidden" id="${parameter}-content-id" class="job-parameter-value" name="${parameter}">
                          </div>
                        `
                    } else if (parameters[parameter]['type'] === 'boolean') {
                        let checked = parameters[parameter]['value'] ? 'checked' : ''

                        parameter_html = `
                            <div class="form-check">
                                <input id="${parameter}-boolean-checkbox" type="checkbox" class="form-check-input job-parameter-value" name="${parameter}" ${checked}>
                                <label for="${parameter}-boolean-checkbox" class="form-check-label">${parameters[parameter]['label']}</label><br />
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'choice' && parameters[parameter].hasOwnProperty('choices')) {
                        let select_options = ''
                        parameters[parameter]['choices'].forEach(choice => {
                            select_options += `<option>${choice}</option>\n`
                        })

                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-choice-selector" class="form-label">${parameters[parameter]['label']}</label>
                                <select id="${parameter}-choice-selector" class="form-select job-parameter-value" name="${parameter}">
                                    ${select_options}
                                </select>
                                ${note_html}
                            </div>
                        `
                    } else if (parameters[parameter]['type'] === 'pep8_text') {
                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-pep8-text-box" class="form-label">${parameters[parameter]['label']}</label>
                                <input id="${parameter}-pep8-text-box" type="text" class="form-control job-parameter-value" name="${parameter}" />
                                ${note_html}
                            </div>
                        `
                    } else if (['text', 'password'].includes(parameters[parameter]['type'])) {
                        parameter_html = `
                            <div class="form-group">
                                <label for="${parameter}-text-box" class="form-label">${parameters[parameter]['label']}</label>
                                <input id="${parameter}-text-box" type="${parameters[parameter]['type']}" class="form-control job-parameter-value" name="${parameter}" />
                                ${note_html}
                            </div>
                        `
                    }
                }

                task_parameters_div.append(parameter_html)

                if (parameters[parameter]['type'] === 'pep8_text') {
                    let pep8_box = $(`#${parameter}-pep8-text-box`)
                    pep8_box.focusout(function () {
                        pep8_box.val(this.corpora.pep8_variable_format(pep8_box.val()))
                    })
                } else if (parameters[parameter]['type'] === 'xref') {
                    let selector = new ContentSelector({
                        id_element: $(`#${parameter}-content-id`),
                        label_element: $(`#${parameter}-content-label`),
                        previous_modal: this.job_modal,
                        corpora: corpora,
                        corpus: corpus,
                        content_type: parameters[parameter].content_type
                    })

                    $(`#${parameter}-selection-button`).click(function() {
                        selector.select()
                    })
                }
            }
        }
    }

    get_local_task_id(task_name) {
        let taskID = null

        this.jobsites.forEach(jobsite => {
            if (jobsite.id === this.local_jobsite_id) {
                console.log('found jobsite')
                if (task_name in jobsite.task_registry) {
                    taskID = jobsite.task_registry[task_name].id
                }
            }
        })
        return taskID
    }

    view_job_report(job_id) {
        $('#job-report-modal').modal()
        $('#job-report-modal').on('hidden.bs.modal', function (e) {
            clearTimeout(this.job_report_timer)
        })
        this.load_job_report(job_id)
    }

    load_job_report(job_id) {
        let no_cache_string = Math.random().toString(36).substring(7)
        let report_url = `/corpus/${this.corpus.id}/get-file/?path=job_reports/${job_id}.txt&no-cache=${no_cache_string}`
        let report_div = $('#job-report-div')
        let sender = this

        report_div.load(report_url, function() {
            report_div.scrollTop(report_div[0].scrollHeight)

            if (!report_div.html().includes('CORPORA JOB COMPLETE')) {
                sender.job_report_timer = setTimeout(() => { sender.load_job_report(job_id) }, 10000)
            }
        })
    }

    new_job(content_type, content_id, selectedTaskId=null) {
        this.load_tasks(content_type, null, selectedTaskId)
        if (content_type) $('#job-content-type').val(content_type)
        if (content_id) $('#job-content-id').val(content_id)
        this.job_modal.modal()
    }

    update_job(info) {
        let job_progress = $(`#job-${info.job_id}-progress`)
        if (job_progress.length) {
            job_progress.css("width", `${info.percent_complete}%`)
            job_progress.attr("aria-valuenow", info.percent_complete)
            job_progress.html(`${info.percent_complete}%`)

            if (info.status !== "running") {
                let stale_job_div = $(`#job-${info.job_id}-container`)
                if (stale_job_div.length) {
                    let sender = this
                    if (this.content_type === 'Corpus') {
                        this.corpora.get_corpus(this.corpus.id, function(data) {
                            if (data && data.provenance) {
                                data.provenance.forEach(prov => {
                                    if (prov.job_id === info.job_id) sender.register_job(
                                        prov.job_id,
                                        prov.task_name,
                                        prov.status,
                                        prov.task_configuration.parameters ? prov.task_configuration.parameters : null,
                                        prov.report_path,
                                        prov.submitted,
                                        prov.completed,
                                        null
                                    )
                                })
                            }
                        })
                    } else {
                        this.corpora.get_content(this.corpus.id, this.content_type, this.content_id, function (data) {
                            if (data && data.provenance) {
                                data.provenance.forEach(prov => {
                                    if (prov.job_id === info.job_id) sender.register_job(
                                        prov.job_id,
                                        prov.task_name,
                                        prov.status,
                                        prov.task_configuration.parameters ? prov.task_configuration.parameters : null,
                                        prov.report_path,
                                        prov.submitted,
                                        prov.completed,
                                        null
                                    )
                                })
                            }
                        })
                    }
                    stale_job_div.remove()

                    if ($('.job-container').length === 0) {
                        this.report_no_jobs()
                    }

                    let loc = window.location
                    let alert = $(`
                        <div class="alert alert-${info.status === "complete" ? 'success' : 'danger'}"
                            style="width: 95%; float: left; margin: 0px;">
                          Task <b>${info.task_name}</b> has completed ${info.status === "complete" ? 'successfully' : 'with errors'}.
                          You may wish to 
                          <button type="button"
                              class="btn btn-link"
                              onclick="window.location.replace('${loc.protocol}//${loc.host}${loc.pathname}')"
                              style="padding: 0px; vertical-align: unset;">
                            refresh the page
                          </button>
                          to view the results.
                        </div>
                    `)
                    Toastify({
                        node: alert[0],
                        duration: 10000,
                        close: true,
                        gravity: 'bottom',
                        position: 'right',
                        style: {
                            background: 'unset',
                            padding: '8px'
                        }
                    }).showToast()
                }
            }
        } else if (!this.jobs_registered.has(info.job_id)) {
            this.jobs_registered.add(info.job_id)
            let sender = this
            this.corpora.get_job(this.corpus.id, info.job_id, function (job) {
                sender.register_job(
                    job.id,
                    job.task_name,
                    job.status,
                    job.configuration.parameters ? job.configuration.parameters : null,
                    job.report_path,
                    job.submitted_time,
                    null,
                    job.percent_complete
                )
            })
        }
    }

    register_job(job_id, task_name, status, parameters, report_path, submitted, completed, percent_complete) {
        let container = this.jobs_container
        let report_button = ''
        let retry_button = ''
        let param_tray = ''
        let progress_bar = ''
        let container_class = 'job-container'
        let alert_class = 'success'

        if (['complete', 'error'].includes(status)) {
            container = this.provenance_container
            container_class = 'provenance-container'

            if (status === 'error') alert_class = 'danger'
        }

        if (container) {
            if ($(`.${container_class}`).length === 0) container.empty()

            if (['Admin', 'Editor'].includes(this.scholar.role)) {
                if (report_path) {
                    report_button = `
                        <button type="button" class="btn btn-sm btn-primary me-1 mb-1 job-report-button" data-job-id="${job_id}">View Report</button>
                    `
                }

                if (['complete', 'error'].includes(status)) {
                    retry_button = `
                        <button
                          type="button"
                          role="button"
                          class="btn btn-sm btn-danger me-1 mb-1 job-retry-button"
                          data-job-id="${job_id}"
                          data-content-type="${this.content_type}"
                          data-content-id="${this.content_id}"
                        >Retry</button>
                    `
                }

                if (parameters) {
                    let param_list = []
                    for (let param in parameters) {
                        param_list.push(`<b>${parameters[param].label}</b><br /> ${parameters[param].value}`)
                    }
                    param_tray = `
                        <a class="btn btn-sm btn-primary mt-1"
                           data-toggle="collapse"
                           href="#job-${job_id}-parameters"
                           role="button"
                           aria-expanded="false"
                           aria-controls="job-${job_id}-parameters">
                            Show Parameters
                        </a>
                        <div class="collapse mt-1" id="job-${job_id}-parameters">
                            <div class="card card-body" style="display: block;">
                                ${param_list.join('<br /><br />')}
                            </div>
                        </div>
                    `
                }

                if (percent_complete || percent_complete === 0) {
                    progress_bar = `
                        <div class="row">
                            <div class="col-sm-12">
                                <div id="job-${job_id}-progress"
                                    class="progress-bar progress-bar-striped bg-success progress-bar-animated mb-1"
                                    role="progressbar"
                                    aria-valuenow="${percent_complete}"
                                    aria-valuemin="0"
                                    aria-valuemax="100"
                                    style="width: ${percent_complete}%; height: 10px;">  
                                  ${percent_complete}%
                                </div>    
                            </div>
                        </div>
                    `
                }
            }

            container.prepend(`
                <div id="job-${job_id}-container" class="alert alert-${alert_class} ${container_class}">
                    ${progress_bar}
                    <div class="row">
                        <div class="col-sm-12 d-flex justify-content-between">
                            <span>
                                Task: <b>${task_name}</b><br />
                                Submitted: ${this.corpora.time_string(submitted)}<br />
                                ${completed ? `Completed: ${this.corpora.time_string(completed)}<br />` : ''}
                                ${param_tray}
                            </span>
                            <span class="text-right">
                                ${report_button}
                                ${retry_button}
                            </span>
                        </div>
                    </div>
                </div>
            `)
        }
    }

    report_no_jobs(completed=false) {
        let container = this.jobs_container
        let message_suffix = `jobs running for this ${this.content_type}`
        if (completed) {
            container = this.provenance_container
            message_suffix = `completed jobs for this ${this.content_type}`
        }
        container.html(`
            <div class="alert alert-info m-0">
                There are currently no ${message_suffix}.
            </div>
        `)
    }
}

