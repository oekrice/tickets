from obtain_data import find_basic_info, find_station_info
import threading
import numpy as np
from datetime import datetime as dt, timedelta
from datetime import time
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
matplotlib.use("Agg")

def rank_stations(request_info, station_info):
    #This is for determining which stations it is worthwhile having a look at. 
    #For now, pick the ones which are best for time, and the (potentially) best for price, without any kind of mingling of the two concepts.
    #This should allow for an effective multi-split approach but also for the weird splits that allow for journeys that only my thing will manage.
    #Need to make this a bit smarter based on the individual request info. Some stations will just be impossible!
    #Don't necessarily need minimum times here, but could be helpful. 

    #Determine maximum time for this connection
    extra_time = request_info.get("max_extra_time",125)
    nesting_degree = request_info.get("nesting_degree",0)
    t0 = request_info['start_time'].hour*60 + request_info['start_time'].minute
    t1 = request_info['end_time'].hour*60 + request_info['end_time'].minute
    max_time = t1 - t0
    direct_time = station_info[request_info["destination"]]["in_time"] + extra_time
    max_time = min(max_time, direct_time)  #This is in minutes

    times = []; prices = []; stats= []
    for station in station_info:
        #Filter stations based on the timing above. Need a hard cutoff here which will actually reduce as the constraints become more extreme
        local_start_time = t0 + station_info[station]["in_time"]
        local_end_time = t1 - station_info[station]["out_time"]
        if (local_start_time <=  local_end_time) and (station_info[station]["in_time"] + station_info[station]["out_time"] < max_time) and station != request_info["destination"]:
            #Sort the stations based on the above
            prices.append(station_info[station]["price_score"])
            times.append(station_info[station]["time_score"])
            stats.append([station, local_start_time, local_end_time])
    timelist = [stat for _, stat in sorted(zip(times, stats))]
    pricelist = [stat for _, stat in sorted(zip(prices, stats))]
    #Merge the two in turn, ignoring duplicates. That's more tricky than you might imagine.
    bothlist = [None]*(len(timelist) + len(pricelist))
    bothlist[::2] = timelist
    bothlist[1::2] = pricelist

    final_list = []
    basic_list = []

    #Remove duplicates
    for i in range(len(bothlist)):
         if bothlist[i][0] not in basic_list:
             #Check for time constraints at this point. Can perhaps be more sophisticated about this in future... But also need to know the time of the initial request. Bugger.
             #Perhaps can focus efforts elsewhere in this regard...
             final_list.append(bothlist[i])
             basic_list.append(bothlist[i][0])
    return final_list

def find_journeys(request_info, splits = []):
    #This function is for finding journeys GENERALLY. The degree to how in-depth this is is given in request_info
    #A degree of 0 will just find the NR ones etc., and things can go from there to be more in-depth.
    #Each set of requests will check both those at this level and that BELOW (if appropriate). Thus can very much be circular.
    #Requires station checks to be done here or things will get lost...
    #print('Request logged', request_info)
    #If request info is greater than 0, need to do station checks
    nesting_degree = request_info.get("nesting_degree", 0)
    if request_info["request_depth"] > 0:
        #Need to do additional admin if there's more to it than a basic check
        station_info = find_station_info(request_info)   #This will attempt to rank the stations in the request based on geography, THEN other things like timing and price (which will take a request).
        station_checks = rank_stations(request_info, station_info)   #Need to be smarter with this, and just not check those where the timings are off. Can get a tmin and tmax for each station too, based on this particular request.
        nchecks_init = request_info.get("nchecks_init", 20)
        print(request_info["request_depth"], nesting_degree)
        if nesting_degree > 0:
            nrequests_max = 2  #This should be lower now as there can potentially be lots of threading within threading at this point. Maybe set to 10? Would be nice to get updates on this.
            nchecks_init = int(nchecks_init//10) + 1 #Seems reasonable for extreme checks
        elif request_info["request_depth"] == 1 and nesting_degree == 0:
            nrequests_max = 50
        else:
            nrequests_max = 20

        allchecks = station_checks[:nchecks_init]

        print('Checking ', nchecks_init, ' stations between', request_info["origin"], 'and', request_info["destination"] )
        individual_journeys = []

        if len(allchecks) > 0:
            nlumps = int(len(allchecks)/(nrequests_max/2) + 1)
            nrequests_actual = len(allchecks)/nlumps + 1

            for lump in range(nlumps):
                threads = []; lumpcount = 0
                minstat = int(nrequests_actual*lump); maxstat = int(min(nrequests_actual*(lump+1), len(allchecks)))

                if lump == 0:
                    #Do the basic check on direct journeys at the degree below this one
                    input_parameters = request_info.copy()   #All timing stuff is the same to begin with.
                    input_parameters["request_depth"] = input_parameters["request_depth"] - 1
                    input_parameters["nesting_degree"] = nesting_degree + 1
                    x = threading.Thread(target=find_journeys, args=(input_parameters, individual_journeys), daemon = False)
                    threads.append(x)
                    x.start()

                for station in allchecks[minstat:maxstat]:  #Alas this bit needs some multithreading, as it's far too slow.
                    #Let's do a basic search and see how long it takes. Do first section and second section separately. Hopefully not too long for a reasonably small list.
                    input_parameters_first = request_info.copy()   #All timing stuff is the same to begin with.
                    input_parameters_first["request_depth"] = input_parameters_first["request_depth"] - 1
                    input_parameters_first["nesting_degree"] = nesting_degree + 1
                    input_parameters_first["destination"] = station[0]
                    input_parameters_first["end_time"] = time(hour = int((station[2] + 5)//60), minute = int((station[2] + 5)%60))

                    input_parameters_second = request_info.copy()   #All timing stuff is the same to begin with.
                    input_parameters_second["request_depth"] = input_parameters_second["request_depth"] - 1
                    input_parameters_second["nesting_degree"] = nesting_degree + 1

                    input_parameters_second["origin"] = station[0]
                    input_parameters_second["start_time"] = time(hour = int((station[1] - 5)//60), minute = int((station[1] - 5)%60))

                    print(station, input_parameters_second["start_time"], input_parameters_first["end_time"])
                    x = threading.Thread(target=find_journeys, args=(input_parameters_first, individual_journeys), daemon = False)
                    threads.append(x)
                    x.start()

                    x = threading.Thread(target=find_journeys, args=(input_parameters_second, individual_journeys), daemon = False)
                    threads.append(x)
                    x.start()

                for j, x in enumerate(threads):
                    x.join()

                print('%d percent of stations checked...' % (100*maxstat/len(allchecks)))

        alljourneys = []; id_count = 0
        #Once these have all completed, save into a nice ordered list and check for reasonable combinations
        for journey_group in individual_journeys:
            for journey in journey_group:
                alljourneys.append(journey)
                alljourneys[-1]["id"] = id_count
                id_count += 1

        allsplits = []
        #Find combinations of these which work.
        for i1, j1 in enumerate(alljourneys):
            for i2, j2 in enumerate(alljourneys):
                if j1["destination"] == j2["origin"] and float(j1["arr_time"]) <= float(j2["dep_time"]):
                    #This is valid. Combine into a single journey object.
                    #Determine existing split stations here
                    allsplits.append({
                        'origin':j1['origin'], 'destination': j2['destination'],
                        'dep_time':j1['dep_time'], 'arr_time':j2['arr_time'],
                        'price':j1['price'] + j2['price'],
                        'split_stations':j1["split_stations"] + [j1["destination"]] + j2["split_stations"],
                        'split_arrs':j1["split_arrs"] + [j1["arr_time"]] + j2["split_arrs"],
                        'split_deps':j1["split_deps"] + [j2["dep_time"]] + j2["split_deps"]
                    })
            if j1["origin"] == request_info["origin"] and j1["destination"] == request_info["destination"]:   #This is a valid nourney without anything else
                    allsplits.append({
                        'origin':j1['origin'], 'destination': j1['destination'],
                        'dep_time':j1['dep_time'], 'arr_time':j1['arr_time'],
                        'price':j1['price'],
                        'split_stations':j1['split_stations'],
                        'split_arrs':j1['split_arrs'], 'split_deps':j1['split_deps']
                    })

        splits.append(filter_splits(request_info, allsplits))
        print(len(splits[0]), ' single splits found between', request_info["origin"], 'and', request_info["destination"])

        return splits
    else:
        individual_journeys = []
        request_info["nesting_degree"] = nesting_degree
        find_basic_info(request_info, alljourneys = individual_journeys)
        id_count = 0
        alljourneys = []
        #Once these have all completed, save into a nice ordered list and check for reasonable combinations
        for journey_group in individual_journeys:
            for journey in journey_group:
                alljourneys.append(journey)

        splits.append(filter_splits(request_info, alljourneys))

        return splits

def find_first_splits(request_info, station_checks):
    #The degree to which this goes in-depth depends entirely on the request info. Should be quite general ideally, but that's very tricky.

    nchecks_init = request_info.get("nchecks_init", 20)
    allchecks = station_checks[:nchecks_init]
    nrequests_max = 100  #This should be lower now as there can potentially be lots of threading within threading at this point. Maybe set to 10? Would be nice to get updates on this.
    nlumps = int(len(allchecks)/(nrequests_max/2) + 1)
    nrequests_actual = len(allchecks)/nlumps + 1
    individual_journeys = []
    for lump in range(nlumps):
        threads = []; lumpcount = 0
        minstat = int(nrequests_actual*lump); maxstat = int(min(nrequests_actual*(lump+1), len(allchecks)))

        if lump == 0:
            #Do the basic check on direct journeys
            x = threading.Thread(target=find_basic_info, args=(request_info, individual_journeys), daemon = False)
            threads.append(x)
            x.start()

        for station in allchecks[minstat:maxstat]:  #Alas this bit needs some multithreading, as it's far too slow.
            #Let's do a basic search and see how long it takes. Do first section and second section separately. Hopefully not too long for a reasonably small list.
            input_parameters_first = request_info.copy()   #All timing stuff is the same to begin with.
            input_parameters_first["destination"] = station[0]
            input_parameters_first["end_time"] = time(hour = int((station[2] + 5)//60), minute = int((station[2] + 5)%60))

            input_parameters_second = request_info.copy()   #All timing stuff is the same to begin with.
            input_parameters_second["origin"] = station[0]
            input_parameters_first["start_time"] = time(hour = int((station[1] - 5)//60), minute = int((station[1] - 5)%60))

            print(station, input_parameters_first["start_time"], input_parameters_first["end_time"])
            x = threading.Thread(target=find_basic_info, args=(input_parameters_first, individual_journeys), daemon = False)
            threads.append(x)
            x.start()

            x = threading.Thread(target=find_basic_info, args=(input_parameters_second, individual_journeys), daemon = False)
            threads.append(x)
            x.start()

        for j, x in enumerate(threads):
            x.join()

        print('%d percent of stations checked...' % (100*maxstat/len(allchecks)))

    alljourneys = []; id_count = 0
    #Once these have all completed, save into a nice ordered list and check for reasonable combinations
    for journey_group in individual_journeys:
        for journey in journey_group:
            alljourneys.append(journey)
            alljourneys[-1]["id"] = id_count
            id_count += 1

    #Find combinations of these which work. 
    print('All trains found. Finding valid combinations.')
    splits = []
    for i1, j1 in enumerate(alljourneys):
        for i2, j2 in enumerate(alljourneys):
            if j1["destination"] == j2["origin"] and float(j1["arr_time"]) <= float(j2["dep_time"]):
                #This is valid. Combine into a single journey object.
                #Determine existing split stations here
                splits.append({
                    'origin':j1['origin'], 'destination': j2['destination'], 
                    'dep_time':j1['dep_time'], 'arr_time':j2['arr_time'],
                    'price':j1['price'] + j2['price'],
                    'split_stations':j1["split_stations"] + [j1["destination"]] + j2["split_stations"],
                    'split_arrs':j1["split_arrs"] + [j1["arr_time"]] + j2["split_arrs"],
                    'split_deps':j1["split_deps"] + [j2["dep_time"]] + j2["split_deps"]
                })
        if j1["origin"] == request_info["origin"] and j1["destination"] == request_info["destination"]:   #This is a valid nourney without anything else
                splits.append({
                    'origin':j1['origin'], 'destination': j1['destination'], 
                    'dep_time':j1['dep_time'], 'arr_time':j1['arr_time'],
                    'price':j1['price'],
                    'split_stations':j1['split_stations'],
                    'split_arrs':j1['split_arrs'], 'split_deps':j1['split_deps']
                })

     #Add on direct journeys? Would be better to do that initially in the multithreading...  I think it's fine.

    return splits

def filter_splits(request_info, unfiltered_splits):
    #Uses the price matrix approach to filter the splits. Current going to base it on departure time and journey length. Resolution will depend on how long such things take...
    #Actually, this is silly. Let's determine bounds first. Or could just do that based on the request? Yes!
    Path("plots").mkdir(parents=True, exist_ok=True)

    res = 1/60
    time_spread = request_info.get("time_spread",10)/60   #Spread times by these in each direction (resolution of not caring)
    t0 = request_info['start_time']
    t1 = request_info['end_time']
    #jtime = abs(t1 - t0).total_seconds()/3600   #Number of hours
    minx = t0.hour + t0.minute/60 - res; maxx = t1.hour + t1.minute/60 + res
    miny = 0; maxy = maxx-minx + 2*res
    nbins_x = int((maxx - minx)/res) + 1; nbins_y = int((maxy - miny)/res) + 1
    xs = np.linspace(minx, maxx, nbins_x + 1); ys = np.linspace(miny, maxy, nbins_y + 1)
    res = xs[1] - xs[0]
    price_matrix = 1e6*np.ones((len(xs), len(ys)))   #Set as unattainably high to begin with, and reduce if necessary
    spread_bins = int(time_spread/res)
    local_matrix = price_matrix.copy() 
    minprice = 1e6; maxprice = 0
    mintime = 1e6
    for split in unfiltered_splits:
        
        t0 = dt.strptime(split["dep_time"], "%H%M")
        t1 = dt.strptime(split["arr_time"], "%H%M")
        jtime = abs(t1 - t0).total_seconds()/3600   #Number of hours
        mintime = min(mintime, jtime)
        #Check if this split is an optimal one (so far!), and if so update the matrix for it.
        xbin = np.digitize(t0.hour  + t0.minute/60, xs) - 1
        ybin = np.digitize(jtime, ys) - 1
        maxprice = max(split["price"], maxprice)
        minprice = min(split["price"], minprice)
        if split["price"] < price_matrix[xbin,ybin]:
            spreadmin = max(0, xbin-spread_bins); spreadmax = min(xbin+spread_bins,len(xs))
            #Update the price matrix here. Don't want loops but might have to have them... Bugger.
            local_matrix[spreadmin:spreadmax+1,ybin] = split["price"]
            local_matrix[spreadmin:spreadmax+1,ybin+1:] = split["price"] - 0.005  #Don't bother with ones which are exactly the same price
            #Update for journeys which left earlier but took longer (arriving at the same time or later)
            for c, i in enumerate(range(xbin-1, -1, -1)):
                if ybin + c < len(ys):
                    local_matrix[i,ybin+c+1:] = split["price"] - 0.005
            price_matrix = np.minimum(price_matrix, local_matrix)
            local_matrix[:,:] = 1e6


    maxprice = 0
    xmin = 1e6; xmax = 0
    ymin = 1e6; ymax = 0

    #Actually filter the splits based upon this matrix.
    filtered_splits = []
    max_extra_time = request_info.get("max_extra_time", 125)
    time_limit = mintime + max_extra_time/60
    for split in unfiltered_splits:
        
        t0 = dt.strptime(split["dep_time"], "%H%M")
        t1 = dt.strptime(split["arr_time"], "%H%M")
        jtime = abs(t1 - t0).total_seconds()/3600   #Number of hours
        #Check if this split is an optimal one (so far!), and if so update the matrix for it.
        xbin = np.digitize(t0.hour  + t0.minute/60, xs) - 1
        ybin = np.digitize(jtime, ys) - 1
        if split["price"] <= price_matrix[xbin,ybin] and jtime < time_limit:
            maxprice = max(maxprice, split["price"])
            #Update the price matrix here. Don't want loops but might have to have them... Bugger.
            filtered_splits.append(split)
            price_matrix[xbin,ybin] -= 0.005   #Don't add a split with the same price here. Just keep the first one.
            plt.scatter(t0.hour  + t0.minute/60, jtime, c = 'red', zorder = 10, edgecolors = 'black')
            xmin = min(xmin, t0.hour  + t0.minute/60); xmax = max(xmax, t0.hour  + t0.minute/60)
            ymin = min(ymin, jtime); ymax = max(ymax, jtime)
    price_matrix[price_matrix > 1e5] = maxprice
    if False:
        plt.xticks(range(0,24))
        plt.yticks(range(0,24))
        plt.xlim(xmin,xmax)
        plt.ylim(ymin-0.5,ymax+0.5)
        plt.pcolormesh(xs, ys, price_matrix.T)
        plt.colorbar()
        plt.savefig('plots/plot2.png')
        plt.close()

    filtered_splits = sorted(filtered_splits, key=lambda journey: int(journey['arr_time']))
    filtered_splits = sorted(filtered_splits, key=lambda journey: int(journey['dep_time']))
    
    return filtered_splits
