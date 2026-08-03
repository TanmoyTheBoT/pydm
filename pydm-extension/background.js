let nativePort = null;



// ============================
// Connect PyDM Native Host
// ============================

function connectPyDM()
{

    if(nativePort)
        return;


    try
    {

        nativePort =
            chrome.runtime.connectNative(
                "com.pydm.host"
            );


        nativePort.onDisconnect.addListener(
        ()=>{


            console.log(
                "PyDM disconnected",
                chrome.runtime.lastError
            );


            nativePort = null;


        });


    }
    catch(error)
    {

        console.error(
            "Native host error:",
            error
        );


        nativePort = null;

    }

}





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


    if(enabled)
    {


        chrome.action.setIcon({

            path:{
                16:"icons/enabled-16.png",
                48:"icons/enabled-48.png",
                128:"icons/enabled-128.png"
            }

        });


    }
    else
    {


        chrome.action.setIcon({

            path:{
                16:"icons/disabled-16.png",
                48:"icons/disabled-48.png",
                128:"icons/disabled-128.png"
            }

        });


    }


}







// ============================
// Install
// ============================

chrome.runtime.onInstalled.addListener(
()=>{


    chrome.storage.local.set({

        enabled:true

    });


    setIcon(true);


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







// ============================
// Chrome Download Detection
// ============================

chrome.downloads.onCreated.addListener(
(download)=>{


    sendToPyDM({

        type:"download",

        url:download.url,

        filename:download.filename


    });


});








// ============================
// Message From content.js
// ============================

chrome.runtime.onMessage.addListener(
(message)=>{


    if(
        message.type === "link"
    )
    {


        sendToPyDM({

            type:"download",

            url:message.url,

            filename:""


        });


    }


});