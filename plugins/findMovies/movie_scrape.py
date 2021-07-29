from types import SimpleNamespace
from difflib import SequenceMatcher
import re, sys, copy, json

import log
from stash_interface import StashInterface

import adultdvdempire
import data18
import hotmovies

CONTROL_TAG = "find_movie_match"
PATH_TEMPLATE = '<moviefolder>\\<scenefolder>\\<file>.mp4'

def main():
    json_input = json.loads(sys.stdin.read())

    output = {}
    run(json_input, output)

    out = json.dumps(output)
    print(out + "\n")

def run(json_input, output):
    mode_arg = json_input['args']['mode']
    
    try:
        client = StashInterface(json_input["server_connection"])
        
        control_tag_id = find_or_create_tag(client)
        
        if mode_arg == "movie_search":
            log.info('Running Movie Search...')
            movie_search(client, control_tag_id)

    except Exception:
        raise

    log.info("done")

    output["output"] = "ok"

def find_or_create_tag(client):
    global control_tag_id

    control_tag_id = client.find_tagid_from_name(CONTROL_TAG)
    
    if not control_tag_id:
        log.info('control tag not found creating tag')
        control_tag_id = client.create_tag({'name': CONTROL_TAG})
        #return ok
        print(json.dumps({"output":"ok"}) + "\n")

    return control_tag_id

def movie_search(client, control_tag_id):

    scenes = []

    try:
        scenes = client.find_scenes(f={
            "is_missing": "movie",
            "tags": {
                "value": [control_tag_id],
                "modifier": "INCLUDES"
            }
        })
    except Exception as e:
        log.error('Could not "find_scenes"')
        log.error(json.dumps(control_tag_id))
        log.error(str(e))


    total = len(scenes)

    log.info(f'found {total} with tag "{CONTROL_TAG}" missing movie')
        
    for i, scene in enumerate(scenes):
        log.progress(i/total)

        dirname = extract_dirname(scene["path"], '<moviefolder>')
    
        d = parse_dirname(dirname)
        movie_path = extract_parent_path(scene["path"], '<moviefolder>')

        if not d:
            continue

        hits = adultdvdempire.search_movie_by_name(d.query)
        match = match_results(d, hits)

        if not match:
            continue
        
        movie_data = {
            'name':match.title,
            'url':match.url,
            'director': movie_path
        }

        stash_movie = client.find_movie(movie_data)
        if stash_movie:
            movie_id = stash_movie['id']
            movie_data['id'] = movie_id
            client.update_movie(movie_data)
            log.info(f'set url for movie {movie_id}')
        else:
            movie_id = client.create_movie(movie_data)
            log.info(f'created new movie {match.title}')

        if not movie_id:
            continue

        scene_update_input = {
            'id':scene['id'],
            'movies': [ {'movie_id':movie_id, 'scene_index':None} ]
        }

        # Update scene
        try:
            client.update_scene_overwrite(scene_update_input)
        except Exception as e:
            log.error('Error updating scene')
            log.error(json.dumps(scene_update_input))
            log.error(str(e))


def extract_parent_path(path, target):
    ex_list = PATH_TEMPLATE.split('\\')
    ex_list.reverse()
    movie_fldr_idx = (ex_list.index(target))
    return '\\'.join(path.split('\\')[:-movie_fldr_idx])

def extract_dirname(path, target):
    ex_list = PATH_TEMPLATE.split('\\')
    ex_list.reverse()
    movie_fldr_idx = (ex_list.index(target)+1)
    return path.split('\\')[-movie_fldr_idx]

def match_results(parse_data, hits):

    subset = []
    misses = []
    for hit in hits:

        h = parse_dirname(hit.title)
        if not h:
            log.debug(f'skipping {hit.title}')
            continue
        
        # remove reserved path characters before matching
        h.query = re.sub(r'[<>:"\/\\\|\?\*]','', h.query)

        if parse_data.query in h.query:
            subset.append(hit)

        if parse_data.series_number:

            if parse_data.series_number not in hit.title:
                continue

            diff = SequenceMatcher(None, parse_data.query, h.query).ratio()
            if diff < 0.92:
                misses.append({'miss':hit.title, 'diff':diff})
                continue

        else:
            diff = SequenceMatcher(None, parse_data.query, h.query).ratio()
            if diff < 0.96:
                misses.append({'miss':hit.title, 'diff':diff})
                continue
        
        return hit

    if len(subset) == 1:
        return subset[0]

    misses.sort(key=lambda x: x['diff'], reverse=True)

    log.debug( f'Search: {parse_data.query}')
    for miss in misses[:5]:
        log.debug('Miss: ({:.2f}) {}'.format(miss["diff"], miss["miss"]))

def parse_dirname(str_in):
    str_in = re.sub(r'\n', '', str_in)

    data = SimpleNamespace()
    data.RAW = copy.deepcopy(str_in)
    
    data.name = str_in

    # convert dot/underscore to space
    data.name = re.sub(r'[\._]', ' ', data.name)

    # remove duplacate spaces
    data.name = re.sub(r' +', ' ', data.name)

    # match resolution
    rez_pattern = r'[\[\(]?((?:480|540|720|1080|2160)[pP])[\)\]]?'
    rez_match = re.search(rez_pattern, data.name)
    if rez_match:
        data.resolution = rez_match.group(1)
        data.name = data.name[:rez_match.start()]
    else:
        data.resolution = None

    #break on format
    m = re.search('( xxx |dvdr(?:ip)?|web-dl|bluray)', data.name, re.IGNORECASE)
    if m:
        data.misc = data.name[m.start():]
        data.name = data.name[:m.start()]

    #detect series #
    data.series_number = None
    m = re.search(r'(?: |#)0*(\d{1,3})(?: |$)', data.name)
    if m:
        data.series_number = m.group(1)
        data.name = data.name[:m.start()]

    # replace misc
    data.name = re.sub(r'\((AI|eu)\)', '', data.name)
    data.name = re.sub(r'\[(English)\]', '', data.name)

    # remove leading and trailing "The"
    data.name = re.sub(r'(^[Tt]he|[Tt]he$)', '', data.name)
    
    # remove leading and trailing "A"
    data.name = re.sub(r'(^A|A$)', '', data.name)

    data.name = data.name.strip(' -')


    if data.series_number:
        data.query = f'{data.name} {data.series_number}'
    else:
        data.query = data.name

    if len(data.query) < 8:
        return None

    return data


main()