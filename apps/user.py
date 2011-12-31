# coding: utf-8

import uuid, re

from tornado.web import HTTPError
from tornado.options import options

from apps import BaseRequestHandler
from apps.models import User, Loud
from utils.decorator import authenticated, validclient
from utils.imagepp import save_images
from utils.sp import sms_send, ret_code2desc
from utils.tools import generate_password, QDict, make_md5
from utils.escape import json_encode, json_decode


class UserHandler(BaseRequestHandler):

    @authenticated
    def get(self, uid):
        if uid:
            user = User.query.get(uid)

            if user:
                info = user.user2dict()
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
                query_users = query_users.filter(User.name.like('%'+q.q+'%'))

            # composite the results collection
            total = query_users.count()
            query_dict = {
                    'q': q.q,
                    'qs': q.sort,
                    'st': q.start,
                    'qn': q.num,
                    }

            user_collection = {
                    'users': [e.user2dict() for e in query_users.order_by(q.sort).limit(q.num).offset(q.start)],
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
    def put(self, uid):
        ''' The User object can't modify phone
        '''
        user = User.query.get(uid)
        if not user: raise HTTPError(404)

        data = self.get_data()
        if self.current_user.is_admin or \
                user.owner_by(self.current_user) and \
                not ({'userkey', 'role', 'token'} & set(data)):
            user.from_dict(data)
            user.save()
        else:
            raise HTTPError(403, "No permission.")

        self.set_status(200)
        self.finish()

    @authenticated
    def delete(self, uid):
        # PS: delete all relation data user_id = 0
        user = User.query.get(uid)

        if user:
            if user.admin_by(self.current_user):
                self.db.delete(user) 
                self.db.commit()
            else:
                raise HTTPError(403, "No permission.")

        self.set_status(200)
        self.finish()


class UploadHandler(BaseRequestHandler):
    # TODO wait for test

    @validclient
    def post(self):
        if 'photo' in self.request.files:
            if not save_images(self.request.files['photo']):
                raise HTTPError(501, "save image error.")
        else:
            raise HTTPError(400)

        self.finish()
