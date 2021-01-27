"""utility functions needed by the SpotifyClient and associated scripts
"""
from datetime import datetime
from datetime import timedelta


def get_future(secs):
    """calculate time from now until specific time in the future"""
    mins = secs / 60
    future = datetime.now() + timedelta(minutes=mins)
    return future.strftime('%H:%M:%S')


def fetch(iterable, token):
    """designed for parsing tortuous json files, fetch is
       a recursive generator that locates the specified json key 
       at any nested depth or complexity.

       Fetch returns a generator.

       ARGUMENTS:
           iterable: json file or object; (dict, list):

                     a json file with any number of nested lists
                     and dictionaries.

           token: str:
                    the json/dict key that points to the desired data.
    """
    if isinstance(iterable, dict):
        for key, value in iterable.items():
            if key == token:
                yield iterable[key]
            if isinstance(value, (dict, list)):
                yield from fetch(value, token)

    elif isinstance(iterable, list):
        for item in iterable:
            if isinstance(item, (dict, list)):
                yield from fetch(item, token)
