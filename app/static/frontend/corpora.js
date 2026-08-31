// for getting/manipulating DOM
function getEl(id) { return document.getElementById(id) }
function getElWithQuery(query) { return document.querySelector(query) }
function getElsWithQuery(query) { return document.querySelectorAll(query) }
function forElsMatching(query, callback) { [].forEach.call(document.querySelectorAll(query), callback) }
function clearEl(el) { while (el.firstChild) el.removeChild(el.firstChild) }
function appendToEl(el, html) {
    el.append(htmlToEl(html))
}
function prependToEl(el, html) {
    el.prepend(htmlToEl(html))
}
function htmlToEl(html) {
    let docFrag = document.createDocumentFragment()
    let range = document.createRange()
    range.setStart(docFrag, 0)
    docFrag.appendChild(range.createContextualFragment(html))
    return docFrag
}
const hideEl = (el) => el.classList.add('hidden')
const showEl = (el) => el.classList.remove('hidden')
function getCssVar(variableName) {
    return getComputedStyle(document.documentElement).getPropertyValue(`--${variableName}`)
}
function setCssVar(variableName, value) {
    document.documentElement.style.setProperty(variableName, value)
}

// basic utility functions
function callAPI(url, params={}, callback) {
    let fetchURL = url
    let getParams = buildGetParams(params)
    if (getParams) fetchURL += `?${getParams}`
    fetch(fetchURL)
        .then(res => res.json())
        .then(data => callback(data))
}
function buildGetParams(params) {
    let getParams = ''
    if (Object.keys(params).length) {
        let paramStrings = []
        for (let param in params) {
            paramStrings.push(`${param}=${params[param]}`)
        }
        getParams += paramStrings.join('&')
    }
    return getParams
}
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
function romanize (num) {
    if (isNaN(num))
        return num;
    let digits = String(+num).split(""),
        key = ["","C","CC","CCC","CD","D","DC","DCC","DCCC","CM",
            "","X","XX","XXX","XL","L","LX","LXX","LXXX","XC",
            "","I","II","III","IV","V","VI","VII","VIII","IX"],
        roman = "",
        i = 3;
    while (i--)
        roman = (key[+digits.pop() + (i * 10)] || "") + roman;
    return Array(+digits.join("") + 1).join("M") + roman;
}
function escapeAttrVal(val) {
    return val.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
function hasProp(obj, path) {
    return path.split(".").every(function(x) {
        if(typeof obj != "object" || obj === null || ! x in obj)
            return false
        obj = obj[x]
        return true
    })
}
function distillHTML(htmlString) {
    let stylisticTags = ['em', 'p', ]
    let tagTransforms = {
        'i': 'em'
    }

    // strip out all tag attributes. we want just simple tags
    htmlString = htmlString.replace(/<(\/?)([\w-]+)[^>]*>/g, function(match, slash, tagName) {
        return '<' + slash + tagName + '>'
    })

    Object.keys(tagTransforms).forEach(tag => {
        htmlString = htmlString.replaceAll(`<${tag}>`, `<${tagTransforms[tag]}>`)
        htmlString = htmlString.replaceAll(`</${tag}>`, `</${tagTransforms[tag]}>`)
    })

    let tagsAndText = getTagsAndText(htmlString)

    tagsAndText.opened_tags.forEach(tag => {
        if (!stylisticTags.includes(tag)) htmlString = htmlString.replaceAll(`<${tag}>`, '')
    })
    tagsAndText.closed_tags.forEach(tag => {
        if (!stylisticTags.includes(tag)) htmlString = htmlString.replaceAll(`</${tag}>`, '')
    })

    return htmlString
}
function getTagsAndText(input) {
    // Return empty result for empty or non-string input
    if (!input || typeof input !== 'string') {
        return { opened_tags: [], closed_tags: [], text: '' }
    }

    // Find all opening HTML tags in the string
    const openTagRegex = /<\s*([a-zA-Z][a-zA-Z0-9]*)[^>]*>/g
    const openTagMatches = [...input.matchAll(openTagRegex)]
    const openedTags = openTagMatches.map(match => match[1])

    // Find all closing HTML tags in the string
    const closeTagRegex = /<\s*\/\s*([a-zA-Z][a-zA-Z0-9]*)[^>]*>/g
    const closeTagMatches = [...input.matchAll(closeTagRegex)]
    const closedTags = closeTagMatches.map(match => match[1])

    // Extract text content by removing HTML tags
    const text = input.replace(/<\/?[^>]+(>|$)/g, '')

    return {
        opened_tags: openedTags, // Remove duplicates
        closed_tags: closedTags, // Remove duplicates
        text: text
    }
}
function delayedScroll(anchor, smooth=true, parent=null) {
    let scrollOpts = {behavior: 'smooth'}
    if (!smooth) scrollOpts = null

    let idSelectedEl = getElWithQuery(`${parent ? '#' + parent + ' ' : ''}#${anchor}`)
    if (idSelectedEl) idSelectedEl.scrollIntoView(scrollOpts)
    else {
        let anchorSelectedEl = getElWithQuery(`${parent ? '#' + parent + ' ' : ''}a[name=${anchor}]`)
        if (anchorSelectedEl) anchorSelectedEl.scrollIntoView(scrollOpts)
    }
}
function parseDate(timestamp) {
    return new Date(timestamp).toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric'
    })
}
function forEachKey(obj, callback) {
    Object.keys(obj).forEach(key => callback(key))
}


class Corpus {
    constructor(host, id, schema={}, indirectConnections=[]) {
        this.host = host
        this.id = id
        this.api = `${host}/api/corpus/${id}`
        this.content = {}

        /* example schema
        {
            Book: {
                preload: true,                  // <- whether to pull down all content of this type on load
                xRefs: [                        // <- any cross-references to track internally
                    {field: 'authors', reference: 'Person', multi: true},
                    {field: 'genre', reference: 'Genre', multi: true}
                ],
                sortFields: ['+title'],             // <- field to sort by when pulling down content
                criteria: {f_project_id: 42},   // <- any filtering criteria to use when pulling down content
            },
            Person: {
                preload: true,
                sortFields: ['+last_name', '+first_name']
            },
            Genre: {
                preload: true,
                sortFields: ['+name']
            }
        }
        */
        this.schema = Object.assign({}, schema)
        forEachKey(this.schema,contentType => {
            if (!this.schema[contentType].hasOwnProperty('preload')) this.schema[contentType].preload = false
            if (!this.schema[contentType].hasOwnProperty('xRefs')) this.schema[contentType].xRefs = []
            if (!this.schema[contentType].hasOwnProperty('sortFields')) this.schema[contentType].sortFields = []
            this.schema[contentType].ids = new Set()
        })

        /* example indirect connections
        [
            ['Person', 'Book', 'Genre']         // <- this would instruct corpus logic to register indirect connections
                                                //    between people and genres so you could query all genres related
                                                //    to a specific author
        ]
        */
        this.indirectConnections = indirectConnections
    }

    async load(callback, useCache=true) {
        // grab data and populate content
        let apiRequests = []
        for (let contentType in this.schema) {
            if (this.schema[contentType].preload) {
                let criteria = Object.assign({}, this.schema[contentType].criteria, {
                    'page-size': 10000,
                })

                this.schema[contentType].sortFields.forEach(sortField => {
                    let direction = 'asc'
                    if (sortField.startsWith('-')) direction = 'desc'
                    sortField = sortField.replace('+', '').replace('-', '')
                    criteria[`s_${sortField}`] = direction
                })

                apiRequests.push({
                    contentType,
                    url: `${this.api}/${contentType}/?${buildGetParams(criteria)}`
                })
            }
        }

        const db = await this.#openDB()

        let results = await Promise.all(apiRequests.map(async ({ contentType, url }) => {
            // Kick off the cache read and last-updated check in parallel
            const cachedRecordPromise = db ? this.#dbGet(db, contentType) : Promise.resolve(null)
            const lastUpdatedPromise = fetch(`${this.api}/${contentType}/last-updated/`).then(r => r.json())
            const [cachedRecord, lastUpdatedResponse] = await Promise.all([cachedRecordPromise, lastUpdatedPromise])

            // Serve from cache if it exists and is still fresh
            const cacheIsValid = cachedRecord && cachedRecord.last_updated >= lastUpdatedResponse.last_updated
            if (db && useCache && cacheIsValid) return cachedRecord.data

            // Cache is stale or bypassed -- fetch fresh data from the API
            const response = await fetch(url)
            const data = await response.json()

            // Store fresh data in the cache for next time (non-blocking)
            if (db) this.#dbPut(db, contentType, { last_updated: lastUpdatedResponse.last_updated, data }).catch(err => console.warn(`Failed to cache ${contentType}:`, err))

            return data
        }))
        results.forEach(result => {
            if (result.meta && result.records) {
                let contentType = result.meta.content_type
                if (!(contentType in this.content)) this.content[contentType] = {}

                result.records.forEach(record => {
                    this.schema[contentType].ids.add(record.id)
                    this.content[contentType][record.id] = record
                    this.content[contentType][record.id]['contentType'] = contentType
                    this.content[contentType][record.id]['_conns'] = {}
                })
            }
        })

        // wire up any xrefs
        forEachKey(this.schema, contentType => {
            if (this.schema[contentType].preload) {
                let contents = this.getContents(contentType)
                contents.forEach(content => {
                    this.registerConnections(content)
                })
            }
        })

        // wire up indirect connections
        this.registerIndirectConnections()

        callback(this)
    }

    getContent(contentType, id) {
        // for content that gets fully loaded because it's a facet
        if (contentType in this.content) {
            if (id in this.content[contentType]) return this.content[contentType][id]
        }

        // for content that isn't preloaded but should be interlinked anyway
        if (contentType in this.schema) {
            if (!this.schema[contentType].preload) {
                if (!(contentType in this.content)) this.content[contentType] = {}
                this.content[contentType][id] = {
                    id: id,
                    contentType: contentType,
                    label: contentType,
                    _conns: {}
                }
            }

            return this.content[contentType][id]
        }

        return null
    }

    getContents(contentType) {
        let results = []
        if (contentType in this.schema) {
            this.schema[contentType].ids.forEach(id => {
                results.push(this.getContent(contentType, id))
            })
        }
        return results
    }

    getAssociatedContents(contentType, id, associatedContentType=null) {
        let associatedContents = []
        let content = this.getContent(contentType, id)
        if (content) {
            forEachKey(content._conns, connectedContentType => {
                if (connectedContentType === associatedContentType || associatedContentType === null) {
                    content._conns[connectedContentType].forEach(connectedContentID => {
                        associatedContents.push(this.getContent(connectedContentType, connectedContentID))
                    })
                }
            })
        }
        return associatedContents
    }

    makeConnection(contentType_a, id_a, contentType_b, id_b) {
        let contentA = this.getContent(contentType_a, id_a)
        let contentB = this.getContent(contentType_b, id_b)

        if (contentA && contentB) {
            if (!(contentB.contentType in contentA._conns)) contentA._conns[contentB.contentType] = new Set()
            if (!(contentA.contentType in contentB._conns)) contentB._conns[contentA.contentType] = new Set()

            contentA._conns[contentB.contentType].add(contentB.id)
            contentB._conns[contentA.contentType].add(contentA.id)
        }
    }

    registerConnections(content) {
        if (content.contentType in this.schema) {
            this.schema[content.contentType].xRefs.forEach(xRef => {
                if (xRef.field in content) {
                    if (xRef.multi) {
                        content[xRef.field].forEach(val => {
                            if (val.id) {
                                this.makeConnection(
                                    content.contentType,
                                    content.id,
                                    xRef.reference,
                                    val.id
                                )
                            }
                        })
                    } else if (content[xRef.field].id) {
                        this.makeConnection(
                            content.contentType,
                            content.id,
                            xRef.reference,
                            content[xRef.field].id
                        )
                    }
                }
            })
        }
    }

    registerIndirectConnections() {
        this.indirectConnections.forEach(triple => {
            let rootCT = triple[0]
            let mediatingCT = triple[1]
            let leafCT = triple[2]

            let rootContents = this.getContents(rootCT)
            rootContents.forEach(rootContent => {
                let mediatingContents = this.getAssociatedContents(rootCT, rootContent.id, mediatingCT)
                mediatingContents.forEach(mediatingContent => {
                    let leafContents = this.getAssociatedContents(mediatingCT, mediatingContent.id, leafCT)
                    leafContents.forEach(leafContent => {
                        this.makeConnection(rootCT, rootContent.id, leafCT, leafContent.id)
                    })
                })
            })
        })
    }

    getTotalConnections(contentTypeA, contentIDA, contentTypeB) {
        let total = 0
        let content = this.getContent(contentTypeA, contentIDA)
        if (content) {
            if (contentTypeB in content._conns) {
                total = content._conns[contentTypeB].size
            }
        }
        return total
    }

    #openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.host, 1)
            request.onupgradeneeded = e => {
                e.target.result.createObjectStore('responses', { keyPath: 'facet' })
            }
            request.onsuccess = e => resolve(e.target.result)
            request.onerror = e => reject(e.target.error)
        }).catch(() => null)
    }

    #dbGet(db, facet) {
        return new Promise((resolve, reject) => {
            const request = db.transaction('responses', 'readonly')
                .objectStore('responses')
                .get(facet)
            request.onsuccess = e => resolve(e.target.result ?? null)
            request.onerror = e => reject(e.target.error)
        })
    }

    #dbPut(db, facet, payload) {
        return new Promise((resolve, reject) => {
            const request = db.transaction('responses', 'readwrite')
                .objectStore('responses')
                .put({ facet, ...payload })
            request.onsuccess = () => resolve()
            request.onerror = e => reject(e.target.error)
        })
    }
}

function getCorpus(host, id, schema={}, indirectConnections=[], callback) {
    let corpus = new Corpus(host, id, schema, indirectConnections)
    corpus.load(callback)
}