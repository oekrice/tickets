from datetime import datetime as dt, timedelta
import datetime
import time
import requests
from lxml import html
import threading

#This is for obtaining the data

def makeurl_nr(origin, destination, date_search, page_start_time):
    s1 = "https://ojp.nationalrail.co.uk/service/timesandfares/"
    s2 = "/"
    s3 = "dep"

    return s1 + origin + s2 + destination + s2 +  date_search.strftime("%d%m%y") + s2 + page_start_time.strftime("%H%M") + s2 + s3

def find_basic_info(input_parameters):
    '''
    This function will take the input parameters and scrape the national rail website for the required information.
    Currently only contains start and end, and I'll need to do something with the dates to make them nice
    '''
    journeys = []   #to be appended to, eventually
    print('Finding info in the function')
    date_search = input_parameters.get("date",dt.today())
    t_start = input_parameters.get("start_time",dt.now().time())
    t_end = input_parameters.get("end_time",datetime.time(23,59))
    origin = input_parameters["origin"]
    destination = input_parameters["destination"]
    overall_start_time = t_start

    multithread_cadence = 60  #Cadence in minutes for the remaining hours of the day. This will need playing with a bit to optimise I imagine.

    #Establish the required start times here
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

            url = makeurl_nr(origin, destination, date_search, page_start_time)
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
                        if dep1 >= local_start and arr1 <= t_end and arr1 > dep1 and arr1 > page_start_time and dep1 <= local_end:
                            journeys.append({"origin": origin, "destination": destination, "dep_time": dep1.strftime("%H%M"), "arr_time": arr1.strftime("%H%M"), "price": p1})
                            #journeys.append([float(dep1), float(arr1), float(p1)])
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

    journeys = []
    threads = []
    for si, local_start in enumerate(start_times):
        if si == len(start_times) - 1:
            local_end = t_end
        else:
            local_end = start_times[si + 1]

        x = threading.Thread(target=append_to_journeys, args=(local_start, local_end, journeys), daemon = False)
        threads.append(x)
        x.start()
    for j, x in enumerate(threads):
        x.join()

    #Sort and filter the journeys
    print('Found', len(journeys))

    unique_journeys = []; seen = set()
    for journey in journeys:
        # Create a tuple representing the unique identity of each entry
        key = (journey['origin'], journey['destination'], journey['dep_time'], journey['arr_time'], journey['price'])
        if key not in seen:
            seen.add(key)
            unique_journeys.append(journey)
    unique_journeys = sorted(unique_journeys, key=lambda journey: int(journey['dep_time']))

    print('After filtering', len(unique_journeys))
    return unique_journeys
