async function renderLink(target) {
    let url = target.getAttribute('data-value')
    let label = target.getAttribute('data-label')

    const link = document.createElement('a')
    link.href = url
    link.textContent = label
    link.target = '_blank'
    target.appendChild(link)

    try {
        const response = await fetch(url, {
            method: 'HEAD',
            mode: 'cors'
        })
        const contentType = response.headers.get('Content-Type')

        if (contentType && contentType.startsWith('image/')) {
            const thumbnail = document.createElement('img')

            thumbnail.src = url
            thumbnail.alt = label
            thumbnail.classList.add('p-md-4')
            thumbnail.style.maxWidth = `${target.parentElement.clientWidth}px`
            thumbnail.style.cursor = 'pointer'
            thumbnail.onclick = () => window.open(url, '_blank')

            target.replaceChild(thumbnail, link)
        }
    } catch (error) {}
}
