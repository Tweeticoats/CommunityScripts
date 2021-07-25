import requests
import sys
import log
import re

class StashInterface:
	port = ""
	url = ""
	headers = {
		"Accept-Encoding": "gzip, deflate, br",
		"Content-Type": "application/json",
		"Accept": "application/json",
		"Connection": "keep-alive",
		"DNT": "1"
	}
	cookies = {}

	def __init__(self, conn, fragments={}):
		self.port = conn['Port']
		scheme = conn['Scheme']

		# Session cookie for authentication
		self.cookies = {
			'session': conn.get('SessionCookie').get('Value')
		}

		domain = conn.get('Domain') if conn.get('Domain') else 'localhost'

		# Stash GraphQL endpoint
		self.url = scheme + "://" + domain + ":" + str(self.port) + "/graphql"
		log.debug(f"Using stash GraphQl endpoint at {self.url}")

		self.fragments = fragments
		self.fragments.update(stash_gql_fragments)

	def __resolveFragments(self, query):

		fragmentRefrences = list(set(re.findall(r'(?<=\.\.\.)\w+', query)))
		fragments = []
		for ref in fragmentRefrences:
			fragments.append({
				"fragment": ref,
				"defined": bool(re.search("fragment {}".format(ref), query))
			})

		if all([f["defined"] for f in fragments]):
			return query
		else:
			for fragment in [f["fragment"] for f in fragments if not f["defined"]]:
				if fragment not in self.fragments:
					raise Exception(f'GraphQL error: fragment "{fragment}" not defined')
				query += self.fragments[fragment]
			return self.__resolveFragments(query)

	def __callGraphQL(self, query, variables=None):

		query = self.__resolveFragments(query)

		json = {'query': query}
		if variables is not None:
			json['variables'] = variables

		response = requests.post(self.url, json=json, headers=self.headers, cookies=self.cookies)

		if response.status_code == 200:
			result = response.json()
			if result.get("error", None):
				for error in result["error"]["errors"]:
					raise Exception("GraphQL error: {}".format(error))
			if result.get("data", None):
				return result.get("data")
		elif response.status_code == 401:
			sys.exit("HTTP Error 401, Unauthorised. Cookie authentication most likely failed")
		else:
			raise ConnectionError(
				"GraphQL query failed:{} - {}. Query: {}. Variables: {}".format(
					response.status_code, response.content, query, variables)
			)

	def scan_for_new_files(self):
		try:
			query = """
					mutation {
						metadataScan (
							input: {
								useFileMetadata: true 
								scanGenerateSprites: false
								scanGeneratePreviews: false
								scanGenerateImagePreviews: false
								stripFileExtension: false
							}
						) 
					}
			"""
			result = self.__callGraphQL(query)
		except ConnectionError:
			query = """
					mutation {
						metadataScan (
							input: {
								useFileMetadata: true
							}
						) 
					}
			"""
			result = self.__callGraphQL(query)
		log.debug("ScanResult" + str(result))

	def get_tag_id_from_name(self, name):
		for tag in self.find_tags(q=name):
			if tag["name"] == name:
				return tag["id"]
			if any(name == a for a in tag["aliases"] ):
				return tag["id"]
		return None

	def find_tags(self, q="", f={}):
		query = """
			query FindTags($filter: FindFilterType, $tag_filter: TagFilterType) {
				findTags(filter: $filter, tag_filter: $tag_filter) {
					count
					tags {
						id
						name
						aliases
					}
				}
			}
		"""

		variables = {
			"filter": {
				"direction": "ASC",
				"page": 1,
				"per_page": -1,
				"q": q,
				"sort": "name"
			},
			"tag_filter": f
		}
		
		result = self.__callGraphQL(query, variables)
		return result["findTags"]["tags"]

	def create_tag(self, tag):
		query = """
			mutation tagCreate($input:TagCreateInput!) {
				tagCreate(input: $input){
					id
				}
			}
		"""

		name = tag.get('name')
		if not name:
			return None

		variables = {'input': {
			'name': name
		}}

		result = self.__callGraphQL(query, variables)
		return result["tagCreate"]["id"]

	def destroy_tag(self, tag_id):
		query = """
			mutation tagDestroy($input: TagDestroyInput!) {
				tagDestroy(input: $input)
			}
		"""
		variables = {'input': {
			'id': tag_id
		}}

		self.__callGraphQL(query, variables)

	# This method will overwrite all provided data fields
	def update_scene_overwrite(self, scene_data):
		query = """
			mutation sceneUpdate($input:SceneUpdateInput!) {
				sceneUpdate(input: $input) {
					id
				}
			}
		"""
		variables = {'input': scene_data}

		result = self.__callGraphQL(query, variables)
		return result["sceneUpdate"]["id"]

	def find_scenes(self, filter={}):
		query = """
		query FindScenes($filter: FindFilterType, $scene_filter: SceneFilterType, $scene_ids: [Int!]) {
			findScenes(filter: $filter, scene_filter: $scene_filter, scene_ids: $scene_ids) {
				count
				scenes {
					...stashScene
				}
			}
		}
		"""
		variables = {
			"filter": { "per_page": -1 },
			"scene_filter": filter
		}
			
		result = self.__callGraphQL(query, variables)
		scenes = result.get('findScenes').get('scenes')

		return scenes

	def find_scenes_with_tags(self, tag_ids, modifier="INCLUDES_ALL"):
		scene_filter = {
			"tags": { "modifier": modifier, "value": tag_ids } 
		}
		return self.find_scenes(filter=scene_filter)


	def find_movie(self, movie):
		movies = self.find_movies(movie)
		for m in movies:
			if movie.get('name') and m.get('name') and movie['name'] == m['name']:
				return m

		return None
	
	def create_movie(self, movie_data):
		name = movie_data.get("name")
		query = """
			mutation($name: String!) {
				movieCreate(input: { name: $name }) {
					id
				}
			}
		"""

		variables = {
			'name': name
		}

		result = self.__callGraphQL(query, variables)
		movie_data["id"] = result.get('movieCreate').get('id')

		return self.update_movie(movie_data)
	def update_movie(self, movie_data):
		query = """
			mutation MovieUpdate($input:MovieUpdateInput!) {
				movieUpdate(input: $input) {
					id
				}
			}
		"""
		variables = {'input': movie_data}

		result = self.__callGraphQL(query, variables)
		return result["movieUpdate"]["id"]

	def find_or_create_movie(self, movie_data, update_movie=False):
		movie_stashid = self.find_movie(movie_data)
		if movie_stashid:
			if update_movie:
				movie_data['id'] = movie_stashid
				self.update_movie(movie_data)
			return movie_stashid
		else:
			return self.create_movie(movie_data)
	
	def find_movies(self, movie, f={}):
		query = """
			query FindMovies($filter: FindFilterType, $movie_filter: MovieFilterType) {
				findMovies(filter: $filter, movie_filter: $movie_filter) {
					count
					movies {
						id
						name
						aliases
					}
				}
			}
		"""

		search = ""
		if movie.get('name'):
			search = movie.get('name')

		variables = {
			"filter": {
				"per_page": -1,
				"q": search
			},
			"movie_filter": f
		}
		
		result = self.__callGraphQL(query, variables)
		return result.get('findMovies').get('movies')


	def find_movies_with_url(self):
		return self.find_movies(f={
			"url": {
			"value": "",
			"modifier": "NOT_NULL"
			}
  		})

	def get_movies_missing_front_image(self):
		return self.find_movies(f={
			"url": {
			"value": "",
			"modifier": "NOT_NULL"
			},
			"is_missing": "front_image"
		})

	def find_scenes_where_path_like(self, path_part):
		return self.find_scenes(f={
			"path": {
			"value": f"{path_part}\"",
			"modifier": "INCLUDES"
			}
		})

	def find_scenes_with_tag(self, tag):
		tag_id = None
		if tag.get('id'):
			tag_id = tag.get('id')
		elif tag.get('name'):
			tag_id = self.get_tag_id_from_name(tag.get('name'))

		scene_filter = {
			"tags": {
				"value": [tag_id],
				"modifier": "INCLUDES"
			}
		}
		return self.find_scenes(filter=scene_filter)

stash_gql_fragments = {
	"scrapedScene":"""
		fragment scrapedScene on ScrapedScene {
		  title
		  details
		  url
		  date
		  image
		  file{
			size
			duration
			video_codec
			audio_codec
			width
			height
			framerate
			bitrate
		  }
		  studio{
			stored_id
			name
			url
			remote_site_id
		  }
		  tags{ ...scrapedSceneTag }
		  performers{
			...scrapedScenePerformer
		  }
		  movies{
			...scrapedSceneMovie
		  }
		  remote_site_id
		  duration
		  fingerprints{
			algorithm
			hash
			duration
		  }
		  __typename
		}
	""",
	"scrapedScenePerformer":"""
		fragment scrapedScenePerformer on ScrapedScenePerformer {
		  stored_id
		  name
		  gender
		  url
		  twitter
		  instagram
		  birthdate
		  ethnicity
		  country
		  eye_color
		  height
		  measurements
		  fake_tits
		  career_length
		  tattoos
		  piercings
		  aliases
		  tags { ...scrapedSceneTag }
		  remote_site_id
		  images
		  details
		  death_date
		  hair_color
		  weight
		  __typename
		}
	""",
	"scrapedSceneTag": """
		fragment scrapedSceneTag on ScrapedSceneTag {
			stored_id
			name
		}
	""",
	"scrapedSceneMovie": """
		fragment scrapedSceneMovie on ScrapedSceneMovie {
			stored_id
			name
			aliases
			duration
			date
			rating
			director
			synopsis
			url
		}
	""",
	"scrapedPerformer":"""
		fragment scrapedPerformer on ScrapedPerformer {
			name
			gender
			url
			twitter
			instagram
			birthdate
			ethnicity
			country
			eye_color
			height
			measurements
			fake_tits
			career_length
			tattoos
			piercings
			aliases
			tags { ...scrapedSceneTag }
			image
			details
			favorite
			death_date
			hair_color
			weight
			__typename
		}
	""",
	"stashSceneUpdate":"""
		fragment stashSceneExit on Scene {
			id
			title
			details
			url
			date
			rating
			gallery_ids
			studio_id
			performer_ids
			movies
			tag_ids
			stash_ids
		}
	""",
	"stashScene":"""
		fragment stashScene on Scene {
		  id
		  checksum
		  oshash
		  title
		  details
		  url
		  date
		  rating
		  organized
		  o_counter
		  path
		  tags {
			...stashTag
		  }
		  file {
			size
			duration
			video_codec
			audio_codec
			width
			height
			framerate
			bitrate
		  }
		  galleries {
			id
			checksum
			path
			title
			url
			date
			details
			rating
			organized
			studio {
			  id
			  name
			  url
			}
			image_count
			tags {
			  ...stashTag
			}
		  }
		  performers {
			...stashPerformer
		  }
		  studio{
			id
			name
			url
			stash_ids{
				endpoint
				stash_id
			}
		  }
		  stash_ids{
			endpoint
			stash_id
		  }
		}
	""",
	"stashSceneAsUpdate":"""
		fragment stashSceneAsUpdate on Scene {
		  id
		  title
		  details
		  url
		  date
		  rating
		  organized
		  tags {
			id
		  }
		  performers {
			id
		  }
		  studio{
			id
		  }
		}
	""",
	"stashPerformer":"""
		fragment stashPerformer on Performer {
			id
			checksum
			name
			url
			gender
			twitter
			instagram
			birthdate
			ethnicity
			country
			eye_color
			height
			measurements
			fake_tits
			career_length
			tattoos
			piercings
			aliases
			favorite
			tags { ...stashTag }
			image_path
			scene_count
			image_count
			gallery_count
			stash_ids {
				stash_id
				endpoint
				__typename
			}
			rating
			details
			death_date
			hair_color
			weight
			__typename
		}
	""",
	"stashSceneMarker":"""
		fragment stashSceneMarker on SceneMarker {
			id
			scene
			title
			seconds
			primary_tag { ...stashTag }
			tags {...stashTag }
		}
	""",
	"stashTag":"""
		fragment stashTag on Tag {
			id
			name
			image_path
			scene_count
		}
	"""
}