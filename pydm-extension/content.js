let enabled = true;



chrome.storage.local.get(
["enabled"],
(data)=>{


    enabled =
        data.enabled !== false;


});




chrome.storage.onChanged.addListener(
(changes)=>{


    if(changes.enabled)
    {

        enabled =
            changes.enabled.newValue;

    }

});






document.addEventListener(
"click",
(e)=>{


    if(!enabled)
        return;



    let link =
        e.target.closest("a");



    if(!link)
        return;



    let url =
        link.href;



    if(
        /\.(exe|msi|zip|rar|7z|iso|apk|pdf|mp4|mkv)$/i.test(url)
    )
    {


        e.preventDefault();



        chrome.runtime.sendMessage({

            type:"link",

            url:url

        });


    }


},
true);