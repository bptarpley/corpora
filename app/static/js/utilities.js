// for getting/manipulating DOM
function getEl(id) { return document.getElementById(id) }
function getElWithQuery(query) { return document.querySelector(query) }
function getElsWithQuery(query) { return document.querySelectorAll(query) }
function forElsMatching(query, callback) { [].forEach.call(document.querySelectorAll(query), callback) }
function clearEl(el) { while (el.firstChild) el.removeChild(el.firstChild) }
// inserting HTML. these use insertAdjacentHTML rather than parsing into a detached
// fragment, because the parser needs the TARGET element as context: a detached
// fragment has no table context, so parsing '<tr><td>x</td></tr>' there silently
// discards the tags and leaves the bare text "x" behind.
function appendToEl(el, html) {
    el.insertAdjacentHTML('beforeend', html)
}
function prependToEl(el, html) {
    el.insertAdjacentHTML('afterbegin', html)
}
// for the cases that need a detached node rather than an insertion (e.g. handing a
// node to Toastify). <template> is used because its contents parse in a mode that
// preserves table rows, unlike a plain document fragment.
function htmlToFragment(html) {
    let template = document.createElement('template')
    template.innerHTML = html.trim()
    return template.content
}
function htmlToEl(html) {
    return htmlToFragment(html).firstElementChild
}
// null-tolerant, for the same reason removeEl and onEl are (see below). d-none is
// Bootstrap's own display utility and what this project's markup already uses --
// these used to toggle a 'hidden' class that no stylesheet here defines, so they
// silently did nothing.
const hideEl = (el) => { if (el) el.classList.add('d-none') }
const showEl = (el) => { if (el) el.classList.remove('d-none') }
const setElVisible = (el, visible) => { if (el) el.classList.toggle('d-none', !visible) }
function setElsVisible(query, visible) {
    forElsMatching(query, el => el.classList.toggle('d-none', !visible))
}
function getCssVar(variableName) {
    return getComputedStyle(document.documentElement).getPropertyValue(`--${variableName}`)
}
function setCssVar(variableName, value) {
    document.documentElement.style.setProperty(variableName, value)
}

// removing elements. these are null-tolerant on purpose: jQuery's $('.missing').remove()
// is a no-op, whereas getEl('missing').remove() throws. keeping that tolerance avoids
// having to guard every call site while migrating off jQuery.
function removeEl(el) { if (el) el.remove() }
function removeElsMatching(query) { forElsMatching(query, el => el.remove()) }

// enabling/disabling form controls. ALWAYS use this rather than setAttribute():
// jQuery's .attr('disabled', false) REMOVES the attribute, but
// setAttribute('disabled', false) sets it to the string "false", which is truthy --
// so the control silently stays disabled. assigning the property avoids that trap.
function setDisabled(el, disabled=true) { el.disabled = !!disabled }
function setChecked(el, checked=true) { el.checked = !!checked }

// reading/writing form control values. prefer these over el.value directly, since
// a multi-select's value is an array (matching jQuery's .val()) rather than the
// single string el.value reports, and a checkbox's value is its checked state.
function getVal(el) {
    if (el.tagName === 'SELECT' && el.multiple) return Array.from(el.selectedOptions).map(opt => opt.value)
    if (el.type === 'checkbox') return el.checked
    return el.value
}
function setVal(el, value) {
    if (el.tagName === 'SELECT' && el.multiple) {
        let values = (Array.isArray(value) ? value : [value]).map(String)
        Array.from(el.options).forEach(opt => opt.selected = values.includes(opt.value))
    }
    else if (el.type === 'checkbox') el.checked = !!value
    else el.value = value
}

// binding events. onEl is null-tolerant for the same reason removeEl is. onDelegate
// binds a single listener to a container and matches events bubbling up from
// descendants, which is how to handle dynamically generated content without
// rebinding (the vanilla equivalent of jQuery's $(parent).on(evt, selector, fn)).
function onEl(el, event, callback) { if (el) el.addEventListener(event, callback) }
function onElsMatching(query, event, callback) {
    forElsMatching(query, el => el.addEventListener(event, callback))
}
function onDelegate(el, event, selector, callback) {
    el.addEventListener(event, evt => {
        let match = evt.target.closest(selector)
        if (match && el.contains(match)) callback(evt, match)
    })
}

// replaces any handler previously set this way, which is the vanilla equivalent of
// jQuery's .off(evt).on(evt, fn) idiom. use it where a handler is (re)bound on every
// render and must not accumulate; onEl is still correct for one-time bindings.
function onlyOnEl(el, event, callback) {
    if (el) el[`on${event}`] = callback
}

// slides an element open the way jQuery's slideDown('slow') did, for elements that
// use Bootstrap's display utilities. This needs JS rather than a CSS transition for
// two reasons: `display` is not animatable at all, and CSS cannot transition to a
// height of `auto` -- so the natural height and vertical margins are measured while
// the element is laid out, then animated to explicitly.
//
// Collapsing is deliberately instant, matching the jQuery original (which paired
// slideDown with a plain .hide()). Repeat calls in the same direction are ignored,
// so a drawer already open does not re-animate.
function toggleDrawer(el, visible, displayClass='d-flex', duration=600) {
    if (!el) return
    if (!el.classList.contains('d-none') === visible) return

    el.getAnimations?.().forEach(anim => anim.cancel())
    el.style.overflow = ''

    if (!visible) {
        el.classList.remove(displayClass)
        el.classList.add('d-none')
        return
    }

    el.classList.remove('d-none')
    el.classList.add(displayClass)

    let still = !el.animate || window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (still) return

    // measured now that the element is laid out at its natural size
    let style = getComputedStyle(el)
    let open = {
        height: `${el.getBoundingClientRect().height}px`,
        marginTop: style.marginTop,
        marginBottom: style.marginBottom,
        opacity: 1
    }
    let shut = {height: '0px', marginTop: '0px', marginBottom: '0px', opacity: 0}

    el.style.overflow = 'hidden'
    let anim = el.animate([shut, open], {duration: duration, easing: 'ease-in-out'})
    anim.onfinish = () => { el.style.overflow = '' }
}

// wiring declared by field templates. The .html templates under
// corpus/field_templates carry their own bindings, e.g.
//
//     data-events="load:renderGeoPoint;input:setValue"
//
// "load" invokes the named function immediately, passing the element; any other
// occasion becomes an event listener, and the handler receives the Event as usual.
// Callbacks are looked up on `window` because they come from the per-field-type
// .js templates that the view concatenates into the page, so they are not in
// scope here. Elements are marked data-mounted so a second call is a no-op --
// pages that re-render fields can call this again safely.
// Field-template callbacks are invoked two ways: with an element (a data-events
// "load:" binding) or with an event (every other occasion). jQuery handed callbacks a
// normalized jQuery.Event that carried `target` as an OWN property, so the idiom
// `if (arg.hasOwnProperty('target')) arg = arg.target` told the two apart. A native
// Event exposes `target` on its prototype, so hasOwnProperty is always false there and
// the event object silently gets used as if it were an element. Use this instead.
function elFromEventOrEl(arg) {
    if (arg instanceof Event) return arg.currentTarget || arg.target
    return arg
}

function mountDataEvents(root=document) {
    let needsResize = false

    root.querySelectorAll('[data-events]:not([data-mounted])').forEach(el => {
        el.setAttribute('data-mounted', 'y')

        el.getAttribute('data-events').split(';').forEach(binding => {
            let [occasion, callback] = binding.split(':')
            if (!occasion || !callback || typeof window[callback] !== 'function') return

            if (occasion === 'load') window[callback](el)
            // 'resize' is a window event, so binding it to the element would never
            // fire. It is re-dispatched to every declaring element below instead.
            else if (occasion === 'resize') needsResize = true
            else el.addEventListener(occasion, window[callback])
        })
    })

    // bound once per page rather than once per mount: content_edit.html re-mounts on
    // every multi-value add, and the jQuery version it replaces attached a fresh
    // window handler each time a new resize-declaring element appeared.
    if (needsResize && !mountDataEvents._resize_bound) {
        mountDataEvents._resize_bound = true
        window.addEventListener('resize', () => {
            document.querySelectorAll('[data-events]').forEach(el => {
                el.getAttribute('data-events').split(';').forEach(binding => {
                    let [occasion, callback] = binding.split(':')
                    if (occasion === 'resize' && typeof window[callback] === 'function')
                        window[callback](el)
                })
            })
        })
    }
}

// Bootstrap 5 tooltips are opt-in, so anything rendered after page load needs
// initializing explicitly. safe to call repeatedly and on containers with none.
function initTooltips(container=document) {
    if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) return
    container.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        bootstrap.Tooltip.getOrCreateInstance(el)
    })
}
function hideTooltip(el) {
    if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) return
    let tip = bootstrap.Tooltip.getInstance(el)
    if (tip) tip.hide()
}

// showing/hiding Bootstrap modals.
// TEMPORARY SHIM: bootstrap.min.js is currently v4.0.0, whose modal is a jQuery
// plugin, while corpora.css is already v5.3.8. Once the JS is upgraded to 5.x the
// jQuery fallback below can be deleted and these become one-liners.
// NOTE: v4 also defines a `bootstrap` global, so feature-detect on
// getOrCreateInstance (v5-only) rather than on the global itself.
function bootstrapModalAPI() {
    let hasV5 = typeof bootstrap !== 'undefined' && bootstrap.Modal && bootstrap.Modal.getOrCreateInstance
    return hasV5 ? bootstrap.Modal : null
}
function showModal(el) {
    if (!el) return
    let modalAPI = bootstrapModalAPI()
    if (modalAPI) modalAPI.getOrCreateInstance(el).show()
    else $(el).modal('show')
}
function hideModal(el) {
    if (!el) return
    let modalAPI = bootstrapModalAPI()
    if (modalAPI) modalAPI.getOrCreateInstance(el).hide()
    else $(el).modal('hide')
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
    // note: array values are comma-joined into a single param, matching the
    // original behavior. use URLSearchParams.append() directly if you need
    // repeated keys (e.g. ?f=a&f=b) for Django's request.GET.getlist().
    return new URLSearchParams(params).toString()
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
        if(typeof obj != "object" || obj === null || !(x in obj))
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