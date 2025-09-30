from datetime import datetime as dt, timedelta
import datetime
import time
import requests
from lxml import html
import threading
import json
import geopy
import numpy as np
#This is for obtaining the data

def makeurl_nr(origin, destination, date_search, page_start_time, arr_flag = False):
    s1 = "https://ojp.nationalrail.co.uk/service/timesandfares/"
    s2 = "/"
    if arr_flag:
        s3 = "arr"
    else:
        s3 = "dep"
    return s1 + origin + s2 + destination + s2 +  date_search.strftime("%d%m%y") + s2 + page_start_time.strftime("%H%M") + s2 + s3

def find_basic_info(input_parameters, alljourneys = []):
    '''
    This function will take the input parameters and scrape the national rail website for the required information.
    Currently only contains start and end, and I'll need to do something with the dates to make them nice
    '''
    journeys = []   #to be appended to, eventually
    date_search = input_parameters.get("date",dt.today())
    t_start = input_parameters.get("start_time",dt.now().time())
    t_end = input_parameters.get("end_time",datetime.time(23,59))
    origin = input_parameters["origin"]
    destination = input_parameters["destination"]
    start_only = input_parameters.get("start_only", False)   #Flags to only obtain a partial request (used to establish the stations which are worth a full request later on)
    end_only = input_parameters.get("end_only", False)
    
    if start_only:
        end_only = False  #Don't let them both be true. Could cause trouble.

    overall_start_time = t_start

    multithread_cadence = 60  #Cadence in minutes for the remaining hours of the day. This will need playing with a bit to optimise I imagine.

    #Establish the required start times here
    if start_only or end_only:  #Partial searches
        start_times = [t_start]
    else:  #Full search
        go = True
        start_times = []
        start_time = overall_start_time
        while go:
            start_times.append(start_time)
            start_time =  (dt.combine(date_search, start_time) + timedelta(minutes=multithread_cadence)).time()
            if start_time > t_end:
                go = False
            if len(start_times) > 1:
                if start_time < start_times[-1]:
                    go = False

    def append_to_journeys(local_start, local_end, journeys):
        go = True
        pagecount = 0
        page_start_time = local_start
        while go:   #cycling through pages as it only gives a few results at a time
            if origin == destination:
                return []

            if end_only:
                url = makeurl_nr(origin, destination, date_search, local_end, arr_flag = True)
            else:
                url = makeurl_nr(origin, destination, date_search, page_start_time, arr_flag = False)
            try:
                page = requests.get(url)
            except:
                print('Internet error, probably. Waiting and trying again...')
                go = True
                pagecount = 0
                time.sleep(10.0)
                continue

            tree = html.fromstring(page.content)

            if str(page) == "<Response [403]>":
                print('National rail have cottoned on. Waiting a bit and trying again...')
                go = True
                pagecount = 0
                time.sleep(10.0)
                continue

            dep = tree.xpath('//div[@class="dep"]/text()')
            arr = tree.xpath('//div[@class="arr"]/text()')
            price = tree.xpath('//label[@class="opsingle"]/text()')
            if page == '<Response [200]>':
                journeys = []

            if len(dep) > 0 and len(price) == len(dep)*2:
                #Check the number of priaces matches the number of departures/arrivals
                for i in range(len(dep)):
                    dep1 = dt.strptime(dep[i].strip(), "%H:%M").time()
                    arr1 = dt.strptime(arr[i].strip(), "%H:%M").time()
                    #Sometimes no fares are available for various reasons. Just don't list these
                    if len(price[i*2+1].strip()) == 0:
                        pass
                    else:
                        p1 = float(price[i*2 + 1].strip()[1:])
                        if not start_only and not end_only:
                            if dep1 >= local_start and arr1 <= t_end and arr1 > dep1 and arr1 > page_start_time and dep1 <= local_end:
                                journeys.append({"origin": origin, "destination": destination, "dep_time": dep1.strftime("%H%M"), "arr_time": arr1.strftime("%H%M"), "price": p1})
                        else:
                            journeys.append({"origin": origin, "destination": destination, "dep_time": dep1.strftime("%H%M"), "arr_time": arr1.strftime("%H%M"), "price": p1})
                    if arr1 < page_start_time:
                        go = False
                if arr1 < local_end and arr1 > t_start:
                    pagecount += 1
                    page_start_time = (dt.combine(date_search, dep1) + timedelta(minutes=1)).time()
                else:
                    go = False
            else:
                go = False
            if pagecount > 25:
                return []
            if start_only or end_only:
                go = False

    journeys = []
    threads = []
    if len(start_times) > 1:
        for si, local_start in enumerate(start_times):
            if si == len(start_times) - 1 or end_only:
                local_end = t_end
            else:
                local_end = start_times[si + 1]

            x = threading.Thread(target=append_to_journeys, args=(local_start, local_end, journeys), daemon = False)
            threads.append(x)
            x.start()
        for j, x in enumerate(threads):
            x.join()

    else:
        append_to_journeys(start_times[0], t_end, journeys)
    #Sort and filter the journeys

    unique_journeys = []; seen = set()
    for journey in journeys:
        # Create a tuple representing the unique identity of each entry
        key = (journey['origin'], journey['destination'], journey['dep_time'], journey['arr_time'], journey['price'])
        if key not in seen:
            seen.add(key)
            unique_journeys.append(journey)
    unique_journeys = sorted(unique_journeys, key=lambda journey: int(journey['dep_time']))

    alljourneys.append(unique_journeys)
    return unique_journeys

def find_station_info(request_info):

    #This should be roughly similar for the same pair of stations each time, so can probably be cached or equivalent. It's certainly quite slow :(

    max_deviation = request_info.get("max_deviation",0.2)   #How far off the route to go. Some can really get quite improbable so it's worth setting this quite high...
    
    origin = request_info['origin']
    destination = request_info['destination']
    all_station_data = json.loads(open('./station_info.json').read())
    station_data = {}; station_list = []
    x0 = (all_station_data[origin]['latitude'], all_station_data[origin]['longitude']); x2 = (all_station_data[destination]['latitude'], all_station_data[destination]['longitude'])
    dref = geopy.distance.distance(x0, x2).miles
    print('Loaded', len(all_station_data), 'stations initially')
    for station in all_station_data:
        add_station = True   #Only add this to the final list if it satisfies various requirements
        x1 = (all_station_data[station]['latitude'], all_station_data[station]['longitude'])
        d0 = geopy.distance.distance(x0, x1).miles; d1 = geopy.distance.distance(x1, x2).miles
        all_station_data[station]["deviation"] = (d0 + d1)/dref - 1.   #Extra distance to go via this station
        all_station_data[station]["progress"] = (dref**2 + d0**2 - d1**2)/(2*dref**2)  #Proportion of the progress to the destination station by visiting here. A bit nuanced I think as to what's best here.
        if all_station_data[station]["deviation"] > max_deviation:
            add_station = False
        if add_station:
            station_data[station] = all_station_data[station]
            station_list.append(station)
    print('Looking at', len(station_list), 'stations after geographical filtering. Now to look at timings and prices. This is more tricky.')

    alljourneys = []
    #Separate this out into lumps
    nrequests_max = 100
    nlumps = int(len(station_list)/(nrequests_max/2) + 1)
    nrequests_actual = len(station_list)/nlumps + 1
    modified_request_info = request_info.copy()
    modified_request_info["start_time"] = datetime.time(9,00)
    modified_request_info["end_time"] = datetime.time(23,59)
    for lump in range(nlumps):
        threads = []; lumpcount = 0
        minstat = int(nrequests_actual*lump); maxstat = int(min(nrequests_actual*(lump+1), len(station_list)))
        for station in station_list[minstat:maxstat]:  #Alas this bit needs some multithreading, as it's far too slow.
            lumpcount += 1
            #Let's do a basic search and see how long it takes. Do first section and second section separately. Hopefully not too long for a reasonably small list.
            input_parameters_first = modified_request_info.copy()   #All timing stuff is the same to begin with.
            input_parameters_first["destination"] = station
            input_parameters_first["start_only"] = True

            input_parameters_second = modified_request_info.copy()   #All timing stuff is the same to begin with.
            input_parameters_second["origin"] = station
            input_parameters_second["start_only"] = True

            x = threading.Thread(target=find_basic_info, args=(input_parameters_first, alljourneys), daemon = False)
            threads.append(x)
            x.start()

            x = threading.Thread(target=find_basic_info, args=(input_parameters_second, alljourneys), daemon = False)
            threads.append(x)
            x.start()

        for j, x in enumerate(threads):
            x.join()

    reftime = 1e6
    for journeys in alljourneys:
        if len(journeys) > 0:
            mintime = 1e6; minprice = 1e6
            for journey in journeys:
                t0 = dt.strptime(journey["dep_time"], "%H%M")
                t1 = dt.strptime(journey["arr_time"], "%H%M")
                mintime = min(mintime, abs(t1 - t0).total_seconds()/60)
                minprice = min(minprice, journey["price"])
            if journey['origin'] == origin:  #This is the first split
                station_data[journey['destination']]['time1'] = mintime
                station_data[journey['destination']]['price1'] = minprice
            else:
                station_data[journey['origin']]['time2'] = mintime
                station_data[journey['origin']]['price2'] = minprice
            if journey['origin'] == origin and journey['destination'] == destination:
                reftime = min(reftime, mintime)
            #Set the reference time if it is both. This is a bit ugly but can't really be helped

    #Use this data to determine the final station data (filter out impossible ones and things, and give some kind of scores. Time score plus price score (both to be minimised?)
    final_station_data = {}
    for station in station_data:
        #print(station_data[station])
        if 'time1' in station_data[station] and 'time2' in station_data[station]:
            #This appears to be a valid option
            time_score = station_data[station]['time1'] + station_data[station]['time2'] - reftime
            price1 = np.abs(station_data[station]['price1']/station_data[station]['progress'])
            price2 = np.abs(station_data[station]['price2']/(1.0 - station_data[station]['progress']))
            price_score = min(price1, price2)
            final_station_data[station] = {"time_score":time_score, "price_score":price_score}
            print(station, final_station_data[station])
    filename = "./station_data/%s_%s.json" % (origin, destination)
    with open(filename, "w") as f:
        json.dump(final_station_data, f)
    #We're using alljourneys here ONLY to rank the stations with rough prices, and don't actually care about whether these journeys are doable. That comes later. So for now this is probably fine to be as-is.
    #It might be worth changing the parameters here to be a generic midday time or something? Actually, let's just do that. In a minute.
    return
