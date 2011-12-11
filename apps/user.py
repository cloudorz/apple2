# coding: utf-8

import uuid, datetime, re

from tornado.web import HTTPError
from tornado.options import options

from apps import BaseRequestHandler
from apps.models import User, Loud
from utils.decorator import authenticated, availabelclient
from utils.imagepp import save_images
from utils.sp import sms_send, ret_code2desc
from utils.tools import generate_password, QDict, make_md5
from utils.escape import json_encode, json_decode

class UserHandler(BaseRequestHandler):
    # wait for test TODO

    @authenticated
    def get(self, uid):
        if uid:
            user = User.query.get(uid)

            if user:
                info = user.user2dict()
                self.render_json(info)
            else:
                self.set_status(404)
                self.finsh()

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

            return self.render_json(user_collection)

    @availabelclient
    def post(self, phn):
        user = User()

        data = self.get_data()
        user.from_dict(data)
        # after the phone set in
        user.generate_avatar_path()

        if user.save():
            self.set_status(201)
            self.set_header('Location', user.get_link())
        else:
            self.set_status(400)

        self.finsh()

    @authenticated
    def put(self, uid):
        ''' The User object can't modify phone
        '''
        user = User.query.get(uid)
        if not user: raise HTTPError(404)

        data = self.get_data()
        if self.current_user.is_admin and \
                user.owner_by(self.current_user) and \
                not ({'email, is_admin, token'} & set(data)):
            user.from_dict(data)
            user.save()
        else:
            self.set_status(403)

        self.finsh()

    @authenticated
    def delete(self, uid):
        # PS: delete all relation data user_id = 0
        user = User.query.get(uid)
        if not user: raise HTTPError(404)

        if user.admin_by(self.current_user):
            self.db.delete(user) 
            self.db.commit()

        self.finsh()


class AuthHandler(BaseRequestHandler):
    # TODO wait for change

    @availabelclient
    def post(self):
        new_info = self.get_data()
        if 'phone' in new_info and 'password' in new_info:
            user = User.query.get_by_phone(new_info['phone'])
            if user and user.authenticate(new_info['password']):
                user.token = uuid.uuid5(uuid.NAMESPACE_URL, "%s%s" % (user.phone,
                    options.token_secret)).hex

                info = user.user2dict_by_auth() # must before save
		key = 'users:%s' % user.token
                self.rdb.set(key, json_encode(user.user2dict4redis()))
                self.rdb.expire(key, 3600)

                user.save()

                self.render_json(info) 
                return 
            else:
                self.set_status(406)
                msg = self.message("Password or phone is not correct.")
        else:
            self.set_status(400)
            msg = self.message("phone, password field required.")

        self.render_json(msg)


class UploadHandler(BaseRequestHandler):
    # TODO wait for test

    @availabelclient
    def post(self):
        if 'photo' in self.request.files:
            if not save_images(self.request.files['photo']):
                self.set_status(501)
        else:
            self.set_status(400)

        self.finsh()
