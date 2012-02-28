# coding: utf-8

import tornado.web
from tornado.web import HTTPError

from apps import BaseRequestHandler
from apps.models import User
from utils.decorator import authenticated, validclient, admin


class AdminAvatarHandler(BaseRequestHandler):

    @authenticated
    @admin
    def get(self, uk):
        user = User.query.get_by_userkey(uk)
        if user:
            info = user.user2dict4right()
            self.render_json(info)
        else:
            raise HTTPError(404)

    @authenticated
    @admin
    def post(self, uk):
        user_data = self.get_data()
        user_data['deviceid'] = "test-test-test"
        user = User()
        user.from_dict(user_data)
        user.generate_secret()
        user.generate_avatar_path()

        if user.save():
            self.set_status(201)
            self.set_header('Location', user.get_link())
        else:
            raise HTTPError(500, 'Save avatar user info error.')

        self.finish()


class CheckAdminHandler(BaseRequestHandler):

    @authenticated
    @admin
    def get(self):
        self.render_json({'msg': 'ok'})
