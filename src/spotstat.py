import os
import sys
from time import sleep
from client import SpotifyClient
from utilities.iter.accessories import fetch

CLEAR = ''
TAGS = ['ARTIST: ', 'ALBUM: ', 'TRACK: ']

app = os.environ.get('spotifyapp')
key = os.environ.get('spotifykey')
url = os.environ.get('appwebsite')
tkn = os.environ.get('csrf_token')
stb = os.environ.get('status_bar')

api = SpotifyClient(client=app, secret=key, csrf=tkn, redirect=url)
api.refresh = os.environ.get('spotifyacc')

def query():
    """query the api for current playback state
       returns artist, album, track information
    """
    data = api.get_current_track(access=api.token)
    if data:
        info = list({value: 0 for value in fetch(data, 'name')})
        text = list(zip(TAGS, info))
        return ' | '.join([''.join(item) for item in text])
    return 0

def status(file, data):
    with open(file, 'w') as spotstat:
        spotstat.write(data)
         
if __name__ == '__main__':
    request = 0
    api.refresh_access_token(token=api.refresh)
    try:
        while True:
            while not request:
                request = query()
    
            print(request)
            status(stb, request)
            pos = api.get_playback(access=api.token)
            dur = api.get_track_duration(pos)
            sleep((dur/1000.0) + 3)
            request = 0
            
    except KeyboardInterrupt:
        status(stb, CLEAR)
        sys.exit()