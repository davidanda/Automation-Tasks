import json
import os

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import requests
import youtube_dl

from exceptions import ResponseException
from secrets import spotify_token, spotify_user_id
from playlistId import playlist_id


class CreatePlaylist:
    def __init__(self):
        self.youtube_client = self.get_youtube_client()
        self.user_id = spotify_user_id
        self.spotify_token = spotify_token
        self.playlist_id = playlist_id
        self.all_song_info = {}

    def get_youtube_client(self):
        # Disable OAuthlib's HTTPS verification when running locally.
        # *DO NOT* leave this option enabled in production.
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        api_service_name = "youtube"
        api_version = "v3"
        client_secrets_file = "client_secret.json"

        # Get credentials and create an API client
        scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, scopes)

        credentials = flow.run_console()

        # from the Youtube DATA API
        youtube_client = googleapiclient.discovery.build(
            api_service_name, api_version, credentials=credentials)

        return youtube_client

    def get_playlist_videos(self):
        request = self.youtube_client.playlistItems().list(
            part="snippet,contentDetails",
            maxResults=25,
            playlistId="{}".format(self.playlist_id)
            )
        response = request.execute()

        # collect each video and get important information      
        for i in range(len(response["items"])):
            video_title = response["items"][i]["snippet"]["title"]
            video_id = response["items"][i]["snippet"]["resourceId"]["videoId"]
            youtube_url = "https://www.youtube.com/watch?v={}".format(video_id)


            # using youtube_dl to collect the song name & artist name
            video = youtube_dl.YoutubeDL({}).extract_info(youtube_url, download=False, force_generic_extractor=False)
            track = video["track"]
            artist = video["artist"]

            if track is not None and artist is not None:
                # save all important info and skip any missing song and artist
                self.all_song_info[video_title] = {
                    "youtube_url": youtube_url,
                    "track": track,
                    "artist": artist,

                    # add the uri, easy to get song to put into playlist
                    "spotify_uri": self.get_spotify_uri(track, artist)

                }

    def create_playlist(self):
        request_body = json.dumps({
            "name": "Youtube chunes",
            "description": "playlist generated from my youtube playlist",
            "public": True
        })

        query = "https://api.spotify.com/v1/users/{}/playlists".format(self.user_id)
        response = requests.post(
            query,
            data = request_body,
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.spotify_token)
        })
        response_json = response.json()

        # playlist id
        return response_json["id"]

    def get_spotify_uri(self, track, artist):
        query = "https://api.spotify.com/v1/search?query={}+{}&type=track&offset=0&limit=20".format(track, artist)
        response = requests.get(
            query,
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.spotify_token)
        })
        response_json = response.json()
        tracks = response_json["tracks"]["items"]

        # only use the first song
        uri = tracks[0]["uri"]

        return uri

    def add_song_to_playlist(self):
        """Add all songs from youtube playlist into a new Spotify playlist"""
        # populate dictionary with the songs
        self.get_playlist_videos()

        # collect all of uri
        uris = [info["spotify_uri"] for song, info in self.all_song_info.items()]

        # create a new playlist
        playlist_id = self.create_playlist()

        # add all songs into new playlist
        request_data = json.dumps(uris)

        query = "https://api.spotify.com/v1/playlists/{}/tracks".format(
            playlist_id)

        response = requests.post(
            query,
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.spotify_token)
            }
        )

        # check for valid response status

        if response.status_code != 201:
            raise ResponseException(response.status_code)

        response_json = response.json()
        return response_json


#if __name__ == '__main__':
cp = CreatePlaylist()
cp.add_song_to_playlist()