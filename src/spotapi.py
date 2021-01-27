#!/Users/kafka/.local/share/virtualenvs/spotify-api-QrUSopDC/bin/python3.8
"""
A simple utility that uses SpotifyClient to get information from the 
spotify api about currently playing tracks, playlists and the ability to 
'like' the currently playing track, which adds it to a specified playlist.

This utility caches authorization and media information locally for faster 
access.
"""
import os
import sys
import time
import json
from datetime import datetime
from iter.accessories import fetch
from client import SpotifyClient

app = os.environ.get('spotify_app')
key = os.environ.get('spotify_key')
url = os.environ.get('app_redirect')
tkn = os.environ.get('csrf_token')
uri = os.environ.get('current_track_uri')

liked_tracks = os.environ.get('default_playlist')
authorization_file = os.environ.get('spotify_auth_file')

api = SpotifyClient(client=app, secret=key, csrf=tkn, redirect=url)
api.refresh = os.environ.get('spotify_access')


def create_tmp(path):
    """create tmp directory if it doesn't already exist"""
    if os.path.isdir(path):
        return 1
    try:
        os.mkdir(path)
        return 1

    except OSError as error:
        print(error)
        return 0


def get_access():
    """shared session: import access credentials from uthorization file"""
    try:
        if datetime.now().strftime('%H:%M:%S') >= get_auth_expiration():
            api.refresh_access_token()
            return 0

        with open(authorization_file, 'r') as cs:
            return json.load(cs)

    except FileNotFoundError:
        api.refresh_access_token()
        return 0


def save_track_uri(track_uri):
    """save uri of current track to for ipc"""
    with open(uri, 'w') as file:
        file.write(track_uri)


def get_auth_expiration():
    with open('/tmp/spotify-api/auth-expiration.txt', 'r') as file:
        return file.read().strip()


def check_cache(filename, track):
    """checks if data is cached then lazily tests for value membership"""
    with open(filename, 'r') as cached:
        return next((True for line in cached if track in line), False)


def create_cache(filename, items):
    """create a cache file if one doesn't already exist"""
    with open(filename, 'w') as cache:
        cache.write('\n'.join(items))


def append_cache(filename, track):
    """append data to the end of the cache file"""
    with open(filename, 'a') as cache:
        cache.write(f'{track}')


def track_in_playlist(track, playlist_id):
    """check to see if track is already in the specified playlist"""
    if os.path.isfile('/tmp/spotify-api/liked.txt'):
        return check_cache('/tmp/spotify-api/liked.txt', track)

    data = api.get_playlist(playlist_id)
    if data:
        tracks = [item for item in fetch(data['tracks'], 'uri') if 'track' in item]
        create_cache('/tmp/spotify-api/liked.txt', tracks)
        return track in tracks


def like(playlist=liked_tracks):
    """add currently playing track to specified playlist"""
    with open(uri, 'r') as track_data:
        track_uri = track_data.read().strip()

    if track_uri:
        if track_in_playlist(track_uri, playlist):
            print(f"track {track_uri} is already in playlist {playlist}")
            return None

        response = api.add_track(playlist, track_uri)

        try:
            print('snapshot id: ', response['snapshot_id'])
            print(f"added {track_uri} to playlist: {playlist}")
            append_cache('/tmp/spotify-api/liked.txt', f'{track_uri}\n')

        except TypeError:
            print('Spotify was unable to process this request')
    else:
        print('an error has occured: uri file was corrupt or inaccessible')


def playlists():
    """prints playlist names and corresponding ids to stdout"""
    plists = api.get_playlists()
    for item in plists['items']:
        sys.stdout.write("%-30s %-25s\n" % (item['name'], item['id']))


def info():
    """currently playing track info and uris"""
    info = api.get_current_track()['item']
    save_track_uri(info['uri'])
    sys.stdout.write("%-60s %-25s\n" % (f"Track:  {info['name']}", info['uri']))
    sys.stdout.write("%-60s %-25s\n" % (f"Album:  {info['album']['name']}", info['album']['uri']))
    sys.stdout.write("%-60s %-25s\n" % (f"Artist: {info['artists'][0]['name']}", info['artists'][0]['uri']))


def show_help():
    sys.stdout.write("%-30s %-25s\n" % ("spotapi help", "display this help file"))
    sys.stdout.write("%-30s %-25s\n" % ("spotapi like", "add song to specified default playlist"))
    sys.stdout.write("%-30s %-25s\n" % ("spotapi playlists", "show all playlists and playlist_ids"))
    sys.stdout.write("%-30s %-25s\n" % ("spotapi info", "display currently playing track info and uris"))


def main(flag):
    """main function"""
    cmd = dict(zip('-h -i -p -l'.split(), (show_help, info, playlists, like)))

    tmp_directory = create_tmp('/tmp/spotify-api')
    if tmp_directory:
        session = get_access()
        if session:
            api.authorized = session['header']

        try:
            cmd[flag]()

        except KeyError:
            show_help()


if __name__ == '__main__':
    start = time.time()
    main(sys.argv[1])
    print(f"\nfinished in {time.time() - start} seconds")
