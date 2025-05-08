class ContentGraph {
    constructor(corpora, corpus, vis_div_id, vis_legend_id, config={}) {
        this.corpora = corpora
        this.corpus = corpus
        this.corpus_id = corpus.id
        this.corpus_uri = `/corpus/${this.corpus.id}`
        this.nodes = new vis.DataSet([])
        this.edges = new vis.DataSet([])
        this.groups = {}
        this.selected_uris = []
        this.filtering_views = {}
        this.collapsed_relationships = []
        this.hidden_cts = ['Corpus', 'File']
        this.extruded_nodes = []
        this.panes_displayed = {}
        this.seed_uris = []
        this.sprawls = []
        this.sprawl_timer = null
        this.click_timer = null
        this.click_registered = false
        this.hide_singletons = false
        this.per_type_limit = 'per_type_limit' in config ? config['per_type_limit'] : 20
        this.max_mass = 'max_node_mass' in config ? config['max_node_mass'] : 100
        this.vis_div_id = vis_div_id
        this.vis_div = $(`#${vis_div_id}`)
        this.vis_legend_id = vis_legend_id
        this.width = 'width' in config ? config['width'] : this.vis_div.width()
        this.height = 'height' in config ? config['height'] : this.vis_div.height()
        this.min_link_thickness = 'min_link_thickness' in config ? config['min_link_thickness'] : 1
        this.max_link_thickness = 'max_link_thickness' in config ? config['max_link_thickness'] : 15
        this.default_link_thickness = 'default_link_thickness' in config ? config['default_link_thickness'] : 1
        this.label_display = 'label_display' in config ? config['label_display'] : 'full'
        this.last_action = 'explore'
        this.first_start = true
        let sender = this

        // SETUP CT OPTIONS MODAL
        if (!$('#explore-ct-modal').length) {
            $('body').prepend(`
                <!-- Explore CT Modal -->
                <div class="modal fade" id="explore-ct-modal" tabindex="-1" role="dialog" aria-labelledby="explore-ct-modal-label" aria-hidden="true">
                    <div class="modal-dialog" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h4 class="modal-title" id="explore-ct-modal-label"><span class="modal-proxy-ct"></span> Options</h4>
                                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                <span aria-hidden="true">&times;</span>
                                </button>
                            </div>
                            <div class="modal-body">
                            
                                <h5>Filter by View</h5>
                                <div id="explore-ct-cv-div" class="mb-4 p-2"></div>
                                
                                <h5>Collapse Relationship</h5>
                                <div id="explore-ct-modal-collapse-div" class="p-2">
                                    <div class="row">
                                        <div class="col mb-2">
                                            Collapsing a relationship allows you to see the relationships between two different
                                            Content Types that normally are a step removed from each other. So, let's say a
                                            Content Type called "Novel" refers to a Content Type
                                            called "Chapter," and "Chapter" in turn refers to "Character." By
                                            clicking on "Chapter" in the legend (displaying this window), choosing "Novel" from the dropdown on the left,
                                            choosing "Character" from the dropdown on the right, and then clicking on the "Collapse"
                                            button, the visualization will hide all "Chapter" nodes and simply show all indirect
                                            relationships between "Novel" and "Character."
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col">
                                            <select class="form-control" id="from_ct_selector"></select>
                                        </div>
                                        <div class="col text-center">
                                            <i class="fas fa-arrow-left"></i> <span class="modal-proxy-ct"></span> <i class="fas fa-arrow-right"></i>
                                        </div>
                                        <div class="col">
                                            <select class="form-control" id="to_ct_selector"></select>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col mt-2 text-center">
                                            <select class="form-control" id="addproxy_ct_selector">
                                                <option value="None">Select Content Type to add another step to collapse...</option>
                                            </select>
                                            <button type="button" class="btn btn-primary" id="collapse-add-button">Collapse</button>
                                        </div>
                                    </div>
                                </div>
                                <div id="explore-ct-modal-already-collapsed-div" class="p-2 d-none">
                                    This Content Type is in a collapsed relationship. To uncollapse, click
                                    "uncollapse" next to Content Type in the visualization legend.
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                                <button type="button" class="btn btn-primary" id="explore-ct-sprawl-button">Sprawl Every <span class="modal-proxy-ct"></span></button>
                                <button type="button" class="btn btn-primary" id="explore-ct-hide-button">Hide Every <span class="modal-proxy-ct"></span></button>
                            </div>
                        </div>
                    </div>
                </div>
            `)

            // SETUP EXPLORE CT MODAL COLLAPSE SELECTORS AND EVENTS
            let from_ct_selector = $('#from_ct_selector')
            let to_ct_selector = $('#to_ct_selector')
            let add_ct_selector = $('#addproxy_ct_selector')
            for (let ct_name in this.corpus.content_types) {
                let option = `<option value='${ct_name}'>${ct_name}</option>`
                from_ct_selector.append(option)
                to_ct_selector.append(option)
                add_ct_selector.append(option)
            }

            add_ct_selector.change(function() {
                let ct_to_add = add_ct_selector.val()
                if (ct_to_add !== 'None') {
                    let cts_added = $('.modal-proxy-ct').html()
                    $('.modal-proxy-ct').html(cts_added + '.' + ct_to_add)
                }
            })

            $('#collapse-add-button').click(function() {
                let proxy_ct = $('.modal-proxy-ct').html()

                sender.collapsed_relationships.push({
                    from_ct: $('#from_ct_selector').val(),
                    proxy_ct: proxy_ct,
                    to_ct: $('#to_ct_selector').val()
                })

                sender.reset_graph()

                $('#explore-ct-modal').modal('hide')
            })

            $('#explore-ct-hide-button').click(function() {
                let hide_ct = $('.modal-proxy-ct').html()
                sender.hidden_cts.push(hide_ct)
                sender.reset_graph()
                $('#explore-ct-modal').modal('hide')
            })

            $('#explore-ct-sprawl-button').click(function() {
                let sprawl_ct = $('.modal-proxy-ct').html()
                sender.nodes.map(n => {
                    if (n.id.includes(`/${sprawl_ct}/`)) {
                        sender.sprawl_node(n.id)
                    }
                })
                $('#explore-ct-modal').modal('hide')
            })
        }

        // ENSURE MULTISELECT FORM EXISTS
        if (!$('#multiselect-form').length) {
            $('body').append(`
                <form id="multiselect-form" method="post" action="/not/set">
                    <input type="hidden" name="csrfmiddlewaretoken" value="${this.corpora.csrf_token}">
                    <input id="multiselect-content-ids" name="content-ids" type="hidden" value="">
                </form>
            `)
        }

        // ADD INITIAL CONTENT TO GRAPH
        if ('seeds' in config) {
            config.seeds.map(seed => {
                this.seed_uris.push(seed)
            })
        }

        // SETUP LEGEND
        this.setup_legend()

        // SETUP VIS.JS NETWORK
        this.network = new vis.Network(
            this.vis_div[0],
            {
                nodes: this.nodes,
                edges: this.edges
            },
            {
                nodes: {
                    shape: 'dot',
                    size: 10,
                    scaling: {
                        min: 10,
                        max: 200,
                        label: {
                            enabled: true,
                            min: 14,
                            max: 30,
                            maxVisible: 30,
                            drawThreshold: 5
                        }
                    },
                    font: {
                        background: "white"
                    },
                    mass: 2
                },
                edges: {
                    smooth: {
                        type: "continuous"
                    },
                    scaling: {
                        max: 30
                    }
                },
                groups: this.groups,
                interaction: {
                    zoomSpeed: 0.4,
                    hover: true,
                    tooltipDelay: this.label_display === 'full' ? 3600000 : 100
                },
                physics: {
                    solver: 'barnesHut',
                    barnesHut: {
                        springConstant: .01,
                        damping: 0.8,
                        avoidOverlap: 1,
                        springLength: 200
                    },
                    stabilization: {
                        enabled: true,
                        fit: true
                    },
                    groups: this.groups
                },
            }
        )

        // ADD WHITE BACKGROUND
        this.network.on("beforeDrawing",  function(ctx) {
            // save current translate/zoom
            ctx.save()
            // reset transform to identity
            ctx.setTransform(1, 0, 0, 1, 0, 0)
            // fill background with solid white
            ctx.fillStyle = '#ffffff'
            ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height)
            // restore old transform
            ctx.restore()
        })

        // CUSTOM PHYSICS
        this.network.physics._performStep = function(nodeId) {
            const node = this.body.nodes[nodeId]
            const force = this.physicsBody.forces[nodeId]

            if (node.options.hasOwnProperty('group')) {
                force.x += this.options.groups[node.options.group].wind.x
                force.y += this.options.groups[node.options.group].wind.y
            }

            const velocity = this.physicsBody.velocities[nodeId]

            // store the state so we can revert
            this.previousStates[nodeId] = {
                x: node.x,
                y: node.y,
                vx: velocity.x,
                vy: velocity.y,
            }

            if (node.options.fixed.x === false) {
                velocity.x = this.calculateComponentVelocity(
                    velocity.x,
                    force.x,
                    node.options.mass
                )
                node.x += velocity.x * this.timestep
            } else {
                force.x = 0
                velocity.x = 0
            }

            if (node.options.fixed.y === false) {
                velocity.y = this.calculateComponentVelocity(
                    velocity.y,
                    force.y,
                    node.options.mass
                )
                node.y += velocity.y * this.timestep
            } else {
                force.y = 0
                velocity.y = 0
            }

            const totalVelocity = Math.sqrt(
                Math.pow(velocity.x, 2) + Math.pow(velocity.y, 2)
            )
            return totalVelocity
        }

        this.network.on("click", function(params) {
            sender.remove_unpinned_panes()

            if (params.nodes.length > 0) {
                let clicked_uri = params.nodes[0]
                let pane_id = `${clicked_uri.replace(/\//g, '-')}-pane`
                let canvas_offset = sender.vis_div.offset()
                let pane_x = params.pointer.DOM.x + canvas_offset.left
                let pane_y = params.pointer.DOM.y + canvas_offset.top

                if (!$(`#${pane_id}`).length) {
                    $('body').append(`
                        <div id="${pane_id}"
                            class="content-pane"
                            style="background-color: rgba(255, 255, 255, .8);
                                width: 200px;
                                height: 225px;
                                position: absolute;
                                top: ${pane_y}px;
                                left: ${pane_x}px;
                                pointer-events: auto;"
                            data-uri="${clicked_uri}">
    
                            <div style="height: 25px;">
                                <span id="${pane_id}-select" title="Select" data-uri="${clicked_uri}" class="popup-button far fa-check-square" ${sender.selected_uris.includes(clicked_uri) ? "style='color: #EF3E36;'" : ''}></span>
                                <span id="${pane_id}-pin" title="Pin" data-uri="${clicked_uri}" class="popup-button fas fa-thumbtack"></span>
                                <span id="${pane_id}-sprawl" title="Sprawl" data-uri="${clicked_uri}" class="popup-button fas fa-expand-arrows-alt"></span>
                                <span id="${pane_id}-extrude" title="Hide" data-uri="${clicked_uri}" class="popup-button far fa-eye-slash"></span>
                                <a href="${clicked_uri}/" target="_blank"><span title="Open" class="popup-button float-right fas fa-external-link-square-alt"></span></a>
                            </div>
                            <div id="${pane_id}-meta">
                            </div>
                            <iframe id="${pane_id}-iframe" src="${clicked_uri}/?popup=y" frameBorder="0" width="200px" height="200px" />
                        </div>
                    `)

                    sender.build_meta_controls(clicked_uri, pane_id)

                    $(`#${pane_id}-select`).click(function() {
                        let uri = $(this).data('uri')
                        let node = sender.nodes.get(uri)

                        if (!sender.selected_uris.includes(uri)) {
                            sender.selected_uris.push(uri)
                            $(this).css('color', '#EF3E36')
                            node.font = {
                                background: '#EF3E36',
                                color: "white"
                            }
                        } else {
                            sender.selected_uris = sender.selected_uris.filter(val => val !== uri)
                            $(this).css('color', '#091540')
                            node.font = {
                                background: 'white',
                                color: "black"
                            }
                        }
                        sender.nodes.update(node)
                        sender.setup_legend()
                    })

                    $(`#${pane_id}-pin`).click(function() {
                        sender.pin_node($(this).data('uri'))
                    })

                    $(`#${pane_id}-sprawl`).click(function() {
                        sender.sprawl_node($(this).data('uri'), {pane_id: pane_id})
                    })

                    $(`#${pane_id}-extrude`).click(function() {
                        sender.extrude_node($(this).data('uri'), true)
                    })

                    sender.panes_displayed[clicked_uri] = {pinned: false}
                    sender.make_draggable(document.getElementById(pane_id))
                }
            }
        })

        this.network.on("dragStart", function(params){
            params.nodes.map(id => {
                let n = sender.nodes.get(id)
                n.fixed = false
                //affix_node_label(n)
                sender.nodes.update(n)
            })
        })

        this.network.on("dragEnd", function(params){
            params.nodes.map(id => {
                sender.nodes.update([{ id: id, fixed: true }])
            })
        })

        this.seed_uris.map(uri => this.sprawl_node(uri, {is_seed: true, sprawl_children: true}))
    }

    setup_legend() {
        let sender = this
        let group_colors = [
            '#EF3E36',
            '#091540',
            '#17BEBB',
            '#BFC0C0',
            '#2191FB',
            '#297045',
            '#9448BC',
            '#FFB627',
            '#CCC9E7',
            '#E9E3B4',
        ]
        let group_winds = [
            {x: 0, y: -1},
            {x: 0, y: 1},
            {x: -1, y: 0},
            {x: 1, y: 0},
            {x: -.5, y: .5},
            {x: .5, y: -.5},
            {x: -.7, y: -.7},
            {x: .7, y: .7},
            {x: -.5, y: -.5},
            {x: .5, y: .5}
        ]
        let group_color_cursor = 0

        // ensure the first content type in seeds receives the first color
        if (this.seed_uris.length) {
            let seed_group = this.seed_uris[0].split('/')[3]
            this.groups[seed_group] = {color: group_colors[group_color_cursor], wind: group_winds[group_color_cursor]}
            group_color_cursor++
        }

        let group_names = Object.keys(this.corpus.content_types).map(ct => ct)
        group_names.map(group_name => {
            if (group_name !== 'Corpus' && !Object.keys(this.groups).includes(group_name)) {
                this.groups[group_name] = {
                    color: group_colors[group_color_cursor],
                    wind: group_winds[group_color_cursor]
                }
                group_color_cursor++
                if (group_color_cursor >= group_colors.length) group_color_cursor = 0
            }
        })

        let legend = $(`#${this.vis_legend_id}`)
        legend.html('')
        for (let group_name in this.groups) {
            let action_links = ""

            this.collapsed_relationships.map(col_rel => {
                if (group_name === col_rel['proxy_ct']) {
                    action_links += `<a href="#" class="uncollapse-link mr-2" data-collapse="${col_rel.proxy_ct}">uncollapse</a>`
                }
            })

            this.hidden_cts.map(hidden => {
                if (group_name === hidden) {
                    action_links += `<a href="#" class="unhide-link mr-2" data-hidden="${hidden}">unhide</a>`
                }
            })

            legend.append(`
                <span class="badge mr-1 p-1 ct-legend-badge" style="background-color: ${this.groups[group_name].color}; color: #FFFFFF; cursor: pointer;">${group_name}</span>${action_links}
            `)
        }

        // LABEL OPTIONS
        legend.append(`
            <select id="explore-label-opt" class="mr-2">
                <option value="full" ${sender.label_display === 'full' ? 'selected' : ''}>Show full label</option>
                <option value="trunc" ${sender.label_display === 'trunc' ? 'selected' : ''}>Show truncated label</option>
                <option value="hover" ${sender.label_display === 'hover' ? 'selected' : ''}>Show label only on hover</option>
            </select>
        `)

        // SPRAWL OPTIONS
        legend.append(`
            <label for="explore-sprawl-opt" class="mr-1 mb-0">Sprawl Size:</label>
            <select id="explore-sprawl-opt" class="mr-2">
                <option value="5" ${sender.per_type_limit === 5 ? 'selected' : ''}>5</option>
                <option value="10" ${sender.per_type_limit === 10 ? 'selected' : ''}>10</option>
                <option value="20" ${sender.per_type_limit === 20 ? 'selected' : ''}>20</option>
                <option value="40" ${sender.per_type_limit === 40 ? 'selected' : ''}>40</option>
                <option value="80" ${sender.per_type_limit === 80 ? 'selected' : ''}>80</option>
            </select>
        `)

        // SINGLETON HIDING
        legend.append(`
            <button id="explore-hide-singletons" class="btn btn-sm btn-primary mr-2">Hide Singletons</button>
        `)

        // HIDE SINGLETONS CLICK
        $('#explore-hide-singletons').click(function() {
            let singletons = []
            sender.nodes.map(n => {
                if (sender.network.getConnectedNodes(n.id).length === 1) singletons.push(n.id)
            })
            singletons.map(uri => {
                let edge_ids = sender.network.getConnectedEdges(uri)
                edge_ids.map(edge_id => sender.edges.remove(edge_id))
                sender.nodes.remove(uri)
            })
        })

        // SELECTED OPTIONS
        if (this.selected_uris.length) {
            legend.append(`
                With selected: 
                <select id="explore-selected-action" class="ml-1">
                    <option value="explore" ${sender.last_action === 'explore' ? 'selected' : ''}>Explore in new tab</option>
                    <option value="hide" ${sender.last_action === 'hide' ? 'selected' : ''}>Hide</option>
                    <option value="sprawl" ${sender.last_action === 'sprawl' ? 'selected' : ''}>Sprawl</option>
                    <option value="merge" ${sender.last_action === 'merge' ? 'selected' : ''}>Merge...</option>
                </select>
                <button type="button" class="btn btn-primary btn-sm" id="explore-selected-action-button">Go</button>
            `)

            $('#explore-selected-action-button').click(function() {
                let action = $('#explore-selected-action').val()
                let ct_name = sender.selected_uris[0].split('/')[3]
                let multi_form = $('#multiselect-form')

                if (action === 'explore') {
                    multi_form.append(`
                        <input type='hidden' name='content-uris' value='${sender.selected_uris.join(',')}'/>
                    `)
                    multi_form.attr('action', `/corpus/${sender.corpus_id}/${ct_name}/explore/?popup=y`)
                    multi_form.attr('target', '_blank')
                    multi_form.submit()
                    multi_form.removeAttr('target')
                } else if (action === 'merge') {
                    let content_ids = []
                    let cts_valid = true

                    sender.selected_uris.map(uri => {
                        let uri_parts = uri.split('/')
                        if (uri_parts[3] === ct_name) {
                            content_ids.push(uri_parts[4])
                        } else {
                            cts_valid = false
                        }
                    })

                    if (cts_valid) {
                        $('#multiselect-content-ids').val(content_ids.join(','))
                        multi_form.attr('action', `/corpus/${corpus_id}/${ct_name}/merge/`)
                        multi_form.submit()
                    } else {
                        alert("In order to merge content, all selected nodes must be of the same content type!")
                    }
                } else if (action === 'hide') {
                    sender.selected_uris.map(uri => sender.extrude_node(uri, true))
                    sender.selected_uris = []
                    sender.setup_legend()
                } else if (action === 'sprawl') {
                    sender.selected_uris.map(uri => sender.sprawl_node(uri))
                }

                sender.last_action = action
            })
        }

        // LEGEND CLICK EVENTS
        $('.ct-legend-badge').click(function() {
            clearTimeout(sender.click_timer)
            let click_target = this

            // DOUBLE CLICK
            if (sender.click_registered) {
                sender.click_registered = false
                let explore_ct = $(click_target).html()
                sender.nodes.map(n => {
                    if (n.id.includes(`/${explore_ct}/`)) {
                        sender.sprawl_node(n.id)
                    }
                })
            // SINGLE CLICK
            } else {
                sender.click_registered = true
                sender.click_timer = setTimeout(function() {
                    sender.click_registered = false

                    let explore_ct = $(click_target).html()
                    $('#explore-ct-modal-label').html(`${explore_ct} Options`)
                    $('.modal-proxy-ct').html(explore_ct)

                    let collapsible = true
                    let hideable = !sender.hidden_cts.includes(explore_ct)

                    let cv_div = $('#explore-ct-cv-div')
                    cv_div.html('')
                    if (Object.keys(sender.corpus.content_types[explore_ct]).includes('views')) {
                        cv_div.append(`<select id="cv-selector" class="form-control" data-ct="${explore_ct}"><option value="--">None</option></select>`)
                        let cv_selector = $('#cv-selector')
                        sender.corpus.content_types[explore_ct].views.map(cv => {
                            let selected_indicator = ''
                            if (sender.filtering_views.hasOwnProperty(explore_ct) && sender.filtering_views[explore_ct] === cv.neo_super_node_uri) {
                                selected_indicator = ' selected'
                            }
                            cv_selector.append(`<option value="${cv.neo_super_node_uri}"${selected_indicator}>${cv.name}</option>`)
                        })

                        cv_selector.change(function() {
                            let ct = cv_selector.data('ct')
                            let cv_supernode = cv_selector.val()
                            if (cv_supernode === '--' && Object.keys(sender.filtering_views).includes(ct)) {
                                delete sender.filtering_views[ct]
                            } else {
                                sender.filtering_views[ct] = cv_supernode
                            }

                            sender.reset_graph()
                            $('#explore-ct-modal').modal('hide')
                        })
                    } else {
                        cv_div.append(`
                            <div class="alert alert-info">
                                No Content Views exist for this content type. Click <a id="create-cv-button" role="button">here</a> to create one. 
                            </div>
                        `)
                    }

                    sender.collapsed_relationships.map(col_rel => {
                        if (col_rel.proxy_ct === explore_ct) {
                            collapsible = false
                        }
                    })

                    if (collapsible) {
                        $('#explore-ct-modal-already-collapsed-div').addClass('d-none')
                        $('#explore-ct-modal-collapse-div').removeClass('d-none')
                    } else {
                        $('#explore-ct-modal-already-collapsed-div').removeClass('d-none')
                        $('#explore-ct-modal-collapse-div').addClass('d-none')
                    }

                    if (hideable) {
                        $('#explore-ct-hide-button').attr('disabled', false)
                    } else {
                        $('#explore-ct-hide-button').attr('disabled', true)
                    }

                    $('#explore-ct-modal').modal()

                }, 700)
            }
        })

        $('.uncollapse-link').click(function(e) {
            e.preventDefault()
            let col_proxy = $(this).data('collapse')
            for (let cl_index = 0; cl_index < sender.collapsed_relationships.length; cl_index++) {
                if (sender.collapsed_relationships[cl_index].proxy_ct === col_proxy) {
                    sender.collapsed_relationships.splice(cl_index, 1)
                    break
                }
            }
            sender.reset_graph()
        })

        $('.unhide-link').click(function(e) {
            e.preventDefault()
            let hid_index = sender.hidden_cts.indexOf($(this).data('hidden'))
            sender.hidden_cts.splice(hid_index, 1)
            sender.reset_graph()
        })

        $('#explore-label-opt').change(function() {
            let option = $('#explore-label-opt').val()
            sender.label_display = option
            if (option === 'full') {
                sender.network.setOptions({interaction:{tooltipDelay:3600000}})
            } else {
                sender.network.setOptions({interaction:{tooltipDelay:100}})
            }

            sender.nodes.map(n => {
                sender.format_label(n)
                sender.nodes.update(n)
            })
        })

        $('#explore-sprawl-opt').change(function() {
            sender.per_type_limit = parseInt($(this).val())
        })
    }

    format_label(n) {
        if (this.label_display === 'full') {
            n.label = n.label_data
            n.title = null
        } else if (this.label_display === 'trunc') {
            n.label = n.label_data.slice(0, 20)
            n.title = n.label_data
        } else {
            n.label = ''
            n.title = n.label_data
        }
    }

    sprawl_node(uri, options={}) {
        let opts = Object.assign(
            {
                is_seed: false,
                sprawl_children: false,
                pane_id: null,
                meta_only: false,
                sprawl_ct: null,
                skip: -1,
                resprawls: 0,
            },
            options
        )

        let sender = this
        let node_ct = uri.split('/').slice(-2)[0]
        let node_id = uri.split('/').slice(-1)[0]
        let sprawl_node = this.nodes.get(uri)
        let skip = 0

        if (opts.skip > 0) skip = opts.skip
        else if (sprawl_node && sprawl_node.hasOwnProperty('skip')) {
            skip = sprawl_node.skip
        }

        let net_json_params = {
            per_type_skip: skip,
            per_type_limit: this.per_type_limit
        }

        let filter_param = Object.keys(this.filtering_views).map(ct => `${ct}:${sender.filtering_views[ct]}`).join(',')
        if (filter_param) { net_json_params['filters'] = filter_param; }

        let collapse_param = this.collapsed_relationships.map(rel => `${rel.from_ct}-${rel.proxy_ct}-${rel.to_ct}`).join(',')
        if (collapse_param) { net_json_params['collapses'] = collapse_param; }

        let hidden_param = this.hidden_cts.join(',')
        if (hidden_param) { net_json_params['hidden'] = hidden_param; }

        if (opts.is_seed) net_json_params['is-seed'] = 'y'
        if (opts.meta_only) net_json_params['meta-only'] = 'y'
        if (opts.sprawl_ct) net_json_params['target-ct'] = opts.sprawl_ct

        this.sprawls.push(false)
        clearTimeout(this.sprawl_timer)
        this.sprawl_timer = setTimeout(this.await_sprawls.bind(this), 2000)
        let sprawl_index = this.sprawls.length - 1

        this.corpora.get_network_json(this.corpus_id, node_ct, node_id, net_json_params, function(net_json) {
            let children = []
            let origin_plotted = false
            let nodes_added = 0

            net_json.nodes.map(n => {
                if (n.id !== sender.corpus_uri && !sender.nodes.get(n.id) && !sender.extruded_nodes.includes(n.id)) {
                    n.label_data = sender.corpora.unescape(n.label)
                    sender.format_label(n)
                    if (n.id === uri) {
                        n.meta = net_json.meta
                        origin_plotted = true
                    }
                    sender.nodes.add(n)
                    nodes_added += 1
                    if (opts.sprawl_children) {
                        children.push(n.id)
                    }
                }
            })

            net_json.edges.map(e => {
                e.id = `${e.from}-${e.to}`
                if (!sender.extruded_nodes.includes(e.from) && !sender.extruded_nodes.includes(e.to) && !sender.edges.get(e.id)) {
                    sender.edges.add(e)
                }
            })

            if (!origin_plotted) {
                sender.nodes.update([{'id': uri, 'meta': net_json.meta}])
            }

            if (opts.sprawl_children) {
                children.map(child_uri => sender.sprawl_node(child_uri))
            }

            if (!opts.meta_only && !opts.sprawl_ct && sprawl_node && sprawl_node.hasOwnProperty('meta') && nodes_added === 0) {
                let plotted = sender.network.getConnectedEdges(uri).length
                let total_count = 0
                for (let path in sprawl_node.meta) {
                    if (!sprawl_node.meta[path].collapsed) {
                        total_count += sprawl_node.meta[path].count
                    }
                }
                if (plotted < total_count && opts.resprawls < 10) {
                    opts.resprawls += 1
                    sender.sprawl_node(uri, opts)
                }
            }
            if (opts.pane_id) {
                sender.build_meta_controls(uri, opts.pane_id)
            }
        })

        if (sprawl_node && !opts.meta_only && !opts.sprawl_ct) {
            sprawl_node.skip = skip += this.per_type_limit
            sender.nodes.update(sprawl_node)
        }

        sender.sprawls[sprawl_index] = true
    }

    await_sprawls() {
        clearTimeout(this.sprawl_timer)
        if (this.sprawls.includes(false)) {
            this.sprawl_timer = setTimeout(this.await_sprawls.bind(this), 2000)
        } else {
            this.sprawls = []
            this.normalize_collapse_thickness()
            this.setup_legend()

            if (this.first_start) {
                // PIN ALL SEED NODES
                this.seed_uris.map(seed_uri => {
                    this.nodes.update([{id: seed_uri, fixed: true}])
                })

                // FIT NETWORK
                this.network.fit()

                this.first_start = false
            }
        }
    }

    build_meta_controls(uri, pane_id) {
        let sender = this
        let node = this.nodes.get(uri)
        let meta_div = $(`#${pane_id}-meta`)
        meta_div.html('')
        if (!node.hasOwnProperty('meta')) {
            this.sprawl_node(uri, {pane_id: pane_id, meta_only: true})
        } else {
            let node_edge_ids = this.network.getConnectedEdges(uri)
            let ct_counts = {}

            node_edge_ids.map(e_id => {
                let e_parts = e_id.split('-')
                let other = e_parts[1]
                if (other.includes(node.group)) other = e_parts[0]
                let other_ct = other.split('/').slice(-2)[0]
                if (other_ct in ct_counts) ct_counts[other_ct] += 1
                else ct_counts[other_ct] = 1
            })

            for (let path in node.meta) {
                let path_parts = path.split('-')
                let sprawl_ct = path_parts[path_parts.length - 1]
                if (this.groups.hasOwnProperty(sprawl_ct)) {
                    let plotted = ct_counts.hasOwnProperty(sprawl_ct) ? ct_counts[sprawl_ct] : 0
                    meta_div.append(`
                        <span
                            class="badge mr-1 p-1 meta-badge"
                            style="background-color: ${this.groups[sprawl_ct].color}; color: #FFFFFF; cursor: pointer;"
                            data-uri="${uri}" data-sprawl_ct="${sprawl_ct}" data-skip="${plotted}"
                        >
                            ${sprawl_ct} (${plotted} / ${node.meta[path].collapsed ? 'collapsed' : node.meta[path].count})
                        </span>
                    `)
                }
            }

            $('.meta-badge').off('click').on('click', function() {
                sender.sprawl_node($(this).data('uri'), {
                    pane_id: pane_id,
                    sprawl_ct: $(this).data('sprawl_ct'),
                    skip: parseInt($(this).data('skip'))
                })
            })
        }
    }

    reset_graph() {
        this.edges.clear()
        this.nodes.clear()
        this.first_start = true

        this.seed_uris.map(uri => {
            this.sprawl_node(uri, {is_seed: true, sprawl_children: true})
        })
    }

    extrude_node(uri, remove_isolated=false) {
        let sender = this
        this.extruded_nodes.push(uri)
        let edge_ids = this.network.getConnectedEdges(uri)
        edge_ids.map(edge_id => this.edges.remove(edge_id))
        this.nodes.remove(uri)

        if (remove_isolated) {
            let isolated_nodes = new vis.DataView(this.nodes, {
                filter: function (node) {
                    let connEdges = sender.edges.get({
                        filter: function (edge) {
                            return (
                                (edge.to == node.id) || (edge.from == node.id))
                        }
                    })
                    return connEdges.length == 0
                }
            })

            isolated_nodes.map(i => this.extrude_node(i.id, false))
        }
    }

    pin_node(uri) {
        if (!this.panes_displayed[uri].pinned) {
            this.panes_displayed[uri].pinned = true
            let pin_id = `${uri.replace(/\//g, '-')}-pane-pin`
            $(`#${pin_id}`).css('color', '#EF3E36')
        } else {
            this.panes_displayed[uri].pinned = false
            this.remove_unpinned_panes()
        }
    }

    normalize_collapse_thickness() {
        this.collapsed_relationships.map(col_rel => {
            let title_a = `has${col_rel.to_ct}via${col_rel.proxy_ct}`
            let title_b = `has${col_rel.from_ct}via${col_rel.proxy_ct}`

            let redundant_edges = this.edges.get({
                filter: function(edge) {
                    return edge.title === title_b
                }
            })

            redundant_edges.map(r => {
                let id_parts = r.id.split('-')
                let inverse_id = `${id_parts[1]}-${id_parts[0]}`
                let inverse_edge = this.edges.get(inverse_id)
                if (inverse_edge === null) {
                    this.edges.add({
                        id: inverse_id,
                        from: id_parts[1],
                        to: id_parts[0],
                        title: title_a,
                        freq: r.freq
                    })
                }
                this.edges.remove(r.id)
            })

            let col_edges = this.edges.get({
                filter: function(edge) {
                    return edge.title === title_a
                }
            })

            let min_freq = 9999999999999999999999
            let max_freq = 1
            col_edges.map(e => {
                if (e.freq < min_freq) { min_freq = e.freq; }
                if (e.freq > max_freq) { max_freq = e.freq; }
            })

            let updated_edges = []
            col_edges.map(e => {
                let mx = (e.freq - min_freq) / (max_freq - min_freq)
                let preshiftNorm = mx * (this.max_link_thickness - this.min_link_thickness)
                updated_edges.push({
                    id: e.id,
                    value: parseInt(preshiftNorm + this.min_link_thickness)
                })
            })
            this.edges.update(updated_edges)
        })

        let update_nodes = []
        let aggregated_edge_cts = []
        this.collapsed_relationships.map(rel => {
            aggregated_edge_cts.push(rel.from_ct)
            aggregated_edge_cts.push(rel.to_ct)
        })

        this.nodes.map(node => {
            let update_node = {id: node.id, value: 0, mass: 0}

            if (aggregated_edge_cts.includes(node.group)) {
                let conn_edge_ids = this.network.getConnectedEdges(node.id)
                update_node.value = 0
                conn_edge_ids.map(conn_edge_id => {
                    let conn_edge = this.edges.get(conn_edge_id)
                    if (conn_edge.hasOwnProperty('freq')) {
                        update_node.value += conn_edge.freq
                    } else {
                        update_node.value += 1
                    }
                })
            } else {
                update_node.value = this.network.getConnectedEdges(node.id).length
            }
            update_node.mass = update_node.value > this.max_mass ? this.max_mass : update_node.value

            if ((!node.hasOwnProperty('value') || !node.hasOwnProperty('mass')) || (node.value !== update_node.value || node.mass !== update_node.mass)) {
                update_nodes.push(update_node)
            }
        })

        if (update_nodes.length) this.nodes.update(update_nodes)
    }

    remove_unpinned_panes() {
        for (let pane_uri in this.panes_displayed) {
            if (!this.panes_displayed[pane_uri].pinned) {
                let pane_id = `${pane_uri.replace(/\//g, '-')}-pane`
                $(`#${pane_id}`).remove()
                delete this.panes_displayed[pane_uri]
            }
        }
    }

    make_draggable(elmnt) {
        var pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0
        if (document.getElementById(elmnt.id + "header")) {
            // if present, the header is where you move the DIV from:
            document.getElementById(elmnt.id + "header").onmousedown = dragMouseDown
        } else {
            // otherwise, move the DIV from anywhere inside the DIV:
            elmnt.onmousedown = dragMouseDown
        }

        function dragMouseDown(e) {
            e = e || window.event
            e.preventDefault()
            // get the mouse cursor position at startup:
            pos3 = e.clientX
            pos4 = e.clientY
            document.onmouseup = closeDragElement
            // call a function whenever the cursor moves:
            document.onmousemove = elementDrag
        }

        function elementDrag(e) {
            e = e || window.event
            e.preventDefault()
            // calculate the new cursor position:
            pos1 = pos3 - e.clientX
            pos2 = pos4 - e.clientY
            pos3 = e.clientX
            pos4 = e.clientY
            // set the element's new position:
            elmnt.style.top = (elmnt.offsetTop - pos2) + "px"
            elmnt.style.left = (elmnt.offsetLeft - pos1) + "px"
        }

        function closeDragElement() {
            // stop moving when mouse button is released:
            document.onmouseup = null
            document.onmousemove = null
        }
    }
}

