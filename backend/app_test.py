#Test for basic functions
from obtain_data import find_basic_info, find_station_info, find_stations
from data_functions import rank_stations, find_first_splits, filter_splits, find_journeys, find_second_splits
from datetime import datetime as dt, timedelta
import datetime
import json, sys
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

#source ../.venv/bin/activate.csh

origin = "YRK"; destination = "DBY"
request_info = {"origin": origin, 
                "destination": destination, 
                "start_time": datetime.time(9,0), 
                "date": dt.today() + timedelta(days = 1), 
                "end_time": datetime.time(13,0),
                "ignore_previous": False,
                "nchecks_init":100,
                "max_extra_time":125,
                "request_depth": 2,
                "check_number": 0   #For the second level of request depths, which can take some time.
                }   


if request_info["request_depth"] == 0:
    #This is just a basic request. So do that.
    journeys = find_basic_info(request_info, [])
    journeys = filter_splits(request_info, journeys)

else:
    station_info = find_stations(request_info)  #This can definitely be done with multithreading proper like, and should happen at a different time to everything else. Getting things to load into the html would be nice

    #The checks at this point will depend on the magnitude of the request
    station_checks = rank_stations(request_info, station_info, 1) #This is automatically filtered to the right level later on

    print('Finding single splits between', request_info["origin"], 'and', request_info["destination"])
    journeys = find_first_splits(request_info, station_checks)
    print(len(journeys), ' valid journeys before filtering stage 1')
    journeys = filter_splits(request_info, journeys)
    print(len(journeys), ' valid journeys after filtering stage 1')
    journeys = [journeys]

    if request_info["request_depth"] == 2 and len(journeys) > 0:
        station_info = find_stations(request_info)  #This can definitely be done with multithreading proper like, and should happen at a different time to everything else. Getting things to load into the html would be nice
        second_checks = rank_stations(request_info, station_info, 2)
        #Run through these second checks as if they are firsts.

        for station in second_checks[:1]:
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

        for journey in alljourneys:
            print(journey)
        #Continue and find further stations for splitting
    #This is for second-


sys.exit()

journeys = []
find_journeys(request_info, journeys)
sys.exit()

direct_journeys = find_basic_info(request_info)
station_info = find_station_info(request_info)   #This will attempt to rank the stations in the request based on geography, THEN other things like timing and price (which will take a request).
station_checks = rank_stations(request_info, station_info)   #Need to be smarter with this, and just not check those where the timings are off. Can get a tmin and tmax for each station too, based on this particular request.
single_splits_unfiltered = find_first_splits(request_info, station_checks)

for journey in single_splits_unfiltered:
    print(journey['split_stations'],journey['split_arrs'],journey['split_deps'] )
sys.exit()
# print('Filtering...')
# with open('test1.json', "w") as f:
#     json.dump(single_splits_unfiltered, f)

with open('test1.json') as f:
    single_splits_unfiltered = json.load(f)

def plot_splits(splits, id):
    xs = []; ys = []; cs = []
    for journey in splits:
        #Determine some info and plot
        t0 = dt.strptime(journey["dep_time"], "%H%M")
        t1 = dt.strptime(journey["arr_time"], "%H%M")
        jtime = abs(t1 - t0).total_seconds()/3600   #Number of hours
        jstart = abs(t0 - dt.strptime("0000", "%H%M")).total_seconds()/3600
        price = journey["price"]
        xs.append(jstart); ys.append(jtime); cs.append(price)
    plt.xticks(range(0,24))
    plt.yticks(range(0,24))
    plt.xlabel('Departure time')
    plt.ylabel('Journey length')
    plt.scatter(xs,ys,c=cs)
    plt.colorbar(label = 'price')
    plt.savefig('plots/plot%d.png' % id)
    plt.close()

plot_splits(single_splits_unfiltered,0)
single_splits = filter_splits(request_info, single_splits_unfiltered)
plot_splits(single_splits,1)
print('Filtered')
print('Number of unfiltered splits', len(single_splits_unfiltered))
print('Number of filtered splits', len(single_splits))

print(single_splits)
#basic_journeys = find_basic_info(request_info)
