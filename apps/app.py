# coding: utf-8

import tornado.web

from tornado.web import HTTPError
from tornado.httputil import url_concat
from tornado.options import options

from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from apps import BaseRequestHandler
from apps.models import App
from utils.decorator import authenticated, validclient, admin
from utils.escape import json_encode, json_decode
from utils.tools import QDict

class AppClientHandler(BaseRequestHandler):

    @authenticated
    @admin
    def get(self, aid):
        if aid:
            app = App.query.get(aid)
            if app is None: raise HTTPError(404, 'The app client is not exisited')

            info = app.app2dict()
            self.render_json(info)
        else:
            query_apps = App.query.order_by('created desc')
            app_collection = {
                    'users': [e.app2dict() for e in query_apps],
                    'total': query_apps.count(),
                    'link': self.full_uri(),
                    }

            self.render_json(app_collection)

    @authenticated
    @admin
    def post(self, aid):
        data = self.get_data()

        app = App()
        app.from_dict(data)
        app.generate_secret()
        print data

        if app.save():
            self.set_status(201)
            self.set_header('Location', app.get_link('appkey'))
        else:
            raise HTTPError(500, 'Created fail. wrong arguments or save error.')

        self.finish()

    @authenticated
    @admin
    def delete(self, aid):
        app = App.query.get(aid)

        if app:
            self.db.delete(app)
            self.db.commit()
        
        self.set_status(200)
        self.finish()
