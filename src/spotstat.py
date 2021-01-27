#!/Users/kafka/.local/share/virtualenvs/spotify-api-QrUSopDC/bin/python3.8
"""
Simple script that uses SpotifyClient to display currently playing 
spotify music in tmux status bar.
"""
import os
import sys
import signal
from time import sleep
from textwrap import shorten
from client import SpotifyClient

from iter.accessories import fetch

RESET = 'Connecting to Spotify...'
TAGS = ['ARTIST: ', 'ALBUM: ', 'TRACK: ']

app = os.environ.get('spotify_app')
key = os.environ.get('spotify_key')
url = os.environ.get('app_redirect')
tkn = os.environ.get('csrf_token')
uri = os.environ.get('current_track_uri')
bar = os.environ.get('status_bar')

authorizaton_file = os.environ.get('spotify_auth_file')

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


def terminate(signum, frame):
    """graceful shutdown and file cleanup on SIGTERM"""
    status(bar, RESET)
    open(authorizaton_file, 'w').close()
    sys.exit()


def status(file, data):
    """update the tmux status bar"""
    with open(file, 'w') as spotstat:
        spotstat.write(data)


def get_track_id(data):
    """store the uri of currently play track for inter process access"""
    try:
        track_id = data['item']['uri']

    except AttributeError:
        track_id = None

    finally:
        with open(uri, 'w') as file:
            file.write(track_id)


def query():
    """query the api for current playback state, artist, album, track info"""
    data = api.get_current_track()
    if data:
        if data['is_playing']:
            get_track_id(data)
            info = list({value: 0 for value in fetch(data, 'name')})
            text = list(zip(TAGS, info))
            return ' | '.join([''.join(item) for item in text])
        print('spotify transport state is currently inactive')
        sys.exit()
    return 0


def main():
    tmp_directory = create_tmp('/tmp/spotify-api')
    if tmp_directory:
        request = 0
        api.refresh_access_token()
        signal.signal(signal.SIGTERM, terminate)
        try:
            while True:
                while not request:
                    request = query()

                status(bar, shorten(request, width=100, placeholder='...'))
                pos = api.get_playback_status()
                dur = api.get_track_duration(pos)
                sleep((dur / 1000.0) + 2)
                request = 0

        except KeyboardInterrupt:
            status(bar, RESET)
            open(authorization_file, 'w').close()
            sys.exit()


if __name__ == '__main__':
    main()
