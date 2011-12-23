# coding: utf-8

import os.path
import redis

import tornado.web
import tornado.httpserver
import tornado.database
import tornado.options
import tornado.ioloop

from tornado.options import define, options
from tornado.web import url

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from apps.loud import LoudHandler, SearchLoudHandler, UpdatedLoudHandler
from apps.user import UserHandler, LoginHandler, UploadHandler
from apps.auth import AuthHandler, AppHandler
from apps.prize import PrizeHandler
from apps.reply import ReplyHandler
from utils.coredb import sql_db

# server
define('port', default=8888, help="run on the given port", type=int)

#URI
#define('site_uri', default="https://n2u.in", type=str, help="site uri") 
#define('static_uri', default="http://s.n2u.in", type=str, help="static uri")
define('site_uri', default="http://localhost:8888", type=str, help="site uri") 
define('static_uri', default="http://localhost:8888/static", type=str, help="static uri")
define('geo_uri', default="http://l.n2u.in", type=str, help="locaiton and address parser uri")

#args
define('er', default=6378137, type=float, help="the earth radius.")
define('cr', default=3000, type=float, help="the cycle radius.")

# database
define('db_uri', default="mysql://root:123@localhost/apple2?charset=utf8", type=str, help="connect to mysql")

# avatar dir  path
define('path', default="/data/web/static/", type=str, help="recommend default one")

# app key
define("app_name", default="lebang", help="app name")
define("app_key", default="20111106001", help="app key")
define("app_secret", default="9e6306f58b705e44d585d61e500d884d", help="app secret")
define("token_secret", default="bc400ed500605c49a035eead0ee5ef41", help="token secret")


# main logic
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
                url(r'^/update$', UpdatedLoudHandler),
                url(r'^/s$', SearchLoudHandler),
                url(r'^/l/(?P<lid>[1-9]\d*|)$', LoudHandler, name='louds'),
                url(r'^/u/(?P<uid>[1-9]\d*|)$', UserHandler, name='users'),
                url(r'^/login$', LoginHandler),
                url(r'^/prize/(?P<pid>[1-9]\d*|)$', PrizeHandler, name='prizes'),
                url(r'^/auth/(?P<aid>[1-9]\d*|)$', AuthHandler, name='auths'),
                url(r'^/app/(?P<aid>[1-9]\d*|)$', AppHandler, name='apps'),
                url(r'^/reply/(?P<aid>[1-9]\d*|)$', AuthHandler, name='replies'),
                url(r'^/upload$', UploadHandler),
                ]
        settings = dict(
                static_path=os.path.join(os.path.dirname(__file__), 'static'),
                debug=True,
                )
        super(Application, self).__init__(handlers, **settings)

        # sqlalchemy session 'db'
        self.db_session = (scoped_session(sessionmaker(autoflush=True, bind=create_engine(options.db_uri))))()
        # redis connection
        self.redis = redis.Redis(host="localhost", port=6379, db=0)


def main():
    tornado.options.parse_command_line()

    app = Application()

    # init the modual
    sql_db.init_app(app)

    # server 
    http_server = tornado.httpserver.HTTPServer(app, xheaders=True)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
