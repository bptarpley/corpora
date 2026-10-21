class JobManager {
    constructor(config={}) {
        this.jobs_container = config.jobs_container ?? null
        this.provenance_container = config.provenance_container ?? null
        this.provenance = config.provenance ?? []
        this.corpora = config.corpora ?? null
        this.corpus = config.corpus ?? null
        this.content_type = config.content_type ?? null
        this.content_id = config.content_id ?? null
        this.scholar_id = config.scholar_id ?? null
        this.custom_parameter_types = config.custom_parameter_types ?? {}
        this.poll_interval = config.poll_interval ?? 10000
        // task names to keep out of the launcher. document.html used to strip these
        // from the rendered <option>s on a 3 second setTimeout, which raced the two
        // API calls that build the modal.
        this.exclude_tasks = config.exclude_tasks ?? []

        this.scholar = null
        this.jobsites = []
        this.local_jobsite_id = null
        this.jobs_registered = new Set()
        this.job_report_timer = null
        this.jobs_poll_timer = null

        this.corpora.get_scholar(this.scholar_id, scholar => {
            this.scholar = scholar
            this.scholar.role = this._resolve_role(scholar)

            if (!this.can_manage_jobs) return

            this._setup_job_queue()
            this._setup_job_launcher()
        })
    }

    // ------------------------------------------------------------------------
    // MODES
    //
    // corpus mode    a corpus was supplied, so job updates arrive over SSE on
    //                that corpus' event channel.
    // instance mode  no corpus was supplied. SSE channels are per-corpus, so
    //                there is nothing to subscribe to; /api/jobs/ is polled
    //                instead. Restricted to Corpora admins, since it surfaces
    //                jobs belonging to every corpus.
    // ------------------------------------------------------------------------
    get instance_wide() {
        return !this.corpus
    }

    get can_manage_jobs() {
        return ['Admin', 'Editor'].includes(this.scholar?.role)
    }

    _resolve_role(scholar) {
        // instance mode deliberately requires admin rather than editor
        if (this.instance_wide) return scholar.is_admin ? 'Admin' : 'Viewer'
        return scholar.available_corpora[this.corpus.id]?.role ?? 'Viewer'
    }

    stop_polling() {
        clearTimeout(this.jobs_poll_timer)
        clearTimeout(this.job_report_timer)
    }

    // ------------------------------------------------------------------------
    // SETUP
    // ------------------------------------------------------------------------
    _setup_job_queue() {
        if (!this.jobs_container) return

        this.jobs_container = getEl(this.jobs_container)
        if (this.provenance_container) this.provenance_container = getEl(this.provenance_container)

        this._load_running_jobs()

        if (this.instance_wide) {
            this.jobs_poll_timer = setTimeout(() => this._poll_jobs(), this.poll_interval)
        } else {
            this.corpus.event_callbacks['job'] = job => {
                if (this.corpus.event_ids.has(job.event_id)) return
                this.corpus.event_ids.add(job.event_id)
                this.update_job(job)
            }
            this._load_provenance()
        }

        this._build_report_modal()
        this._rig_job_buttons()
    }

    // delegated from document.body so that job cards rendered later are covered
    _rig_job_buttons() {
        onDelegate(document.body, 'click', '.job-report-button', (evt, button) => {
            this.view_job_report(button.dataset.jobId, button.dataset.corpusId)
        })

        // retry buttons only ever appear on provenance entries, so there is
        // nothing to rig without a provenance container
        if (!this.provenance_container) return

        onDelegate(document.body, 'click', '.job-retry-button', (evt, button) => {
            let job_id = button.dataset.jobId

            this.jobs_registered.delete(job_id)
            removeEl(getEl(`job-${job_id}-container`))
            if (!getElWithQuery('.provenance-container')) this.report_no_jobs(true)

            this.corpora.retry_job(
                button.dataset.corpusId,
                button.dataset.contentType,
                button.dataset.contentId,
                job_id,
                () => {}
            )
        })
    }

    _load_running_jobs() {
        let corpus_id = this.instance_wide ? null : this.corpus.id

        this.corpora.get_jobs(corpus_id, this.content_type, this.content_id, {}, jobs => {
            if (jobs.records.length) jobs.records.forEach(record => this.register_job(this._job_from_record(record)))
            else this.report_no_jobs()
        })
    }

    _load_provenance() {
        if (!this.provenance_container) return

        if (this.provenance.length) this.provenance.forEach(prov => this.register_job(this._job_from_provenance(prov)))
        else this.report_no_jobs(true)
    }

    // ------------------------------------------------------------------------
    // POLLING (instance mode)
    //
    // A job is deleted server-side the moment it completes -- it lives on as
    // content provenance instead -- so whatever /api/jobs/ returns is exactly
    // what is still in flight. Anything missing from a response has finished.
    // ------------------------------------------------------------------------
    _poll_jobs() {
        this.corpora.get_jobs(null, null, null, {'page-size': 50}, data => {
            this._sync_running_jobs(data.records ?? [])
            this.jobs_poll_timer = setTimeout(() => this._poll_jobs(), this.poll_interval)
        })
    }

    _sync_running_jobs(records) {
        let still_running = new Set(records.map(record => record.id))

        records.forEach(record => {
            let progress = getEl(`job-${record.id}-progress`)
            if (progress) this._set_progress(progress, record.percent_complete)
            else this.register_job(this._job_from_record(record))
        })

        forElsMatching('.job-container', card => {
            let job_id = card.id.slice('job-'.length, -'-container'.length)
            if (!still_running.has(job_id)) {
                removeEl(card)
                this.jobs_registered.delete(job_id)
            }
        })

        if (!records.length) this.report_no_jobs()
    }

    // ------------------------------------------------------------------------
    // The jobs API and content provenance describe the same thing with
    // different field names. Both are normalised here so register_job has one
    // shape to render.
    // ------------------------------------------------------------------------
    _job_from_record(record) {
        return {
            id: record.id,
            task_name: record.task_name,
            status: record.status,
            parameters: record.configuration?.parameters ?? null,
            report_path: record.report_path,
            submitted: record.submitted_time,
            completed: null,
            percent_complete: record.percent_complete,
            corpus_id: record.corpus_id ?? this.corpus?.id,
            content_type: record.content_type ?? this.content_type,
            content_id: record.content_id ?? this.content_id
        }
    }

    _job_from_provenance(prov) {
        return {
            id: prov.job_id,
            task_name: prov.task_name,
            status: prov.status,
            parameters: prov.task_configuration?.parameters ?? null,
            report_path: prov.report_path,
            submitted: prov.submitted,
            completed: prov.completed,
            percent_complete: null,
            corpus_id: this.corpus?.id,
            content_type: this.content_type,
            content_id: this.content_id
        }
    }

    _set_progress(progress, percent_complete) {
        progress.style.width = `${percent_complete}%`
        progress.setAttribute('aria-valuenow', percent_complete)
        progress.innerHTML = `${percent_complete}%`
    }

    // ------------------------------------------------------------------------
    // JOB LAUNCHER
    //
    // The scholar has jobsite/task permissions, but those jobsites and tasks
    // must also actually exist before they can be offered as jobs to enqueue.
    // ------------------------------------------------------------------------
    _setup_job_launcher() {
        // submitting a job requires a corpus to submit it against
        if (this.instance_wide) return

        this.corpora.get_jobsites(jobsites => {
            let jobsite_selector_options = ''

            jobsites.forEach(js => {
                if (!this.scholar.available_jobsites.includes(js.id)) return

                this.jobsites.push(js)
                if (js.name === 'Local') this.local_jobsite_id = js.id

                jobsite_selector_options += `
                    <option value="${js.id}" class="${js.type}" ${js.name === 'Local' ? 'selected' : ''}>
                        ${js.name}
                    </option>
                `
            })

            // the task API endpoint already filters tasks by permission
            this.corpora.get_tasks(null, tasks => {
                tasks.forEach(task => {
                    this.jobsites.forEach(jobsite => {
                        if (task.name in jobsite.task_registry) jobsite.task_registry[task.name] = task
                    })
                })

                this._build_job_modal(jobsite_selector_options)
            })
        })
    }

    _build_job_modal(jobsite_selector_options) {
        if (this.job_modal) return

        prependToEl(document.body, `
            <div class="modal fade" id="job-modal" tabindex="-1" role="dialog" aria-labelledby="job-modal-label" aria-hidden="true">
                <div class="modal-dialog" role="document">
                    <div class="modal-content">
                        <input type="hidden" id="job-content-type">
                        <input type="hidden" id="job-content-ids">
                        <input type="hidden" id="job-content-search">
                        <div class="modal-header">
                            <h5 class="modal-title" id="job-modal-label">Run a Job</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
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
                                <select id="task-selector" class="form-select" name="task"></select>
                            </div>
                            <div id="task-parameters-div"></div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary" id="job-submit-button" disabled>Run</button>
                        </div>
                    </div>
                </div>
            </div>
        `)

        onEl(getEl('jobsite-selector'), 'change', () => this.load_tasks())
        onEl(getEl('task-selector'), 'change', () => this._load_selected_task_parameters())
        onEl(getEl('job-submit-button'), 'click', () => this._submit_job())
    }

    _build_report_modal() {
        if (this.report_modal) return

        prependToEl(document.body, `
            <div class="modal fade" id="job-report-modal" tabindex="-1" role="dialog" aria-labelledby="job-report-modal-label" aria-hidden="true">
                <div class="modal-dialog modal-lg" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Job Report</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <pre id="job-report-div">Loading...</pre>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `)
    }

    _load_selected_task_parameters() {
        let task_id = getVal(getEl('task-selector'))
        let jobsite_id = getVal(getEl('jobsite-selector'))
        let jobsite = this.jobsites.find(js => js.id === jobsite_id)
        if (!jobsite) return

        let task = Object.values(jobsite.task_registry).find(t => t.id === task_id)
        if (task) this.load_task_parameters(task)
    }

    _submit_job() {
        let submission_template = {
            jobsite_id: getVal(getEl('jobsite-selector')),
            task_id: getVal(getEl('task-selector')),
            content_type: getVal(getEl('job-content-type')),
            content_id: null,
            parameters: {}
        }
        forElsMatching('.job-parameter-value', param => {
            submission_template.parameters[param.name] = getVal(param)
        })

        let done = () => hideModal(this.job_modal)
        let id_list = getVal(getEl('job-content-ids'))
        let content_search = getVal(getEl('job-content-search'))

        // one job per explicitly selected content id
        if (id_list) {
            this.corpora.submit_jobs(
                this.corpus.id,
                id_list.split(',').map(content_id => ({...submission_template, content_id})),
                done
            )

        // a search rather than a selection: hand the whole thing to Bulk Launch
        // Jobs, which fans out server-side under check_jobs' throttle instead of
        // enqueueing every job at once from here
        } else if (content_search) {
            this.corpora.submit_jobs(this.corpus.id, [{
                jobsite_id: submission_template.jobsite_id,
                task_id: this.get_local_task_id('Bulk Launch Jobs'),
                content_type: 'Corpus',
                content_id: null,
                parameters: {
                    content_type: submission_template.content_type,
                    task_id: submission_template.task_id,
                    query: content_search,
                    job_params: JSON.stringify(submission_template.parameters)
                }
            }], done)

        // no selection at all, so this is a single corpus-level job
        } else {
            this.corpora.submit_jobs(this.corpus.id, [submission_template], done)
        }
    }

    get job_modal() {
        return getEl('job-modal')
    }

    get report_modal() {
        return getEl('job-report-modal')
    }

    load_tasks(content_type=null, selectedJobsiteId=null, selectedTaskId=null) {
        let jobsite_selector = getEl('jobsite-selector')
        let task_selector = getEl('task-selector')

        if (selectedJobsiteId !== null) setVal(jobsite_selector, selectedJobsiteId)
        clearEl(task_selector)

        this.jobsites.forEach(jobsite => {
            if (jobsite.id !== getVal(jobsite_selector)) return

            for (let task_name in jobsite.task_registry) {
                let task = jobsite.task_registry[task_name]
                if (content_type && content_type !== task.content_type) continue

                // track_provenance doubles as "offer this task in the UI", so the
                // content table's dropdown is filtered the same way. A task that
                // reached us anyway is still rendered, because leaving it out would
                // silently submit whichever option happened to be first instead.
                if (!task.track_provenance && task.id !== selectedTaskId) continue
                if (this.exclude_tasks.includes(task.name)) continue

                appendToEl(task_selector, `
                    <option class="job-task" value="${task.id}"${task.id === selectedTaskId ? ' selected' : ''}>
                        ${task.name}
                    </option>
                `)
            }
        })

        let has_tasks = !!getElWithQuery('option.job-task')
        getEl('task-selector-div').classList.toggle('d-none', !has_tasks)
        setDisabled(getEl('job-submit-button'), !has_tasks)

        // always derive the parameter form from whatever ended up selected. this
        // used to be driven from inside the loop above, so a selectedTaskId that
        // matched no option left the previous job's parameters on screen.
        if (has_tasks) this._load_selected_task_parameters()
        else clearEl(getEl('task-parameters-div'))
    }

    load_task_parameters(task) {
        let task_parameters_div = getEl('task-parameters-div')
        let parameters = task['configuration']['parameters']

        clearEl(task_parameters_div)

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

                appendToEl(task_parameters_div, parameter_html)

                if (parameters[parameter]['type'] === 'pep8_text') {
                    let pep8_box = getEl(`${parameter}-pep8-text-box`)
                    // arrow, so `this` is the JobManager -- as a plain function this
                    // was the input element, and `this.corpora` threw on every blur.
                    onEl(pep8_box, 'focusout', () => {
                        setVal(pep8_box, this.corpora.pep8_variable_format(getVal(pep8_box)))
                    })
                } else if (parameters[parameter]['type'] === 'xref') {
                    // these used to read the page-global `corpora` / `corpus`
                    let selector = new ContentSelector({
                        id_element: getEl(`${parameter}-content-id`),
                        label_element: getEl(`${parameter}-content-label`),
                        previous_modal: this.job_modal,
                        corpora: this.corpora,
                        corpus: this.corpus,
                        content_type: parameters[parameter].content_type
                    })

                    onEl(getEl(`${parameter}-selection-button`), 'click', () => selector.select())
                }
            }
        }
    }

    get_local_task_id(task_name) {
        let local = this.jobsites.find(jobsite => jobsite.id === this.local_jobsite_id)
        return local?.task_registry[task_name]?.id ?? null
    }

    // ------------------------------------------------------------------------
    // JOB REPORTS
    // ------------------------------------------------------------------------
    // corpus_id is passed through from the clicked button, because in instance
    // mode the report lives under whichever corpus owns the job rather than
    // under a corpus this manager knows about.
    view_job_report(job_id, corpus_id=null) {
        // onlyOnEl, not onEl: this used to add a fresh handler on every report
        // view, and `this` was the modal element, so the poll below was never
        // actually cancelled and kept refetching forever.
        if (!this.report_modal) return

        onlyOnEl(this.report_modal, 'hidden.bs.modal', () => clearTimeout(this.job_report_timer))

        getEl('job-report-div').innerHTML = 'Loading...'
        showModal(this.report_modal)
        this.load_job_report(job_id, corpus_id)
    }

    load_job_report(job_id, corpus_id=null) {
        let owning_corpus = corpus_id ?? this.corpus?.id
        if (!owning_corpus) return

        let no_cache = Math.random().toString(36).substring(7)
        let report_div = getEl('job-report-div')

        fetch(`/corpus/${owning_corpus}/get-file/?path=job_reports/${job_id}.txt&no-cache=${no_cache}`)
            .then(res => res.text())
            .then(report => {
                report_div.innerHTML = report
                report_div.scrollTop = report_div.scrollHeight

                if (!report.includes('CORPORA JOB COMPLETE')) {
                    this.job_report_timer = setTimeout(
                        () => this.load_job_report(job_id, owning_corpus),
                        this.poll_interval
                    )
                }
            })
    }

    new_job(content_type, content_id_criteria, selectedTaskId=null) {
        if (this.instance_wide) {
            console.warn('JobManager: jobs cannot be launched without a corpus.')
            return
        }

        // these inputs live in the modal markup, which persists between openings,
        // so a previous selection would otherwise leak into this job
        setVal(getEl('job-content-ids'), '')
        setVal(getEl('job-content-search'), '')

        this.load_tasks(content_type, null, selectedTaskId)
        if (content_type) setVal(getEl('job-content-type'), content_type)
        if (content_id_criteria) {
            if (typeof content_id_criteria === 'string')
                setVal(getEl('job-content-ids'), content_id_criteria)
            else if (Array.isArray(content_id_criteria))
                setVal(getEl('job-content-ids'), content_id_criteria.join(','))
            else if (typeof content_id_criteria === 'object' && content_id_criteria !== null)
                setVal(getEl('job-content-search'), JSON.stringify(content_id_criteria))
        }
        showModal(this.job_modal)
    }

    // ------------------------------------------------------------------------
    // SSE-DRIVEN UPDATES (corpus mode)
    // ------------------------------------------------------------------------
    update_job(info) {
        // only ever driven by the per-corpus SSE channel; instance mode polls instead
        if (this.instance_wide) return

        let progress = getEl(`job-${info.job_id}-progress`)

        // a job we have not rendered yet -- fetch it and render it once
        if (!progress) {
            if (this.jobs_registered.has(info.job_id)) return

            this.jobs_registered.add(info.job_id)
            this.corpora.get_job(this.corpus.id, info.job_id, job => {
                this.register_job(this._job_from_record(job))
            })
            return
        }

        this._set_progress(progress, info.percent_complete)
        if (info.status === 'running') return

        let running_card = getEl(`job-${info.job_id}-container`)
        if (!running_card) return

        // the job has finished, so it now exists as content provenance; re-render
        // it there before dropping the running card
        this._register_as_provenance(info.job_id)
        removeEl(running_card)

        if (!getElWithQuery('.job-container')) this.report_no_jobs()
        this._announce_completion(info)
    }

    _register_as_provenance(job_id) {
        let render_matching = provenance => {
            provenance.forEach(prov => {
                if (prov.job_id === job_id) this.register_job(this._job_from_provenance(prov))
            })
        }

        if (this.content_type === 'Corpus') {
            render_matching(this.corpus.provenance)
        } else {
            this.corpora.get_content(this.corpus.id, this.content_type, this.content_id, data => {
                if (data && data.provenance) render_matching(data.provenance)
            })
        }
    }

    _announce_completion(info) {
        let loc = window.location
        let succeeded = info.status === 'complete'

        // htmlToEl returns the element itself -- the old jQuery version needed
        // an [0] here, which is why this read `alert[0]` for a while
        let alert = htmlToEl(`
            <div class="alert alert-${succeeded ? 'success' : 'danger'}"
                style="width: 95%; float: left; margin: 0px;">
              Task <b>${info.task_name}</b> has completed ${succeeded ? 'successfully' : 'with errors'}.
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
            node: alert,
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

    // ------------------------------------------------------------------------
    // RENDERING
    // ------------------------------------------------------------------------
    // `job` is the normalised shape produced by _job_from_record /
    // _job_from_provenance.
    register_job(job) {
        let finished = ['complete', 'error'].includes(job.status)
        let container = finished ? this.provenance_container : this.jobs_container
        if (!container) return

        let container_class = finished ? 'provenance-container' : 'job-container'
        let alert_class = job.status === 'error' ? 'danger' : 'success'

        // clear the "no jobs" placeholder the first time something lands here
        if (!getElWithQuery(`.${container_class}`)) clearEl(container)

        prependToEl(container, `
            <div id="job-${job.id}-container" class="alert alert-${alert_class} ${container_class}">
                ${this._progress_bar_html(job)}
                <div class="row">
                    <div class="col-sm-12 d-flex justify-content-between">
                        <span>
                            Task: <b>${job.task_name}</b><br />
                            Submitted: ${this.corpora.time_string(job.submitted)}<br />
                            ${job.completed ? `Completed: ${this.corpora.time_string(job.completed)}<br />` : ''}
                            ${this._parameter_tray_html(job)}
                        </span>
                        <span class="text-right">
                            ${this._report_button_html(job)}
                            ${this._retry_button_html(job, finished)}
                        </span>
                    </div>
                </div>
            </div>
        `)
    }

    _report_button_html(job) {
        if (!job.report_path) return ''

        return `
            <button type="button" class="btn btn-sm btn-primary me-1 mb-1 job-report-button"
                    data-job-id="${job.id}"
                    data-corpus-id="${job.corpus_id ?? ''}">View Report</button>
        `
    }

    _retry_button_html(job, finished) {
        if (!finished) return ''

        return `
            <button type="button" role="button" class="btn btn-sm btn-danger me-1 mb-1 job-retry-button"
                    data-job-id="${job.id}"
                    data-corpus-id="${job.corpus_id ?? ''}"
                    data-content-type="${job.content_type ?? ''}"
                    data-content-id="${job.content_id ?? ''}">Retry</button>
        `
    }

    _parameter_tray_html(job) {
        if (!job.parameters) return ''

        let params = Object.values(job.parameters).map(param => `<b>${param.label}</b><br /> ${param.value}`)

        return `
            <a class="btn btn-sm btn-primary mt-1"
               data-bs-toggle="collapse"
               href="#job-${job.id}-parameters"
               role="button"
               aria-expanded="false"
               aria-controls="job-${job.id}-parameters">
                Show Parameters
            </a>
            <div class="collapse mt-1" id="job-${job.id}-parameters">
                <div class="card card-body" style="display: block;">
                    ${params.join('<br /><br />')}
                </div>
            </div>
        `
    }

    _progress_bar_html(job) {
        // a finished job has no meaningful progress to show
        if (job.percent_complete === null || job.percent_complete === undefined) return ''

        return `
            <div class="row">
                <div class="col-sm-12">
                    <div id="job-${job.id}-progress"
                        class="progress-bar progress-bar-striped bg-success progress-bar-animated mb-1"
                        role="progressbar"
                        aria-valuenow="${job.percent_complete}"
                        aria-valuemin="0"
                        aria-valuemax="100"
                        style="width: ${job.percent_complete}%; height: 10px;">
                      ${job.percent_complete}%
                    </div>
                </div>
            </div>
        `
    }

    report_no_jobs(completed=false) {
        let container = completed ? this.provenance_container : this.jobs_container
        if (!container) return

        let what = completed ? 'completed jobs' : 'jobs running'
        let scope = this.instance_wide ? 'in this instance of Corpora' : `for this ${this.content_type}`

        container.innerHTML = `
            <div class="alert alert-info m-0">
                There are currently no ${what} ${scope}.
            </div>
        `
    }
}
