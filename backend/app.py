#Start of my project figuring out how the internet works. Very good.

from flask import Flask, request
import flask
import json
from flask_cors import CORS
import time
from obtain_data import find_basic_info

app = Flask(__name__)
CORS(app)
#This decorator tells the frontend to run the below function when the url "/" is used.

@app.route("/")
def hello():
    return "Hello, World!"

@app.route('/users', methods=["GET","POST"])   #Same as above, but the methods are 'GET' and 'POST' for to and fro, respectively
def users():
    print("users endpoint reached...")
    if request.method == "GET":
        with open ("users.json", "r") as f:
            data = json.load(f)
            data.append({"username": "user4", "pets": ["hamster"]})
            return flask.jsonify(data)
    if request.method == "POST":
        received_data = request.get_json()
        print("received data: %s" % received_data)
        message = received_data['data']
        return_data = {
            "status": "success",
            "origin": f"received: {message}"
        }
        return flask.Response(response=json.dumps(return_data), status=201)
    
@app.route('/trains', methods = ["GET", "POST"])
def trains():
    print('Testing obtaining train info')
    if request.method == "GET": #Obtain some data
        with open ("users.json", "r") as f:
            data = [{"train_id":0, "origin":"NCL", "destination":"YRK"}]
            #data = json.load(f)
            return flask.jsonify(data)
    if request.method == "POST":
        #Get the data from the input
        input_data = request.get_json()
        print("received data: %s" % input_data)
        origin = input_data['origin']
        destination = input_data['destination']

        request_info = {"origin": origin, "destination": destination}   #Can add time constraints to this later
        direct_journeys = find_basic_info(request_info)


        return_data = direct_journeys

        time.sleep(1.0)
        print('Something happened')
        return flask.Response(response=json.dumps(return_data), status=201)

#This bit should come last, I think, as it calls things from above
if __name__ == "__main__":
    app.run("localhost", 14752)

