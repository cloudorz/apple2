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

from apps.loud import LoudHandler, SearchLoudHandler, OfferHelpUsersHandler
from apps.user import UserHandler, UploadHandler
from apps.auth import AuthHandler, DoubanHandler, WeiboHandler, RenrenHandler
from apps.app import AppClientHandler, DeviceHandler
from apps.prize import PrizeHandler
from apps.reply import ReplyHandler
from apps.admin import AdminAvatarHandler, CheckAdminHandler
from apps.notify import MessageHandler, LoudUpdatedHandler, MessageUpdatedHandler, PrizeUpdatedhandler
from apps.rdbm import rdb_init_app
from utils.coredb import sql_db

# server
define('port', default=8000, help="run on the given port", type=int)

#URI
define('site_uri', default="http://i.n2u.in", type=str, help="site uri") 
define('static_uri', default="http://s.n2u.in", type=str, help="static uri")
#define('site_uri', default="http://192.168.0.124", type=str, help="site uri") 
#define('static_uri', default="http://192.168.0.124/static", type=str, help="static uri")
define('geo_uri', default="http://l.n2u.in", type=str, help="locaiton and address parser uri")
define('mquri', default="http://localhost:8888/", type=str, help="restmq uri")

#args
define('er', default=6378137, type=float, help="the earth radius.")
define('cr', default=3000, type=float, help="the cycle radius.")

# database
define('db_uri', default="mysql://root:123@localhost/apple2?charset=utf8", type=str, help="connect to mysql")

# avatar dir  path
define('path', default="/data/web/help_static/", type=str, help="recommend default one")


# main logic
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
                url(r'^/s$', SearchLoudHandler),
                url(r'^/l/(?P<lid>[1-9]\d*|)$', LoudHandler, name='louds'),
                url(r'^/u/(?P<uid>[1-9]\d*|)$', UserHandler, name='users'),
                url(r'^/prize/(?P<pid>[1-9]\d*|)$', PrizeHandler, name='prizes'),
                url(r'^/auth/(?P<aid>\w+_\w+|)$', AuthHandler, name='auths'),
                url(r'^/app/(?P<aid>\w+|)$', AppClientHandler, name='apps'),
                url(r'^/reply/(?P<rid>[1-9]\d*|)$', ReplyHandler, name='replies'),
                url(r'^/offer-help-users/urn:louds:(?P<lid>[1-9]\d*)', OfferHelpUsersHandler),
                url(r'^/upload$', UploadHandler),
                url(r'^/device/(?P<uid>[0-9a-z]+)$', DeviceHandler, name='devices'),
                url(r'^/loudupdate$', LoudUpdatedHandler),
                url(r'^/msgupdate$', MessageUpdatedHandler),
                url(r'^/prizeupdate$', PrizeUpdatedhandler),
                url(r'^/msg/$', MessageHandler),
                # third party login or authorize
                url(r'^/douban/auth$', DoubanHandler, name='douban'),
                url(r'^/weibo/auth$', WeiboHandler, name='weibo'),
                url(r'^/renren/auth$', RenrenHandler, name='renren'),
                # admin 
                url(r'^/admin/avatar/(?P<uk>\w+|)$', AdminAvatarHandler),
                url(r'^/admin/check$', CheckAdminHandler),
                ]
        settings = dict(
                static_path=os.path.join(os.path.dirname(__file__), 'static'),
                # secure cookies
                cookie_secret="5b33a05a25df4609aa6aca4c14c8594b",
                # OAuth's key and secret
                douban_consumer_key="0855a87df29f2eac1900f979d7dd8c04",
                douban_consumer_secret="7524926f6171b225",
                weibo_app_key="563114544",
                weibo_app_secret="ac88e78e4c5037839cbbb9c92369bdef",
                renren_app_key="8f9607b8f2d4446fbc798597dc1dcdd4",
                renren_app_secret="c8bfb41852ae40589f268007205fce13",
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
    rdb_init_app(app)

    # server 
    http_server = tornado.httpserver.HTTPServer(app, xheaders=True)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
