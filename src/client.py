import re
import json
import urllib
import base64
import webbrowser as browser
from datetime import datetime
from datetime import timedelta
from requests import exceptions
from requests_html import HTMLSession
from utilities.iter.accessories import fetch

def get_future(secs):
    mins = secs/60
    future = datetime.now() + timedelta(minutes=mins)
    return future.strftime('%H:%M:%S')


class SpotifyClient():

    BASE_API = 'https://api.spotify.com/v1/me'
    OAUTH_TOKEN_URL = "https://accounts.spotify.com/api/token"
    OAUTH_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    
    def __init__(self, client=None, secret=None, csrf=None, redirect=None):
        """ Spotify Api Interface to query user's account for currently playing track data.
            The scope can be modified to accommadate other endpoints by adding the appropiate
            authorization scopes to the scope list. However, new methods must be written to use the new endpoints.
            
            See https://developer.spotify.com/documentation/general/guides/scopes/ for more info.
            
            A valid redirect url is also required for this client to obtain an authcode, which can be 127.0.0.1,  but you 
            may need to set up a local server for localhost to work.

            The redirct url must be white-listed in the apps settings of the Spotify developer account.
            
            Once an auth code is obtained, the redirect url must reachable when you request an access token from the api.
            It will return a HTTP Error 400 if the redirect isn't valid or accessible.
        
            ARGUMENTS:
                client:  str: the client id issued by Spotify for your app
                secret:  str: the secret id issued by Spotify for your app
                
                csrf:    str: csrf token string used as a url parameter to prevent cross site forgery attacks. 
                              It is optional and can be left as None if desired.
                              
                redirect str: valid url to a domain you control used for redirection. Mandatory.
        """
        self.session = HTMLSession()
        self.app_id = client
        self.secret = secret
        self.authid = f'{self.app_id}:{self.secret}'
        self.scope = ['user-read-currently-playing', 'user-read-playback-state']
        self.state = csrf
        self.redirect = redirect
        self.headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f"Basic {self.base64Encoder(self.authid)}"}

    def base64Encoder(self, urldata):
        """Encode text to binary as required by Spotify url scheme
        """
        dataBytes = urldata.encode('ascii')
        base64Bytes = base64.b64encode(dataBytes)
        return base64Bytes.decode('ascii')

    def get_authorize_url(self):
        """ Generate the Auth URL
        """
        payload = {
            'client_id': self.app_id, 
            'response_type': 'code', 
            'redirect_uri': self.redirect, 
            'scope': ' '.join(self.scope),
            'state': self.state,
            'show_dialog': False
        }
        urlparams = urllib.parse.urlencode(payload)
        return f"{self.OAUTH_AUTHORIZE_URL}?{urlparams}"

    def authorize_app(self):
        """Get Authorization Code for the app.
        
            The first time you run the client, you'll be required to authorize the app.
        
            USAGE:
                authcode = client.authorize_app()
            
            The default browser will open, prompting spotify user login and account authorization
            of the app. Then it will redirect to the specified redirect url. Copy the url from the browser 
            bar and paste it into the command prompt. 
            
            This will extract the authorization code which then must be passed to the 
            generate_access_token method to get an access token.

            You should only need to do this once because once an access token is granted, it can be 
            refreshed indefinitely if you store the refresh token between application runs. 
        """
        auth_url = self.get_authorize_url()
        with self.session as oauth:
            try:
                response = oauth.get(auth_url)
                response.raise_for_status()
                browser.open(response.url)
                urlcode = input("copy and paste the redirect url from the browser bar here: ")
                return re.search(r'(?<=code=)[a-zA-Z0-9_-]+', urlcode).group(0)
                
            except exceptions.RequestException as error:
                print(f'An error has occured.\n{error}') 


    def generate_access_token(self, code=None):
        """Get Spotify access token, which must be included in
           the request url parameters when making a call to the API.

           The access token is required to be in the url parameters in order to make successful calls to the api.

           ARGUMENTS:
                code: str: the app authorization code provided by the spotufy api

           USAGE:
                client.generate_access_token(code=authcode)
        """
        payload = {'grant_type': "authorization_code", "code": code, "redirect_uri": self.redirect}
        with self.session as auth:
            try:
                urlparams = urllib.parse.urlencode(payload)
                response = auth.post(self.OAUTH_TOKEN_URL, headers=self.headers, params=urlparams)
                response.raise_for_status()
                self.token = response.json()['access_token']
                self.expires = response.json()['expires_in']
                self.refresh = response.json()['refresh_token']
                #print(f'access token expires at {get_future(self.expires)}')
                
            except (exceptions.RequestException) as error:
                print(f'An error has occured.\n{error}') 


    def refresh_access_token(self, token=None):
        """Send a request to refresh the access token after it expires. Once you have the initial
            access token, you should only need to use the refresh token to update the app authorization
            after the access_token expires. The token lasts for an hour at a time. After it expires, 
            mahe a refresh request using this method.
            
            All subsequent requests for access should be made with the refresh_access_token() method.

            ARGUMENTS:
                tokem: str: the refresh token that was provided by the spotify api when the app was granted 
                            the initial access token. It is stored in the attribute client.refresh.

            USAGE:
                client.refresh_access_token(token=self.refresh) 
        """
        payload = {'grant_type': 'refresh_token', 'refresh_token': token}  
        with self.session as refresh:
            try:
                urlparams = urllib.parse.urlencode(payload)
                response = refresh.post(self.OAUTH_TOKEN_URL, headers=self.headers, params=urlparams)
                response.raise_for_status()
                self.token = response.json()['access_token']
                self.expires = response.json()['expires_in']
                if 'refresh_token' in response.json():
                    self.refresh = response.json()['refresh_token']
                #print(f'access token expires at {get_future(self.expires)}')
                
            except (exceptions.RequestException) as error:
                print(f'An error has occured.\n{error}')         

     
    def get_current_track(self, access=None):
        """Query the currently-playing endpoint for  data pertaining to the
           media currently being played from the user's Spotify account. A JSON
           object is returned. 

           ARGUMETS:
                access: str: the access token granted by spotify and stored in the 
                             client.token attribute.

            USAGE:
                client.get_current_track(access=self.token)
        """
        endpoint = f'{self.BASE_API}/player/currently-playing'
        with self.session as api:
            try:
                response = api.get(endpoint, headers={"Authorization": f"Bearer {access}"})
                response.raise_for_status()
                return response.json()
                
            except exceptions.RequestException as error:
                if response.status_code == 401:
                    self.refresh_access_token(token=self.refresh)
                    return 0
                print(error)

    def get_playback(self, access=None):
        """Query the player endpoint for user data pertaining to the
           current state of the user's music player. A JSON object is 
           returned from the api.

           ARGUMETS:
                access: str: the access token granted by spotify and store in the 
                             client.token attribute.

            USAGE:
                client.get_playbackk(access=self.token)
        """
        endpoint = f'{self.BASE_API}/player'
        with self.session as api:
            try:
                response = api.get(endpoint, headers={"Authorization": f"Bearer {access}"})
                response.raise_for_status()
                return response.json()
                
            except exceptions.RequestException as error:
                if response.status_code == 401:
                    self.refresh_access_token(token=self.refresh)
                    return 0
                print(error)

    def get_track_duration(self, jsondata):
        """Calculate the time remaining of currently playing track 

          ARGUMENTS:
                jsondata: json: the json object returned by get_playback()
        """
        duration = next(fetch(jsondata, 'duration_ms'))
        position = next(fetch(jsondata, 'progress_ms'))
        return duration - position
