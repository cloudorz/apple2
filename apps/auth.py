# coding: utf-8

from tornado.web import HTTPError

from apps import BaseRequestHandler
from apps.models import User, Loud, Auth, App
from utils.decorator import authenticated, availabelclient, admin
from utils.escape import json_encode, json_decode


class AuthHandler(BaseRequestHandler):

    @authenticated
    def get(self, aid):
        if aid:
            auth = Auth.query.get(aid)
            if not auth: raise HTTPError(404)

            if self.current_user.is_admin or \
                    auth.owner_by(self.current_user):
                info = auth.auth2dict()
                self.render_json(info)
            else:
                raise HTTPError(404)
        else:
            # TODO add admin get all auths
            auth_collection = {
                    'auths': [e.auth2dict() for e in self.current_user.auths],
                    'total': self.current_user.count(),
                    'link': self.full_uri(),
                    }

            self.render_json(auth_collection)

    @authenticated
    def post(self, aid):
        auth = Auth()

        data = self.get_data()
        auth.from_dict(data)

        auth.user_id = self.current_user.id

        if auth.save():
            self.set_status(201)
            self.set_header('Location', auth.get_link())
        else:
            raise HTTPError(400)

        self.finish()

    @authenticated
    def put(self, aid):

        auth = Auth.query.get(aid)

        if not auth: raise HTTPError(404)
        
        data = self.get_data()
        if self.current_user.is_admin or \
                auth.owner_by(self.current_user) and \
                not ({'app_id', 'user_id'}) & set(data):
            auth.from_dict(data)
            auth.save()
        else:
            raise HTTPError(403)

        self.set_status(200)
        self.finish()

    @authenticated
    def delete(self, aid):
        auth = Auth.query.get(aid)
        if not auth: raise HTTPError(404)

        if auth.admin_by(self.current_user):
            self.db.delete(auth)
            self.db.commit()
        else:
            raise HTTPError(403)

        self.set_status(200)
        self.finish()


class AppHandler(BaseRequestHandler):
    
    @authenticated
    @admin
    def get(self, aid):
        if aid:
            app = App.query.get(aid)
            if not app: raise HTTPError(404)

            info = app.app2dict()
            self.render_json(info)
        else:
            app_collection = {
                    'apps': [e.app2dict() for e in App.query.all()],
                    'total': App.query.count(),
                    'link': self.full_uri(),
                    }
            self.render_json(app_collection)

    @authenticated
    @admin
    def post(self, aid):
        data = self.get_data()

        app = App()
        app.from_dict(data)

        if app.save():
            self.set_status(201)
            self.set_header('Location', app.get_link())
        else:
            raise HTTPError(400)

        self.finish()

    @authenticated
    @admin
    def put(self, aid):
        app = App.query.get(aid)
        if not app: raise HTTPError(404)

        if app.admin_by(self.current_user):
            data = self.get_data()
            app.from_dict(data)
            app.save()
        else:
            raise HTTPError(403)

        self.set_status(200)
        self.finish()

    @authenticated
    @admin
    def delete(self, aid):
        app =App.query.get(aid)
        if not app: raise HTTPError(404)

        if app.admin_by(self.current_user):
            self.db.delete(app)
            self.db.commit()
        else:
            raise HTTPError(403)

        self.set_status(200)
        self.finish()
