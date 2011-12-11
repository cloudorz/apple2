# coding: utf-8

import httplib, datetime, traceback

import tornado.web

from tornado.web import HTTPError
from tornado.options import options
from tornado.httputil import url_concat
#from tornado.escape import url_unescape

from utils.escape import json_encode, json_decode
from utils.tools import QDict, make_md5
from apps.models import User

class BaseRequestHandler(tornado.web.RequestHandler):
    """the base RequestHandler for All."""

    @property
    def rdb(self):
        return self.application.redis

    # json pickle data methods
    def json(self, data):
        dthandler = lambda obj: obj.isoformat() if isinstance(obj, (datetime.datetime, datetime.date)) else obj
        return json_encode(data, default=dthandler)

    # decode json picle data 
    def dejson(self, data):
        return json_decode(data)

    def get_data(self):
        ''' parse the data from request body
        now, only convert json data to python type
        '''
        # the content type is not "application/json"
        if not self.is_json_type:
            raise HTTPError(415)

        try:
            data = self.dejson(self.request.body);
        except (ValueError, TypeError), e:
            raise HTTPError(415) # the data is not the right josn format

        return data

    @property
    def is_json_type(self):
        return self.request.headers.get('Content-Type', '').split(';').pop(0).strip().lower() == 'application/json'

    def write_error(self, status_code, **kwargs):
        if self.settings.get("debug") and "exc_info" in kwargs:
            # in debug mode, try to send a traceback
            for line in traceback.format_exception(*kwargs["exc_info"]):
                self.write(line)
        else:
            self.write("code: %s \n " % status_code)
            self.write("message: %s \n " % httplib.responses[status_code])

        self.set_header('Content-Type', 'text/plain')
        self.finish()

    # render data string for response
    def render_json(self, data, **kwargs):
        self.set_header('Content-Type', 'Application/json; charset=UTF-8')
        self.write(self.json(data))

    def auth_user(self):
        auth_value = self.request.headers.get('Authorization', None)
        if auth_value:
            auth_value = auth_value.strip()
            prefix, b4 = auth_value.split(" ", 1)

            b4 = b4.strip()
            if b4:
                return  b4.decode("base64").split(':', 1)

        return None, None


    def get_current_user(self):

        if self.is_available_client():
            return User.query.get_by_email()
            email, token = self.auth_user()
            if email and token:
                user = User.query.get_by_email(email)
                # TODO be in redis
                return user

        return None

    def is_available_client(self):
        app_key = self.get_argument('ak')
        return app_key == options.app_key

    def full_uri(self, query_dict=None):
        #return url_unescape(url_concat("%s%s" % (options.site_uri, self.request.path), query_dict))
        return url_concat("%s%s" % (options.site_uri, self.request.path), query_dict)
