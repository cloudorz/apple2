# coding: utf-8

import tornado.web
from tornado.web import HTTPError

from apps import BaseRequestHandler
from apps.models import User
from utils.decorator import authenticated, validclient, admin
from utils.tools import QDict


class AdminAvatarHandler(BaseRequestHandler):

    @authenticated
    @admin
    def get(self, uk):
        if uk:
            user = User.query.get_by_userkey(uk)
            if user and user.id > 0:
                info = user.user2dict4right()
                self.render_json(info)
            else:
                raise HTTPError(404)
        else:
            q = QDict(
                    q=self.get_argument('q', ""),
                    sort=self.get_argument('qs'),
                    start=int(self.get_argument('st')),
                    num=int(self.get_argument('qn')),
                    )

            query_users = User.query

            if q.q:
                query_users = query_users.filter(User.userkey.like(q.q+'%'))

            # composite the results collection
            total = query_users.count()
            query_dict = {
                    'q': q.q,
                    'qs': q.sort,
                    'st': q.start,
                    'qn': q.num,
                    }

            user_collection = {
                    'users': [e.user2dict4right() for e in query_users.order_by(q.sort).limit(q.num).offset(q.start)],
                    'total': total,
                    'link': self.full_uri(query_dict),
                    }

            if q.start + q.num < total:
                query_dict['st'] = q.start + q.num
                user_collection['next'] = self.full_uri(query_dict)

            if q.start > 0:
                query_dict['st'] = max(q.start - q.num, 0)
                user_collection['prev'] = self.full_uri(query_dict)

            self.render_json(user_collection)

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
