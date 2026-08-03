let nativePort = null;



function connectPyDM()
{

    if(nativePort)
        return;


    nativePort =
        chrome.runtime.connectNative(
            "com.pydm.host"
        );


    nativePort.onDisconnect.addListener(
        ()=>{

            nativePort = null;

        }
    );

}




function sendToPyDM(data)
{

    chrome.storage.local.get(
        ["enabled"],
        (state)=>{


            if(state.enabled === false)
                return;



            connectPyDM();



            if(nativePort)
            {

                nativePort.postMessage(
                    data
                );

            }


        }
    );

}




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





// First install

chrome.runtime.onInstalled.addListener(
()=>{


    chrome.storage.local.set({

        enabled:true

    });


    setIcon(true);


});





// Extension icon click

chrome.action.onClicked.addListener(
()=>{


    chrome.storage.local.get(
        ["enabled"],
        (data)=>{


            let enabled =
                data.enabled !== false;



            enabled = !enabled;



            chrome.storage.local.set({

                enabled:enabled

            });



            setIcon(
                enabled
            );


        }
    );


});






// Chrome download detector

chrome.downloads.onCreated.addListener(
(item)=>{


    sendToPyDM({

        type:"download",

        url:item.url,

        filename:item.filename

    });


});






// Receive from content.js

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