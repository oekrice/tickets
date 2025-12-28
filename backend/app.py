#Start of my project figuring out how the internet works. Very good.

from flask import Flask, request, send_from_directory
import flask
import json
from flask_cors import CORS
import time
from obtain_data import find_basic_info, find_stations
from data_functions import rank_stations, find_first_splits, find_second_splits, find_second_splits, filter_splits
from datetime import datetime as dt, timedelta
from pathlib import Path
from waitress import serve
import sys
import datetime

#sys.path.append("/extra/tmp/vgjn10/python/")

#source ../.venv/bin/activate.csh

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)
#This decorator tells the frontend to run the below function when the url "/" is used.

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

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
    if request.method == "POST":
        #Get the data from the input
        input_data = request.get_json()
        origin = input_data['origin']
        destination = input_data['destination']
        date = dt.strptime(input_data['date'].strip(), "%Y-%m-%d").date()
        arrive_time = dt.strptime(input_data['arriveTime'].strip(), "%H:%M").time()
        depart_time = dt.strptime(input_data['departTime'].strip(), "%H:%M").time()

        if input_data['requestStatus'] == -1:  #Just for checking that a route is possible...
            request_info = {"origin": origin, 
                            "destination": destination,
                            "date": date, 
                            "start_time": depart_time, 
                            "end_time": arrive_time, 
                            "request_depth": -1}   #Can add time constraints to this later. Or immediately? Yes, that should be the next thing.

        elif input_data['requestStatus'] == 0:  #Just look for the direct trains (no splitting)
            request_info = {"origin": origin, 
                            "destination": destination,
                            "date": date, 
                            "start_time": depart_time, 
                            "end_time": arrive_time, 
                            "request_depth": 0}   #Can add time constraints to this later. Or immediately? Yes, that should be the next thing.

        elif input_data['requestStatus'] == 1:  #Look for single splits
            request_info = {"origin": origin,
                            "destination": destination,
                            "date": date,
                            "start_time": depart_time,
                            "end_time": arrive_time,
                            "ignore_previous": False,
                            "nchecks_init":100,
                            "max_extra_time":125,
                            "time_spread":10,
                            "request_depth":1
                            }

        elif input_data['requestStatus'] == 2:  #Look for more splits. Now depends on a status so it can update in due course.
            if input_data['quick'] and input_data['checkNumber'] > 0:
                nchecks_init = 10
            else:
                nchecks_init = 100
            request_info = {"origin": origin,
                            "destination": destination,
                            "date": date,
                            "start_time": depart_time,
                            "end_time": arrive_time,
                            "ignore_previous": False,
                            "nchecks_init":nchecks_init,
                            "max_extra_time":125,
                            "time_spread":10,
                            "request_depth":2,
                            "check_number":input_data['checkNumber']
                            }
            
        existing_journeys = input_data.get('trainData', []) #Obtain these to be appended to if necessary
        print('Received request with details', request_info, 'and', len(existing_journeys), 'existing journeys')

        if request_info["request_depth"] == -1:
            journeys = find_basic_info(request_info, [])
            return_data = journeys

        elif request_info["request_depth"] == 0:
            #This is just a basic request. So do that.
            journeys = find_basic_info(request_info, [])
            journeys = filter_splits(request_info, journeys)
            return_data = journeys

        elif request_info["request_depth"] == 1 or (request_info["request_depth"] == 2 and request_info["check_number"] == 0):
            station_info = find_stations(request_info)  #This can definitely be done with multithreading proper like, and should happen at a different time to everything else. Getting things to load into the html would be nice

            #The checks at this point will depend on the magnitude of the request
            station_checks = rank_stations(request_info, station_info, 1) #This is automatically filtered to the right level later on
            # print('Testing')
            # second_checks = rank_stations(request_info, station_info, 2)

            print('Finding single splits between', request_info["origin"], 'and', request_info["destination"])
            journeys = find_first_splits(request_info, station_checks)
            print(len(journeys), ' valid journeys before filtering, stage 1')
            journeys = filter_splits(request_info, journeys)
            print(len(journeys), ' valid journeys after filtering, stage 1')
            return_data = journeys

        elif (request_info["request_depth"] == 2 and request_info["check_number"] > 0):
            if request_info["request_depth"] == 2 and len(existing_journeys) > 0:
                journeys = [existing_journeys]
                station_info = find_stations(request_info)  #This can definitely be done with multithreading proper like, and should happen at a different time to everything else. Getting things to load into the html would be nice
                second_checks = rank_stations(request_info, station_info, 2)
                print('All second checks', second_checks)
                #Run through these second checks as if they are firsts.
                if request_info["check_number"] > len(second_checks):
                    #print('Testing exceeding the length of the list')
                    return flask.Response(response=json.dumps([]), status=201, mimetype='application/json' )
                else:                     
                    station = second_checks[request_info["check_number"] - 1]
                    print('Trying stage 2 split at', station[0])
                    journeys.append(find_second_splits(request_info, station))

                alljourneys = []; id_count = 0
                #Once these have all completed, save into a nice ordered list and check for reasonable combinations
                for journey_group in journeys:
                    for journey in journey_group:
                        alljourneys.append(journey)
                        alljourneys[-1]["id"] = id_count
                        id_count += 1

                print(len(alljourneys), ' valid journeys before filtering stage 2')
                alljourneys = filter_splits(request_info, alljourneys)
                print(len(alljourneys), ' valid journeys after filtering stage 2')

                return_data = alljourneys

        with open('testdata.json', "w") as f:
            json.dump(return_data, f)
      
        return flask.Response(response=json.dumps(return_data), status=201, mimetype='application/json')

#This bit should come last, I think, as it calls things from above
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)

