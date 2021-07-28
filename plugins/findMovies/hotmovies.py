import log
import requests
from types import SimpleNamespace


def search_movie_by_name(name):
    headers = {
        "Host": "www.hotmovies.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.hotmovies.com",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Cache-Control": "max-age=0",
        "TE": "trailers"
    }
    
    #movie search
    endpoint = f'https://www.hotmovies.com/search_suggestions.php?term={name}'
    
    r = requests.get(endpoint, headers=headers)
    log.debug(f'[{r.status_code}] GET: {endpoint}')

    if r.status_code > 399:
        return None

    hits = r.json()
    hits_meta = []
    for hit in hits:
        hit_meta = SimpleNamespace()
        
        hit_meta.title = hit['value']
        hit_meta.url = hit['surl']
        hit_meta.image = None

        hits_meta.append(hit_meta)

    return hits_meta
