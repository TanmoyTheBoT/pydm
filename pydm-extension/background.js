const STORAGE_KEY = "enabled";
const NATIVE_HOST_NAME = "com.pydm.host";
const SAFE_PROTOCOLS = new Set(["http:", "https:"]);
const DOWNLOAD_EXTENSIONS = /\.(exe|msi|zip|rar|7z|iso|apk|pdf|mp4|mkv|mp3|dll|deb|rpm|dmg|pkg|tar|gz|bz2|xz)$/i;
const DOWNLOAD_PATH_HINTS = /(?:\/latest|\/download|\/downloads|\/installer|\/setup|\/install)(?:\/|$)/i;
const BROWSER_SESSION_START_MS = Date.now();

let nativePort = null;
let isConnecting = false;

function isNewSessionDownload(download)
{
    if(!download || typeof download !== "object")
        return false;

    if(typeof download.startTime !== "string")
        return true;

    const startTimeMs = Date.parse(download.startTime);
    if(Number.isNaN(startTimeMs))
        return true;

    return startTimeMs >= BROWSER_SESSION_START_MS;
}

function setIcon(enabled)
{
    chrome.action.setIcon({
        path:{
            16: enabled ? "icons/enabled-16.png" : "icons/disabled-16.png",
            48: enabled ? "icons/enabled-48.png" : "icons/disabled-48.png",
            128: enabled ? "icons/enabled-128.png" : "icons/disabled-128.png"
        }
    });
}

function updateExtensionState(value)
{
    const enabled = value !== false;
    setIcon(enabled);
}

function connectPyDM()
{
    if(nativePort || isConnecting)
        return nativePort;

    isConnecting = true;

    try
    {
        nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);

        nativePort.onDisconnect.addListener(()=>{
            console.log("PyDM disconnected", chrome.runtime.lastError);
            nativePort = null;
            isConnecting = false;
        });
    }
    catch(error)
    {
        console.error("Native host error:", error);
        nativePort = null;
        isConnecting = false;
    }

    return nativePort;
}

function createContextMenuItem()
{
    chrome.contextMenus.create({
        id: "download-with-pydm",
        title: "Download with PyDM",
        contexts: ["link", "image", "video", "audio"],
    });
}

chrome.contextMenus.onClicked.addListener(
    (info)=>{
        if(info.menuItemId !== "download-with-pydm")
            return;

        const url = info.linkUrl || info.srcUrl;
        if(!url)
            return;

        sendToPyDM({
            type: "download",
            url: url,
            source: "context-menu"
        });
    }
);





// ============================
// Send URL to PyDM
// ============================

function sendToPyDM(data)
{


    chrome.storage.local.get(
    ["enabled"],
    (state)=>{


        let enabled =
            state.enabled !== false;



        if(!enabled)
            return;



        connectPyDM();



        if(nativePort)
        {


            nativePort.postMessage(
                data
            );


            console.log(
                "Sent to PyDM:",
                data
            );


        }


    });


}







// ============================
// Change Extension Icon
// ============================

function setIcon(enabled)
{
    chrome.action.setIcon({
        path:{
            16: enabled ? "icons/enabled-16.png" : "icons/disabled-16.png",
            48: enabled ? "icons/enabled-48.png" : "icons/disabled-48.png",
            128: enabled ? "icons/enabled-128.png" : "icons/disabled-128.png"
        }
    });
}







// ============================
// Install
// ============================

chrome.runtime.onInstalled.addListener(()=>{
    chrome.storage.local.set({
        [STORAGE_KEY]:true
    });
    updateExtensionState(true);
    createContextMenuItem();
});

chrome.runtime.onStartup.addListener(()=>{
    createContextMenuItem();
});







// ============================
// Click Extension Icon
// Enable / Disable
// ============================

chrome.action.onClicked.addListener(
()=>{


    chrome.storage.local.get(
    ["enabled"],
    (data)=>{


        let enabled =
            data.enabled !== false;



        enabled =
            !enabled;



        chrome.storage.local.set({

            enabled:enabled

        });



        setIcon(
            enabled
        );



        console.log(
            enabled
            ?
            "PyDM Enabled"
            :
            "PyDM Disabled"
        );


    });


});







function isLikelyDownloadUrl(url)
{
    if(typeof url !== "string" || !url.trim())
        return false;

    try
    {
        const parsed = new URL(url);

        if(!SAFE_PROTOCOLS.has(parsed.protocol))
            return false;

        const pathname = parsed.pathname.toLowerCase();

        return DOWNLOAD_EXTENSIONS.test(pathname)
            || DOWNLOAD_PATH_HINTS.test(pathname)
            || parsed.searchParams.has("download");
    }
    catch(error)
    {
        return false;
    }
}


async function resolveDownloadTarget(url)
{
    if(!isLikelyDownloadUrl(url))
        return null;

    const candidates = [
        { method:"HEAD", headers:{Accept:"*/*"} },
        { method:"GET", headers:{Accept:"application/octet-stream, */*"} }
    ];

    for(const candidate of candidates)
    {
        try
        {
            const response = await fetch(
                url,
                {
                    method:candidate.method,
                    headers:candidate.headers,
                    redirect:"follow",
                    cache:"no-store"
                }
            );

            const finalUrl = response.url || url;
            const disposition = response.headers.get("content-disposition") || "";

            if(
                isLikelyDownloadUrl(finalUrl)
                || /attachment/i.test(disposition)
                || /filename=/i.test(disposition)
            )
            {
                return {
                    url:finalUrl,
                    filename:""
                };
            }
        }
        catch(error)
        {
            console.warn("Unable to resolve download URL", error);
        }
    }

    return {
        url:url,
        filename:""
    };
}


// ============================
// Chrome Download Detection
// ============================

chrome.downloads.onCreated.addListener(
    (download)=>{
        if(!isNewSessionDownload(download))
            return;

        if(!isLikelyDownloadUrl(download.url))
            return;

        chrome.downloads.cancel(
            download.id,
            ()=>{
                if(chrome.runtime.lastError)
                {
                    console.warn("Failed to cancel download", chrome.runtime.lastError);
                }
            }
        );

        sendToPyDM({
            type:"download",
            url:download.url,
            filename:download.filename
        });
    }
);








// ============================
// Message From content.js
// ============================

chrome.runtime.onMessage.addListener(
    (message, sender, sendResponse)=>{
        if(message?.type !== "link")
            return false;

        (async()=>{
            const target = await resolveDownloadTarget(message.url);

            if(target)
            {
                sendToPyDM({
                    type:"download",
                    url:target.url,
                    filename:target.filename
                });
            }

            sendResponse({
                ok:!!target
            });
        })();

        return true;
    }
);