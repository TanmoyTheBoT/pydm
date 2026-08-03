from flask import Flask, request
import threading


app = Flask(__name__)


main_window = None



def set_window(window):

    global main_window

    main_window = window



@app.post("/download")
def receive_download():

    data = request.json


    url = data.get(
        "url"
    )


    if main_window and url:

       main_window.set_url(url)

       main_window.showNormal()

       main_window.raise_()

       main_window.activateWindow()


    return {
        "status": "ok"
    }



def start_server():

    app.run(
        host="127.0.0.1",
        port=8765,
        debug=False
    )