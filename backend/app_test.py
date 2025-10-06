#Test for basic functions
from obtain_data import find_basic_info, find_station_info
from data_functions import rank_stations, find_first_splits, filter_splits
from datetime import datetime as dt, timedelta
import datetime
import json, sys
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

origin = "NCL"; destination = "YRK"
request_info = {"origin": origin, 
                "destination": destination, 
                "start_time": datetime.time(9,0), 
                "date": dt.today() + timedelta(days = 1), 
                "end_time": datetime.time(18,0),
                "ignore_previous": False,
                "nchecks_init":10,
                "max_extra_time":65
                }   


direct_journeys = find_basic_info(request_info)
sys.exit()

station_info = find_station_info(request_info)   #This will attempt to rank the stations in the request based on geography, THEN other things like timing and price (which will take a request).
station_checks = rank_stations(request_info, station_info)   #Need to be smarter with this, and just not check those where the timings are off. Can get a tmin and tmax for each station too, based on this particular request.
single_splits_unfiltered = find_first_splits(request_info, station_checks)
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
