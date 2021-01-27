import os
import re
import json
import base64
import webbrowser as browser
from functools import partial
from requests import exceptions
from urllib.parse import urlencode
from requests_html import HTMLSession

from iter.accessories import fetch
from system.tools import get_future

here = os.environ.get('spotdir')
authorizaton_file = os.environ.get('spotify_auth_file')

with open(f'{here}/client.conf', 'r') as configuration:
    config = json.load(configuration)

HEADERS = config['headers']
endpoints = config['endpoints']

# scopes are only neccessary when first initalizing app permissions
scopes = [
    'user-read-currently-playing', 'user-read-playback-state',
    'playlist-modify-public', 'playlist-modify-private'
]


def base64encode(urldata):
    """encode text to binary as required by spotify url scheme"""
    dataBytes = urldata.encode('ascii')
    base64Bytes = base64.b64encode(dataBytes)
    return base64Bytes.decode('ascii')


class SpotifyClient():

    def __init__(self, client=None, secret=None, csrf=None, redirect=None, scope=None):
        """ Spotify Api Interface to query user's account for currently playing 
            track data. The scope can be modified to accommadate other endpoints 
            by adding the appropiate authorization scopes to the scope list. 
            However, new methods must be written to use the new endpoints, and
            the app will need to be authorized each time the scope is altered to
            grant the app the appropiate permissions.

            See https://developer.spotify.com/documentation/general/guides/scopes/ 
            for more info.

            A valid redirect url is also required for this client to obtain an 
            authcode, which can be 127.0.0.1,  but you may need to set up a local 
            server for localhost to work.

            The redirect url must be white-listed in the apps settings of the 
            Spotify developer's account.

            Once an auth code is obtained, the redirect url must reachable when 
            you request an access token from the api. It will return a HTTP Error 400 
            if the redirect isn't valid or accessible.

            ARGUMENTS:
                client:  str: the client id issued by Spotify for your app
                secret:  str: the secret id issued by Spotify for your app

                csrf:    str: csrf token string used as a url parameter to prevent 
                              cross site forgery attacks. It is optional and can 
                              be left as None if desired.

                redirect str: valid url to a domain you control used for redirection. 
                              Mandatory.

                scope   list: a list of the domains within the spotify api this app
                              will have permission to access. Only neccessary when 
                              first initalizing app permissions
        """
        self.session = HTMLSession()
        self.state = csrf
        self.scope = scope
        self.app_id = client
        self.secret = secret
        self.redirect = redirect
        self.auth_id = base64encode(f'{self.app_id}:{self.secret}')
        self.grant = {**HEADERS['grant'], "redirect_uri": self.redirect}
        self.basic = {**HEADERS['basic'], 'Authorization': f"Basic {self.auth_id}"}
        self.get = partial(self.api_connect, 'get')
        self.post = partial(self.api_connect, 'post')
        self.delete = partial(self.api_connect, 'delete')

    def __repr__(self):
        return f"<class {type(self).__name__}(scope={', '.join(self.scope)})>"

    def api_connect(self, method, endpoint, **kwargs):
        """connect to the spotify api for data manipulation and retrieval"""
        with self.session as connection:
            api = getattr(connection, method)
            try:
                response = api(endpoint, **kwargs)
                response.raise_for_status()
                return response.json()

            except exceptions.RequestException as error:
                if response.status_code == 401:
                    self.refresh_access_token()
                    return 0
                print(error)

    def auth_api_connect(self, method, endpoint, **kwargs):
        """connect to the spotify api for authorization requests"""
        with self.session as connection:
            api = getattr(connection, method)
            try:
                response = api(endpoint, **kwargs)
                response.raise_for_status()
                content = response.headers.get('content-type')
                if content == 'application/json':
                    return response.json()
                return response.url

            except exceptions.RequestException as error:
                print(error)

    def authorization_url(self):
        """format and encode the authorization url"""
        payload = {
            'client_id': self.app_id,
            'response_type': 'code',
            'redirect_uri': self.redirect,
            'scope': ' '.join(self.scope),
            'state': self.state,
            'show_dialog': False}

        return f"{endpoints['authorize']}?{urlencode(payload)}"

    def authorize_app(self):
        """get authorization code for the app.

            The first time you run the client, you'll be required to authorize 
            the app.

            USAGE:
                authcode = client.authorize_app()

            The default browser will open, prompting spotify user login and 
            account authorization of the app. Then it will redirect to the 
            specified redirect url. Copy the url from the browser bar and paste 
            it into the command prompt. 

            This will extract the authorization code which then must be passed 
            to the generate_access_token method to get an access token.

            You should only need to do this once because once an access token 
            is granted, it can be refreshed indefinitely if you store the refresh 
            token between application runs. 
        """
        endpoint = self.authorization_url()
        url = self.auth_api_connect('get', endpoint)
        browser.open(url)
        urlcode = input("copy and paste the redirect url from the browser bar here: ")
        return re.search(r'(?<=code=)[a-zA-Z0-9_-]+', urlcode).group(0)

    def generate_access_token(self, code=None):
        """get a spotify access token.

           The access token is required to be in the url parameters in order to 
           make successful calls to the api.

           ARGUMENTS:
                code: str: the app authorization code provided by the spotify api,
                           obtained using the client.authorize_app() method.

           USAGE:
                client.generate_access_token(code=authcode)
        """
        endpoint = endpoints['oauth']
        payload = urlencode({**self.grant, "code": code})
        access = self.auth_api_connect('post', endpoint, headers=self.basic, params=payload)
        self.token = access['access_token']
        self.expires = get_future(access['expires_in'])
        self.refresh = access['refresh_token']
        self.authorized = {"Authorization": f"Bearer {self.token}"}
        self.write_access()
        self.store_expiration()

    def refresh_access_token(self):
        """Send a request to refresh the access token after it expires. 

           Once you have the initial access token, you should only need to use 
           the refresh token to update the app authorization after the access_token 
           expires. The token lasts for an hour at a time. After it expires, 
           make a refresh request using this method.

           All subsequent requests for access should be made with the 
           refresh_access_token() method.

            ARGUMENTS:
                tokem: str: the refresh token that was provided by the spotify 
                            api when the app was granted the initial access token. 
                            It is stored in the attribute client.refresh.

            USAGE:
                client.refresh_access_token(token=self.refresh) 
        """
        endpoint = endpoints['oauth']
        payload = urlencode({**HEADERS['renew'], 'refresh_token': self.refresh})
        access = self.auth_api_connect('post', endpoint, headers=self.basic, params=payload)
        self.token = access['access_token']
        self.expires = get_future(access['expires_in'])
        self.authorized = {"Authorization": f"Bearer {self.token}"}
        if 'refresh_token' in access:
            self.refresh['refresh_token'] = access['refresh_token']
        self.write_access()
        self.store_expiration()

    def write_access(self):
        """make authorization credentials accessible to other processes"""
        current_session = {'header': self.authorized, 'refresh_token': self.refresh}
        with open(authorizaton_file, 'w') as output:
            json.dump(current_session, output)

    def store_expiration(self):
        """store token expiration time for future checks"""
        with open('/tmp/spotify-api/auth-expiration.txt', 'w') as file:
            file.write(self.expires)

    def get_current_track(self):
        """query the currently-playing endpoint for data pertaining to the
           media currently being played in the user's spotify account. 
           returns a json object. 

           ARGUMENTS:
                access: str: the access token granted by spotify and stored in the 
                             client.token attribute.

            USAGE:
                client.get_current_track(access=self.token)
        """
        endpoint = endpoints['current_track']
        return self.get(endpoint, headers=self.authorized)

    def get_playback_status(self):
        """query the player endpoint for data pertaining to the
           current state of the user's music player. 
           returns a json object.

           ARGUMETS:
                access: str: the access token granted by spotify and store in the 
                             client.token attribute.

            USAGE:
                client.get_playback(access=self.token)
        """
        endpoint = endpoints['playback']
        return self.get(endpoint, headers=self.authorized)

    def get_playlists(self):
        """returns a json object od data pertaining to user's playlists"""
        endpoint = endpoints['playlists']
        return self.get(endpoint, headers=self.authorized)

    def get_playlist(self, playlist_id):
        """returns information about a specific playlist in json format"""
        endpoint = endpoints['playlist'].format(playlist_id)
        return self.get(endpoint, headers=self.authorized)

    def add_track(self, playlist_id, uri):
        """add track to specified playlist"""
        endpoint = endpoints['manage_tracks'].format(playlist_id)
        header = {**self.authorized, 'content-type': 'application/json'}
        return self.post(endpoint, headers=header, params={"uris": [uri]})

    def delete_track(self, playlist_id, uri):
        """delete track from specified playlist"""
        endpoint = endpoints['manage_tracks'].format(playlist_id)
        header = {**self.authorized, 'accept': 'application/json', 'content-type': 'application/json'}
        return self.delete(endpoint, headers=header, data={"tracks": [{"uri": uri}]})

    def get_track_duration(self, jsdata):
        """calculate the time remaining of currently playing track 

          ARGUMENTS:
                jsdata: json: the json object returned by get_playback()
        """
        duration = next(fetch(jsdata, 'duration_ms'))
        position = next(fetch(jsdata, 'progress_ms'))
        return duration - position
