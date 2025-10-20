import asyncio 
import aiohttp
import random
import numpy as np

from lxml import html
from bs4 import BeautifulSoup

"""
Going to need RTT I think... Luckily I already have that code!
"""
def station_inout(station, date):
    """
    Using brtimes.org (which seems quite a lovely website to scrape), gives the minimum connection time and a list of trains departing that day
    May be easier to use their api, but should be OK as long as I integrate it with the multiprocessing stuff
    """
    
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
            async with session.get(url, timeout = 5.0) as response: #This can get stuck. Not sure how to fix that yet but the internet will know.
                return await response.text()

    async def scrape_new(urls):
        sem = asyncio.Semaphore(1)
        connector = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(connector = connector) as session:
            tasks = [fetch(sem, session, url) for url in urls]
            pages = await asyncio.gather(*tasks)
        return pages

    urls = [makeurl_rtt("DHM", "2025-10-27")]
    pages = asyncio.run(scrape_new(urls))

    page1 = pages[0]

    soup = BeautifulSoup(page1, "html.parser")

    # find all planned GBTT times (arrival or departure)
    services = soup.select("a.service")
    pairs = []
    for si, service in enumerate(services):
        pairs.append([float(service.select_one("div.time.plan.a.gbtt").text.strip()), float(service.select_one("div.time.plan.d.gbtt").text.strip())])
    return np.array(pairs)

print(station_inout("LDS", "20251027"))