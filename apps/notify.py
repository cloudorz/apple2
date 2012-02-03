# coding: utf-8

import datetime

from apps import BaseRequestHandler
from apps.models import Loud, Reply, Prize
from apps.rdbm import Message, ReadMessage
from utils.decorator import authenticated
from utils.tools import pretty_time_str

class LastBaseRequestHandler(BaseRequestHandler):

    @property
    def last_modified_time(self):
        ims = self.request.headers.get('If-Modified-Since', None)
        ims_time = datetime.datetime(1970,1,1,0,0)

        if ims:
            ims_time = datetime.datetime.strptime(ims, '%a, %d %b %Y %H:%M:%S %Z')

        return ims_time


class LoudUpdatedHandler(LastBaseRequestHandler):

    @authenticated
    def get(self):
        
        last = self.last_modified_time
        # loud update check
        lat = self.get_argument('lat')
        lon = self.get_argument('lon')
        new_loud_count = Loud.query.cycle_update(lat, lon, last).count()

        #self.set_header('Last-Modified', pretty_time_str(datetime.datetime.utcnow()))
        self.render_json({'num': new_loud_count})


class MessageUpdatedHandler(LastBaseRequestHandler):
    
    @authenticated
    def get(self):
        
        # messages update check
        msg = ReadMessage(self.current_user.id, self.last_modified_time)
        messages = msg.getMessages()

        #self.set_header('Last-Modified', pretty_time_str(datetime.datetime.utcnow()))
        self.render_json({'num': len(messages)})


class PrizeUpdatedhandler(LastBaseRequestHandler):

    @authenticated
    def get(self):
        
        # prize update check
        prizes = Prize.query.filter(Prize.created>=self.last_modified_time)

        #self.set_header('Last-Modified', pretty_time_str(datetime.datetime.utcnow()))
        self.render_json({'num': prizes.count()})


class MessageHandler(LastBaseRequestHandler):
    
    @authenticated
    def get(self):
        msg = ReadMessage(self.current_user.id, self.last_modified_time)
        messages = msg.getMessages()

        message_collection = {
                'messages': messages,
                'total': len(messages),
                'link': self.full_uri(),
                }

        self.set_header('Last-Modified', pretty_time_str(datetime.datetime.utcnow()))
        self.render_json(message_collection)
