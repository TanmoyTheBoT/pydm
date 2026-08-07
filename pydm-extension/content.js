const STORAGE_KEY = "enabled";
const SAFE_PROTOCOLS = new Set(["http:", "https:"]);
const DOWNLOAD_EXTENSIONS = /\.(exe|msi|zip|rar|7z|iso|apk|pdf|mp4|mkv|mp3|dll|deb|rpm|dmg|pkg|tar|gz|bz2|xz)$/i;
const DOWNLOAD_PATH_HINTS = /(?:\/latest|\/download|\/downloads|\/installer|\/setup|\/install)(?:\/|$)/i;

let enabled = true;

function updateEnabledState(value)
{
    enabled = value !== false;
}

function loadEnabledState()
{
    chrome.storage.local.get(
        [STORAGE_KEY],
        (result)=>{
            updateEnabledState(result[STORAGE_KEY]);
        }
    );
}

function shouldRouteDownload(url)
{
    if(typeof url !== "string" || !url.trim())
        return false;

    try
    {
        const parsed = new URL(url, window.location.href);

        if(!SAFE_PROTOCOLS.has(parsed.protocol))
            return false;

        const pathname = parsed.pathname.toLowerCase();

        return DOWNLOAD_EXTENSIONS.test(pathname)
            || parsed.searchParams.has("download")
            || DOWNLOAD_PATH_HINTS.test(pathname);
    }
    catch(error)
    {
        return DOWNLOAD_EXTENSIONS.test(url)
            || DOWNLOAD_PATH_HINTS.test(url);
    }
}

function getDownloadTarget(target)
{
    if(!target)
        return null;

    const element = target instanceof Element
        ? target
        : target.parentElement;

    if(!element)
        return null;

    const link = element.closest("a, area, [download], [data-pydm-download]");

    if(!link)
        return null;

    const url = link.getAttribute("href")
        || link.getAttribute("data-url")
        || link.getAttribute("download");

    if(!url)
        return null;

    const hasExplicitDownload = link.hasAttribute("download")
        || link.hasAttribute("data-pydm-download");

    if(hasExplicitDownload || shouldRouteDownload(url))
    {
        return {
            url:url,
            source:hasExplicitDownload ? "download-attr" : "link"
        };
    }

    return null;
}

function sendDownloadRequest(url, source)
{
    chrome.runtime.sendMessage({
        type:"link",
        url:url,
        source:source
    });
}

loadEnabledState();

chrome.storage.onChanged.addListener(
    (changes, areaName)=>{
        if(areaName === "local" && changes[STORAGE_KEY])
        {
            updateEnabledState(changes[STORAGE_KEY].newValue);
        }
    }
);

document.addEventListener(
    "click",
    (event)=>{
        if(!enabled || event.defaultPrevented)
            return;

        const target = getDownloadTarget(event.target);

        if(!target)
            return;

        event.preventDefault();
        event.stopPropagation();

        sendDownloadRequest(target.url, target.source);
    },
    true
);
