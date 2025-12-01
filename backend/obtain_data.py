from datetime import datetime as dt, timedelta
import datetime
import time
import requests
from lxml import html
import threading
import json
from geopy.distance import geodesic
import numpy as np
import os, sys
from pathlib import Path
import asyncio 
import aiohttp
import random
from bs4 import BeautifulSoup
#This is for obtaining the data


def station_inout(stations, date):
    """
    Using brtimes.org (which seems quite a lovely website to scrape), gives the minimum connection time and a list of trains departing that day
    May be easier to use their api, but should be OK as long as I integrate it with the multiprocessing stuff
    """"2025-10-27"
    date_formatted = date.strftime("%Y-%m-%d")

    def makeurl_rtt(station, date):

        """
        Generates the url used to scrape from brtimes
        """
        s1 = "https://www.realtimetrains.co.uk/search/detailed/gb-nr:"
        s2 = "/"
        s3 = "/0000-2359?stp=WVS&show=pax-calls&order=wtt"
        return s1 + station + s2 + date + s3

    async def fetch(sem, session, url):
        async with sem:
            async with session.get(url, timeout = 120.0) as response: #This can get stuck. Not sure how to fix that yet but the internet will know.
                return await response.text()

    async def scrape_new(urls):
        sem = asyncio.Semaphore(1)
        connector = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(connector = connector) as session:
            tasks = [fetch(sem, session, url) for url in urls]
            pages = await asyncio.gather(*tasks)
        return pages

    urls = []
    for station in stations:
        urls.append(makeurl_rtt(station, date_formatted))

    try:
        pages = asyncio.run(scrape_new(urls))
    except:
        print('Scraping has failed with URLS:', urls)
        pages = []

    inouts = {}
    for pi, page in enumerate(pages):
        station = stations[pi]
        soup = BeautifulSoup(page, "html.parser")
        # find all planned GBTT times (arrival or departure)
        services = soup.select("a.service")
        pairs = []
        for si, service in enumerate(services):
            if service.select_one("div.time.plan.a.gbtt") is not None and service.select_one("div.time.plan.d.gbtt") is not None:
                pairs.append([float(service.select_one("div.time.plan.a.gbtt").text.strip()), float(service.select_one("div.time.plan.d.gbtt").text.strip())])
        inouts[station] = pairs
    
    return inouts

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

    #print('Nesting', input_parameters["nesting_degree"])
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]

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

    multithread_cadence = 60  #Cadence in minutes for the remaining hours of the day. This will need playing with a bit to optimise I imagine. 60 minutes seems fine.
    #Establish the required start times here
    if start_only or end_only:  #Partial searches
        start_times = [t_start]; end_times = [t_end]
    else:  #Full search
        go = True
        start_times = []; end_times = []
        journeys = []
        start_time = overall_start_time
        while go:
            start_times.append(start_time)
            start_time =  (dt.combine(date_search, start_time) + timedelta(minutes=multithread_cadence)).time()
            if start_time > t_end:
                go = False
            if len(start_times) > 1:
                if start_time < start_times[-1]:
                    go = False

    if len(start_times) > 1:
        for si, local_start in enumerate(start_times):
            if si == len(start_times) - 1 or end_only:
                local_end = t_end
            else:
                local_end = start_times[si + 1]
            end_times.append(local_end)
    else:
        end_times.append(t_end)

    async def fetch(sem, session, url):
        await asyncio.sleep(random.uniform(0.1, 1.0))
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
        success = False; ntries = 0
        while not success and ntries < 5:
            async with sem:
                async with session.get(url, headers=headers, timeout = 60.0) as response:
                    text = await response.text()
                    if len(text) > 200000:  #This has been redirected for some reason
                        ntries += 1
                    else:
                        success = True
                        return text
            await asyncio.sleep(1.0)
        return text
    async def scrape_new(urls):
        sem = asyncio.Semaphore(20)
        connector = aiohttp.TCPConnector(limit=20)
        async with aiohttp.ClientSession(connector = connector) as session:
            tasks = [fetch(sem, session, url) for url in urls]
            pages = await asyncio.gather(*tasks)
        return pages

    go = True
    startcount = 0
    stop_flags = np.zeros(len(start_times))   #Set to 1 once an individual has got too far.

    while go:
        #The main loop for generating urls. Hopefully not that long.
        urls = []
        for ri in range(len(start_times)):
            
            if end_only:
                url = makeurl_nr(origin, destination, date_search, end_times[ri], arr_flag = True)
            else:
                url = makeurl_nr(origin, destination, date_search, start_times[ri], arr_flag = False)

            urls.append(url)

        start_times_current = start_times.copy()
        start_times = []  #Need to reset and do this each time
        #New bit of code to stop asyncio getting confused.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            pages = loop.run_until_complete(scrape_new(urls))
        except:
            print('Scraping has failed with URLS:', urls)
        loop.close()
        pi = 0
        success = True
        for pi, page in enumerate(pages):
            page = pages[pi]
            local_end = end_times[pi]
            tree = html.fromstring(page)
            if len(page) == 118:
                #print('National rail have cottoned on to at least one of these pages... Waiting for a bit and trying again.')
                time.sleep(60.0 + 10.*random.uniform(0,1))
                success = False
                start_times = start_times_current.copy()
                break #Don't carry on with these pages, try again with the same data

            else:
                #Don't need to back off, just go for it as is.'
                wait_time = 120.0
                dep = tree.xpath('//div[@class="dep"]/text()')
                arr = tree.xpath('//div[@class="arr"]/text()')
                if len(dep) == 0:
                    with open("testpage.html", "w") as file:
                        file.write(page)    
                price = tree.xpath('//label[@class="opsingle"]/text()')
                zerochanges = tree.xpath('//div[@class="chg"]/text()')

                nonzerochanges = tree.xpath('//div[@class="chg"]//a[@class="changestip-link"]/text()')

                change_deps = tree.xpath('//table[@class="innertable"]//tr/td[2]/text()')
                change_arrs = tree.xpath('//table[@class="innertable"]//tr/td[5]/text()')
                change_dep_stats = tree.xpath('//table[@class="innertable"]//tr/td[@class="origin"]/abbr/text()')

                nchangetrains = 0
                nchanges = []
                i0 = 0; i1 = 0   #Those which have a link occupy two items in this, which will map to a single item in the second list
                for i in range(len(dep)): #This length is at least reliable.
                    if zerochanges[i0][0].isnumeric():   #No changes -- carry on
                        nchanges.append(0)
                        i0 += 1
                    else:  #Is at least one change here. Need to obtain some information as a result.
                        nchanges.append(int(nonzerochanges[i1][0]))
                        i0 += 2
                        i1 += 1 
                        nchangetrains += 1
                #Check change information matches the required amount -- otherwise might end up with some very strange things
                if len(change_deps) - nchangetrains != np.sum(nchanges):

                    print(nchanges, change_dep_stats)
                    print(len(change_deps) - nchangetrains, np.sum(nchanges))

                    raise Exception('Change info has gone wrong, url is', url)


                if stop_flags[pi] == 0:  #Don't bother if it's already there...
                    if len(dep) > 0 and len(price) == len(dep)*2:
                        #Check the number of priaces matches the number of departures/arrivals
                        maxdep = dt.strptime("00:01", "%H:%M").time()
                        maxarr = dt.strptime("00:01", "%H:%M").time()
                        for i in range(len(dep)):

                            dep1 = dt.strptime(dep[i].strip(), "%H:%M").time()
                            arr1 = dt.strptime(arr[i].strip(), "%H:%M").time()
                            maxdep = max(maxdep, dep1)  #This seems fine!
                            maxarr = max(maxarr, arr1)

                            if nchanges[i] > 0:  #There are changes, so need to figure out the change times
                                cdeps = []; cstats = []; carrs = []
                                start_index = int(np.sum(nchanges[:i]) + np.count_nonzero(nchanges[:i]))  #Number of changes before this. 
                                #Keep in mind the first of each set of changes is duplicated
                                for change_index in range(start_index, start_index + int(nchanges[i]) + 1):
                                    cdeps.append(dt.strptime(change_deps[change_index].strip(), "%H:%M").time().strftime("%H%M"))
                                    carrs.append(dt.strptime(change_arrs[change_index].strip(), "%H:%M").time().strftime("%H%M"))
                                    cstats.append(change_dep_stats[change_index])
                            #Sometimes no fares are available for various reasons. Just don't list these. 
                            #This appears to be becoming more frequent for reasons I don't understand.
                            if len(price[i*2+1].strip()) == 0:
                                pass
                            else:
                                p1 = float(price[i*2 + 1].strip()[1:])
                                doappend = False
                                if not start_only and not end_only:
                                    if dep1 >= start_times_current[pi] and arr1 <= t_end and arr1 > dep1 and arr1 > start_times_current[pi] and dep1 <= t_end:
                                        doappend = True
                                else:
                                    doappend = True
                                if doappend:
                                    if nchanges[i] == 0:  #No changes
                                        journeys.append({"origin": origin, "destination": destination, "dep_time": dep1.strftime("%H%M"), "arr_time": arr1.strftime("%H%M"), "price": p1, 'split_stations':[], 'split_arrs':[], 'split_deps':[],'split_prices':[p1], 'nchanges': nchanges[i], 'change_stations':[], 'change_arrs':[], 'change_deps':[]})
                                    else:
                                        journeys.append({"origin": origin, "destination": destination, "dep_time": dep1.strftime("%H%M"), "arr_time": arr1.strftime("%H%M"), "price": p1, 'split_stations':[], 'split_arrs':[], 'split_deps':[],'split_prices':[p1], 'nchanges': nchanges[i], 'change_stations':cstats[1:], 'change_arrs':carrs[:-1], 'change_deps':cdeps[1:]})
                        #Check for reasons to stop -- if search has gone into tomorrow or exceeded the local end
                        proceed = True  #Proceed unless there's reason not to...
                        if arr1 < overall_start_time or dep1 > local_end or maxarr > t_end:
                            proceed = False

                        #Also check for 'lapping' -- going to the next day at any point. Don't allow these...
                        if arr1 < dep1:
                            proceed = False

                        if proceed:
                            page_start_time = (dt.combine(date_search, maxdep) + timedelta(minutes=0)).time()
                            start_times.append(page_start_time)
                        else:
                            stop_flags[pi] = 1.
                            start_times.append(start_times_current[pi])

                    else:
                        stop_flags[pi] = 1.
                        start_times.append(start_times_current[pi])

                if start_only or end_only:
                    go = False
                if np.min(stop_flags) > 0.0:
                    go = False

        if success:
            startcount += 1

        if startcount > 20:  #Something has gone terribly wrong... Abort. Can happen too if stations are actually in the same place.
            go = False

    #print('Waves of requests:', startcount)
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

def find_stations(request_info):

    origin = request_info['origin']
    destination = request_info['destination']
    filename = "./station_data/%s_%s.json" % (origin, destination)
    ignore_previous = request_info.get("ignore_previous",False)
    #Create folder if necessary
    Path("station_data").mkdir(parents=True, exist_ok=True)
    #Initially check if a file for this combination already exists, and if so use that
    if os.path.exists(filename) and not ignore_previous:
        try:
            with open(filename) as f:
                station_data = json.load(f)
            return station_data
        except:
            print('File is corrupted or something. Ignoring it and running the search again...')

    #This should be roughly similar for the same pair of stations each time, so can probably be cached or equivalent. It's certainly quite slow :(

    max_deviation = request_info.get("max_deviation",0.5)   #How far off the route to go. Some can really get quite improbable so it's worth setting this quite high...
    all_station_data = json.loads(open('./backend/station_info.json').read())
    station_data = {}; station_list = []
    x0 = (all_station_data[origin]['latitude'], all_station_data[origin]['longitude']); x2 = (all_station_data[destination]['latitude'], all_station_data[destination]['longitude'])
    dref = geodesic(x0, x2).miles
    for station in all_station_data:
        add_station = True   #Only add this to the final list if it satisfies various requirements
        x1 = (all_station_data[station]['latitude'], all_station_data[station]['longitude'])
        d0 = geodesic(x0, x1).miles; d1 = geodesic(x1, x2).miles
        all_station_data[station]["deviation"] = (d0 + d1)/dref - 1.   #Extra distance to go via this station
        all_station_data[station]["progress"] = (dref**2 + d0**2 - d1**2)/(2*dref**2)  #Proportion of the progress to the destination station by visiting here. A bit nuanced I think as to what's best here.
        if all_station_data[station]["deviation"] > max_deviation:
            add_station = False
        if add_station:
            station_data[station] = all_station_data[station]
            station_list.append(station)
    print('Looking at', len(station_list), 'stations between',  request_info["origin"], 'and', request_info["destination"])

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/130.0",
    ]

    async def fetch(sem, session, url):
        await asyncio.sleep(random.uniform(0.1, 1.0))
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
        async with sem:
            async with session.get(url, headers=headers, timeout = 60.0) as response: #This can get stuck. Not sure how to fix that yet but the internet will know.
                return await response.text()

    async def scrape_new(urls):
        sem = asyncio.Semaphore(25)
        connector = aiohttp.TCPConnector(limit=25)
        async with aiohttp.ClientSession(connector = connector) as session:
            tasks = [fetch(sem, session, url) for url in urls]
            pages = await asyncio.gather(*tasks)
        return pages

    alljourneys = []
    #Separate this out into lumps. Should always be fine to do this one after another now, so can make 100 odd requests with impunity
    nrequests_max = 100

    nlumps = int(len(station_list)/(nrequests_max/2) + 1)
    nrequests_actual = len(station_list)/nlumps + 1
    modified_request_info = request_info.copy()
    realdate = request_info["date"]
    realdate = realdate + timedelta(days = 7)
    while realdate.weekday() >= 5:
        realdate += timedelta(days = 1)

    modified_request_info["date"] = realdate   #Look a week ahead of the actual request time. For reasons I'm deciding which are entirely arbitrary.
    modified_request_info["start_time"] = datetime.time(12,00)
    modified_request_info["end_time"] = datetime.time(23,59)

    dolumps = True; lump = 0
    alljourneys = []
    while dolumps:
        urls = []; origins = []; destinations = []
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

            #Make the urls here. Don't need much bloat really.
            url = makeurl_nr(origin, station, request_info["date"] + timedelta(days = 7) , datetime.time(12,00), arr_flag = False)
            urls.append(url); origins.append(origin); destinations.append(station)
            url = makeurl_nr(station, destination, request_info["date"] + timedelta(days = 7) , datetime.time(12,00), arr_flag = False)
            urls.append(url); origins.append(station); destinations.append(destination)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pages = loop.run_until_complete(scrape_new(urls))
        loop.close()

        #Pages for all the journeys. Doeesn't matter which order they arrive (lovely)
        alliswell = True
        for page in pages:
            if len(page) == 118:
                #print('National rail have cottoned on to at least one of these pages... Waiting for a couple of minutes.')
                alliswell = False

        if alliswell:
            print('%d percent of stations checked...' % (100*maxstat/len(station_list)))

            for pi, page in enumerate(pages):
                tree = html.fromstring(page)
                journeys = []
                dep = tree.xpath('//div[@class="dep"]/text()')
                arr = tree.xpath('//div[@class="arr"]/text()')
                price = tree.xpath('//label[@class="opsingle"]/text()')

                if len(dep) > 0 and len(price) == len(dep)*2:
                    #Check the number of priaces matches the number of departures/arrivals
                    maxdep = dt.strptime("00:01", "%H:%M").time()
                    maxarr = dt.strptime("00:01", "%H:%M").time()
                    for i in range(len(dep)):
                        dep1 = dt.strptime(dep[i].strip(), "%H:%M").time()
                        arr1 = dt.strptime(arr[i].strip(), "%H:%M").time()
                        maxdep = max(maxdep, dep1)  #This seems fine!
                        maxarr = max(maxarr, arr1)
                        #Sometimes no fares are available for various reasons. Just don't list these
                        if len(price[i*2+1].strip()) == 0:
                            pass
                        else:
                            p1 = float(price[i*2 + 1].strip()[1:])
                            journeys.append({"origin": origins[pi], "destination": destinations[pi], "dep_time": dep1.strftime("%H%M"), "arr_time": arr1.strftime("%H%M"), "price": p1,      'split_stations':[], 'split_arrs':[], 'split_deps':[],'split_prices':[p1]})
                alljourneys.append(journeys)
            lump += 1

        else:
            #Back off and let national rail recover...
            time.sleep(60.0 + 10.*random.uniform(0,1))

        #If all is well, figure out journey times etc. at this point from the raw html

        if lump >= nlumps:
            dolumps = False

    reftime = 0
    for journeys in alljourneys:
        if len(journeys) > 0:
            mintime = 1e6; minprice = 1e6; maxtime = 0.
            for journey in journeys:
                t0 = dt.strptime(journey["dep_time"], "%H%M")
                t1 = dt.strptime(journey["arr_time"], "%H%M")
                mintime = min(mintime, abs(t1 - t0).total_seconds()/60)
                maxtime = max(maxtime, abs(t1 - t0).total_seconds()/60)
                minprice = min(minprice, journey["price"])
            if journey['origin'] == origin:  #This is the first split
                station_data[journey['destination']]['time1'] = mintime
                station_data[journey['destination']]['price1'] = minprice
            else:
                station_data[journey['origin']]['time2'] = mintime
                station_data[journey['origin']]['price2'] = minprice
            if journey['origin'] == origin and journey['destination'] == destination:
                station_data[journey['origin']]['time1'] = mintime
                station_data[journey['origin']]['price1'] = minprice
                reftime = max(reftime, maxtime)
            #Set the reference time if it is both. This is a bit ugly but can't really be helped

    #Use this data to determine the final station data (filter out impossible ones and things, and give some kind of scores. Time score plus price score (both to be minimised?)
    final_station_data = {}
    for station in station_data:
        if 'time1' in station_data[station] and 'time2' in station_data[station] and abs(station_data[station]['progress'] - 1.0) > 1e-6:
            #This appears to be a valid option
            time_score = station_data[station]['time1'] + station_data[station]['time2'] - reftime
            price1 = np.abs(station_data[station]['price1']/station_data[station]['progress'])
            price2 = np.abs(station_data[station]['price2']/(1.0 - station_data[station]['progress']))
            price_score = min(price1, price2)
            final_station_data[station] = {"time_score":time_score, "price_score":price_score, "in_time":station_data[station]['time1'], "out_time":station_data[station]['time2'], "deviation":station_data[station]['deviation'], "progress":station_data[station]['progress']}
        elif station == destination and 'time1' in station_data[station]:
            #This is the whole journey (not the splits), which contains useful information so may as well put it in. Also useful for normalising the prices, which I'll do shortly.
            time_score = station_data[station]['time1'] - reftime
            price_score = np.abs(station_data[station]['price1'])
            final_station_data[station] = {"time_score":time_score, "price_score":price_score, "in_time":station_data[station]['time1'], "out_time":0.0,"deviation":station_data[station]['deviation'], "progress":station_data[station]['progress']}

    with open(filename, "w") as f:
        json.dump(final_station_data, f)
    #We're using alljourneys here ONLY to rank the stations with rough prices, and don't actually care about whether these journeys are doable. That comes later. So for now this is probably fine to be as-is.
    #It might be worth changing the parameters here to be a generic midday time or something? Actually, let's just do that. In a minute.
    print("Station data for this subroute found. Hopefully won't need to do that again")
    return final_station_data
