import log
import requests
from bs4 import BeautifulSoup
from types import SimpleNamespace


def search_movie_by_name(name):
    headers = {
        "Host": "www.adultdvdempire.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.adultdvdempire.com",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "TE": "trailers"
    }
    
    #movie search
    endpoint = f'https://www.adultdvdempire.com/allsearch/search?exactMatch={name}&q={name}&fq=media_id%3a2'
    
    r = requests.get(endpoint, headers=headers)
    log.debug(f'[{r.status_code}] GET: {endpoint}')

    if r.status_code > 399:
        return None

    soup = BeautifulSoup(r.text, 'html.parser')
    
    hits = soup.find_all( "div", {"class": "product-card"})

    hits_meta = []

    for hit in hits:
        hit_meta = SimpleNamespace()

        boxcover = hit.find("a", {"class": "boxcover"})
        
        
        hit_meta.title = boxcover.img['title']
        hit_meta.url = f"https://www.adultdvdempire.com{boxcover['href'].strip()}"
        hit_meta.image = boxcover.img['src']

        hits_meta.append(hit_meta)

    return hits_meta
