#This is for obtaining the data


def find_basic_info(input_parameters):
    '''
    Finds the departure and arrival times between the two stations plus price and changes.
    Trains must arrive before end_time but this will not include every possible iteration,
    just those on the national rail website.
    Ouputs as a list, each entry is depart, arrive and price
    '''
    journeys = []   #to be appended to
    go = True
    pagecount = 0
    page_start = stats.timestring(start_time)
    while go:   #cycling through pages
        if start_station == end_station:
            return []
        url = stats.makeurl_nr(start_station, end_station, day, stats.timestring(page_start))
        try:
            page = requests.get(url)
            tree = html.fromstring(page.content)
        except:
            print('Internet error, probably. Waiting and trying again...')
            journeys = []   #to be appended to
            go = True
            pagecount = 0
            page_start = stats.timestring(start_time)
            time.sleep(10.0)
            continue 
        if str(page) == "<Response [403]>":
            #print('National rail have cottoned on. Waiting a bit and trying again...')
            journeys = []   #to be appended to
            go = True
            pagecount = 0
            page_start = stats.timestring(start_time)
            time.sleep(60.0)
            continue
        
        dep = tree.xpath('//div[@class="dep"]/text()')
        arr = tree.xpath('//div[@class="arr"]/text()')
        price = tree.xpath('//label[@class="opsingle"]/text()')    
        if page == '<Response [200]>':
            return []
        if len(dep) > 0 and len(price) == len(dep)*2:
            for i in range(len(dep)):
                dep1 = stats.totime(dep[i])
                #print(dep1)
                arr1 = stats.totime(arr[i])
                #Sometimes no fares are available for strange reasons (metros and things)
                if len(price[i*2+1].strip()) == 0:
                    pass
                else: 
                    p1 = stats.toprice(price[i*2+1])
                    if dep1 >= float(page_start) and arr1 <= float(end_time) and arr1 > dep1 and arr1 > float(page_start):
                        journeys.append([float(dep1), float(arr1), float(p1)]) 
                if arr1 < float(page_start):
                    go = False
            if arr1 < float(end_time) and arr1 > float(page_start):
                pagecount += 1
                #print(pagecount, start_station, end_station, dep1, page_start)
                
                if int(dep1%100) == 59:
                    if dep1 + 41 <= float(page_start):
                        go = False
                    page_start = dep1+41  
                else:
                    if dep1 + 1 <= float(page_start):
                        go = False
                    page_start = dep1 + 1
            else:
                go = False
        else:
            go = False
        if pagecount > 25:
            return []
            
    return journeys
