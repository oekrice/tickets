from obtain_data import find_basic_info
import threading
import numpy as np
from datetime import datetime as dt, timedelta
import matplotlib.pyplot as plt

def rank_stations(request_info, station_info):
    #This is for determining which stations it is worthwhile having a look at. 
    #For now, pick the ones which are best for time, and the (potentially) best for price, without any kind of mingling of the two concepts.
    #This should allow for an effective multi-split approach but also for the weird splits that allow for journeys that only my thing will manage.
    times = []; prices = []; stats= []
    for station in station_info:
        #Sort the stations based on the above
        prices.append(station_info[station]["price_score"])
        times.append(station_info[station]["time_score"])
        stats.append(station)
    timelist = [stat for _, stat in sorted(zip(times, stats))]
    pricelist = [stat for _, stat in sorted(zip(prices, stats))]
    #Merge the two in turn, ignoring duplicates. That's more tricky than you might imagine.
    bothlist = [None]*(len(timelist) + len(pricelist))
    bothlist[::2] = timelist
    bothlist[1::2] = pricelist

    final_list = []
    #Remove duplicates
    for i in range(len(bothlist)):
         if bothlist[i] not in final_list:
             #Check for time constraints at this point. Can perhaps be more sophisticated about this in future... But also need to know the time of the initial request. Bugger.
             #Perhaps can focus efforts elsewhere in this regard...
             final_list.append(bothlist[i])
    return final_list

def find_first_splits(request_info, station_checks):
    nchecks_init = request_info.get("nchecks_init", 20)
    allchecks = station_checks[:nchecks_init]
    nrequests_max = 10  #This should be lower now as there can potentially be lots of threading within threading at this point. Maybe set to 10? Would be nice to get updates on this.
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
            input_parameters_first["destination"] = station

            input_parameters_second = request_info.copy()   #All timing stuff is the same to begin with.
            input_parameters_second["origin"] = station

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
                splits.append({
                    'origin':j1['origin'], 'destination': j2['destination'], 
                    'dep_time':j1['dep_time'], 'arr_time':j2['arr_time'],
                    'price':j1['price'] + j2['price'],
                    'split_stations':[j1["destination"]],
                    'split_arrs':[j1["arr_time"]], 'split_deps':[j2["dep_time"]]
                })
        if j1["origin"] == request_info["origin"] and j1["destination"] == request_info["destination"]:
                splits.append({
                    'origin':j1['origin'], 'destination': j1['destination'], 
                    'dep_time':j1['dep_time'], 'arr_time':j1['arr_time'],
                    'price':j1['price'],
                    'split_stations':[],
                    'split_arrs':[], 'split_deps':[]
                })
     #Add on direct journeys? Would be better to do that initially in the multithreading...      
    return splits

def filter_splits(request_info, unfiltered_splits):
    #Uses the price matrix approach to filter the splits. Current going to base it on departure time and journey length. Resolution will depend on how long such things take...
    #Actually, this is silly. Let's determine bounds first. Or could just do that based on the request? Yes!
    x_res = 5/60; y_res  = 5/60
    time_spread = request_info.get("time_spread",10)/60   #Spread times by these in each direction (resolution of not caring)
    t0 = request_info['start_time']
    t1 = request_info['end_time']
    #jtime = abs(t1 - t0).total_seconds()/3600   #Number of hours
    minx = t0.hour + t0.minute/60 - x_res; maxx = t1.hour + t1.minute/60 + x_res
    miny = 0; maxy = maxx-minx + y_res
    nbins_x = int((maxx - minx)/x_res); nbins_y = int((maxy - miny)/y_res)
    xs = np.linspace(minx, maxx, nbins_x + 1); ys = np.linspace(miny, maxy, nbins_y + 1)
    x_res = xs[1] - xs[0]; y_res = ys[1] - ys[0]
    price_matrix = 1e6*np.ones((len(xs), len(ys)))   #Set as unattainably high to begin with, and reduce if necessary
    spread_bins = int(time_spread/x_res)

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
            price_matrix = np.minimum(price_matrix, local_matrix)
            local_matrix[:,:] = 1e6

    price_matrix[price_matrix > 1e5] = maxprice

    if False:
        plt.xticks(range(0,24))
        plt.yticks(range(0,24))
        plt.pcolormesh(xs, ys, price_matrix.T)
        plt.colorbar()
        plt.savefig('plots/plot2.png')
        plt.close()

    #Actually filter the splits based upon this matrix.
    filtered_splits = []
    max_extra_time = request_info.get("max_extra_time", 125)
    time_limit = mintime + max_extra_time/60
    for split in unfiltered_splits:
        
        t0 = dt.strptime(split["dep_time"], "%H%M")
        t1 = dt.strptime(split["arr_time"], "%H%M")
        jtime = abs(t1 - t0).total_seconds()/3600   #Number of minutes
        #Check if this split is an optimal one (so far!), and if so update the matrix for it.
        xbin = np.digitize(t0.hour  + t0.minute/60, xs) - 1
        ybin = np.digitize(jtime, ys) - 1
        if split["price"] <= price_matrix[xbin,ybin] and jtime < time_limit:
            #Update the price matrix here. Don't want loops but might have to have them... Bugger.
            filtered_splits.append(split)

    filtered_splits = sorted(filtered_splits, key=lambda journey: int(journey['arr_time']))
    filtered_splits = sorted(filtered_splits, key=lambda journey: int(journey['dep_time']))

    return filtered_splits