# coding: utf-8

import httplib, traceback, urlparse, urllib
import logging

import tornado.web
import tornado.httpclient

from tornado.web import HTTPError
from tornado.options import options
from tornado.httputil import url_concat
from tornado.auth import OAuthMixin, OAuth2Mixin, OpenIdMixin
from tornado.escape import url_escape, utf8
#from tornado.escape import url_unescape

from utils.escape import json_encode, json_decode
from utils.tools import QDict, make_md5
from apps.models import User, App

# The base request handler class
class BaseRequestHandler(tornado.web.RequestHandler):
    """the base RequestHandler for All."""

    @property
    def rdb(self):
        return self.application.redis

    @property
    def db(self):
        return self.application.db_session

    # json pickle data 
    def json(self, data):
        return json_encode(data)

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
            raise HTTPError(415) # the data is not the right json format

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

        if self.check_valid_client():
            name, token = self.auth_user()
            if name and token:
                user = User.query.get_by_userkey(name)
                # TODO be in redis
                return user

        return None

    def check_valid_client(self):
        app_key = self.get_argument('ak', None)

        if app_key:
            app = App.query.get(app_key)
        else:
            app = None

        return app

    def full_uri(self, query_dict=None):
        #return url_unescape(url_concat("%s%s" % (options.site_uri, self.request.path), query_dict))
        #return url_concat(self.request.full_url(), query_dict)
        req = self.request
        return url_concat("%s://%s%s" % (req.protocol, req.host, req.path), query_dict)


class DoubanMixin(OAuthMixin):

    _OAUTH_REQUEST_TOKEN_URL = "http://www.douban.com/service/auth/request_token"
    _OAUTH_AUTHORIZE_URL = "http://www.douban.com/service/auth/authorize"
    _OAUTH_ACCESS_TOKEN_URL = "http://www.douban.com/service/auth/access_token"
    _OAUTH_NO_CALLBACKS = False
    _OAUTH_VERSION = "1.0"

    def douban_request(self, path, callback, method='GET', access_token=None,
            body=None, **args):

        url = urlparse.urljoin("http://api.douban.com", urllib.quote(path))

        headers = None
        if access_token:
            # douban's signa must encode the url
            if method != 'GET':
                oauth = self._oauth_request_parameters(url, access_token, method=method)
                headers = self.to_header(parameters=oauth)
                if method in ('POST', 'PUT'):
                    headers['Content-Type'] = 'Application/atom+xml; charset=utf-8'
            else:
                oauth = self._oauth_request_parameters(url, access_token, args, method=method)
                args.update(oauth)

        if args: 
            url = url_concat(url, args)

        callback = self.async_callback(self._on_douban_request, callback)

        http_client = tornado.httpclient.AsyncHTTPClient()
        http_client.fetch(url, method=method, headers=headers, body=body, callback=callback)

    def to_header(self, realm='', parameters=None):
        """Serialize as a header for an HTTPAuth request."""
        auth_header = 'OAuth realm="%s"' % realm
        # Add the oauth parameters.
        if parameters:
            auth_header = "%s, %s" % (auth_header, ', '.join('%s="%s"' % (k, urllib.quote(str(v))) for
                k,v in parameters.items() if k[:6] == 'oauth_'))
        return {'Authorization': auth_header}

    def _on_douban_request(self, callback, response):
        if response.error:
            logging.warning("Error response %s fetching %s", response.error, response.request.url)
            callback(None)
            return

        try:
            res = json_decode(response.body)
        except (ValueError, TypeError):
            res = response.body

        callback(res)

    def _oauth_consumer_token(self):
        self.require_setting('douban_consumer_key', "Douban OAuth")
        self.require_setting('douban_consumer_secret', "Douban OAuth")

        return dict(
                key=self.settings['douban_consumer_key'],
                secret=self.settings['douban_consumer_secret'],
                )
    
    def _oauth_get_user(self, access_token, callback):
        callback = self.async_callback(self._parse_user_response, callback)
        self.douban_request(
                "/people/@me",
                access_token=access_token,
                callback=callback,
                alt='json',
                )

    def _parse_user_response(self, callback, user):
        if user:
            user['name'] = user['title']['$t']
            user['brief'] = user['content']['$t'][:70]
            user['avatar'] = self._find_icon(user['link'])
            user['expired'] = -1
        callback(user)

    def _find_icon(self, links):
        for e in links:
            if e['@rel'] == 'icon':
                return e['@href']


class WeiboMixin(OAuth2Mixin):

    _OAUTH_AUTHORIZE_URL = "https://api.weibo.com/oauth2/authorize"
    _OAUTH_ACCESS_TOKEN_URL = "https://api.weibo.com/oauth2/access_token"

    def weibo_request(self, path, callback, method='GET', access_token=None, **args):

        url = urlparse.urljoin("https://api.weibo.com/2/", "%s.json" % path)

        if method in ('POST', 'PUT'):
            body = urllib.urlencode(args)
        else:
            url = url_concat(url, args)
            body = None

        callback = self.async_callback(self._on_weibo_request, callback)

        http_client = tornado.httpclient.AsyncHTTPClient()
        http_client.fetch(url, method=method,
                body=body,
                headers={'Authorization': "OAuth2 %s" % access_token},
                callback=callback,
                )

    def _on_weibo_request(self, callback, response):
        if response.error:
            logging.warning("Warn: response %s fetching %s", response.error, response.request.url)
            print response.body
            callback(None)
            return

        info = json_decode(response.body)
        if 'error' in info:
            logging.warning("Warn! code: %s, message: %s", info['error_code'], info['error'])
            callback(None)
            return

        callback(info)

    def weibo_authorize_redirect(self, redirect_uri=None):
        client = self._client_token()
        #redirect_uri = urlparse.urljoin(self.request.full_url(), redirect_uri)
        # FIXME let me go
        redirect_uri = urlparse.urljoin(self._full_uri_or_ip(), redirect_uri)

        self.authorize_redirect(
                redirect_uri=redirect_uri, 
                client_id=client['key'],
                client_secret=client['secret'],
                extra_params={'response_type': 'code'},
                )

    def get_authenticated_user(self, code, callback, redirect_uri=None, http_client=None):

        client = self._client_token()

        #redirect_uri = urlparse.urljoin(self.request.full_url(), redirect_uri)
        # FIXME let me go
        redirect_uri = urlparse.urljoin(self._full_uri_or_ip(), redirect_uri)

        url = self._OAUTH_ACCESS_TOKEN_URL

        extra_params = {
                'grant_type': 'authorization_code',
                }

        args = dict(
            redirect_uri=redirect_uri,
            code=code,
            client_id=client['key'],
            client_secret=client['secret'],
            )
        args.update(extra_params)

        body = urllib.urlencode(args)

        if http_client is None:
            http_client = tornado.httpclient.AsyncHTTPClient()

        callback = self.async_callback(self._on_access_token, callback)

        http_client.fetch(url, method='POST', body=body, callback=callback)

    def _on_access_token(self, callback, response):
        if response.error:
            logging.warning("Error response %s fetching %s", response.error, response.request.url)
            callback(None)
            return

        access_token = json_decode(response.body)
        print access_token
        self._oauth_get_user(access_token, self.async_callback(
             self._on_oauth_get_user, access_token, callback))

    def _on_oauth_get_user(self, access_token, callback, user):
        if not user:
            callback(None)
            return
        user["access_token"] = access_token
        callback(user)

    def _oauth_get_user(self, access_token, callback):
        callback = self.async_callback(self._parse_user_response, callback)
        self.weibo_request(
                "users/show",
                callback,
                access_token=access_token['access_token'],
                uid=access_token['uid'],
                )

    def _parse_user_response(self, callback, user):
        if user:
            user['avatar'] = user['profile_image_url']
            user['brief'] = user['description']
        callback(user)

    def _client_token(self):
        self.require_setting('weibo_app_key', "Weibo OAuth2")
        self.require_setting('weibo_app_secret', "Weibo OAuth2")

        return dict(
                key=self.settings['weibo_app_key'],
                secret=self.settings['weibo_app_secret'],
                )
    
    def _full_uri_or_ip(self):
        if self.request.host == 'localhost':
            url = "http://192.168.0.124/weibo/auth"
        else:
            req = self.request
            url = "%s://%s%s" % (req.protocol, req.host, req.path)

        return url

