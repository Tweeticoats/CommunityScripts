import log
import requests
from bs4 import BeautifulSoup
from types import SimpleNamespace


def search_movie_by_name(name):
    headers = {
        "Host": "www.data18.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "http://www.data18.com",
        "Connection": "keep-alive",
        "Cookie": "c_user=US; welcome=1",
        "Upgrade-Insecure-Requests": "1"
    }
    
    #movie search
    endpoint = f'http://www.data18.com/search/?t=2&k={name}&b=1'
    
    r = requests.get(endpoint, headers=headers)
    log.debug(f'[{r.status_code}] GET: {endpoint}')

    if r.status_code > 399:
        return None

    soup = BeautifulSoup(r.text, 'html.parser')
    
    hits = soup.select('td > div[style*="float: left"]')
    hits_meta = []

    for hit in hits:

        hit_meta = SimpleNamespace()
        
        hit_meta.title = hit.img['title']
        hit_meta.url = f"{hit.a['href'].strip()}"
        hit_meta.image = hit.img['src']
        hit_meta.date = hit.contents[0]

        hits_meta.append(hit_meta)

    return hits_meta
