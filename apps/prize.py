# coding: utf-8

from tornado.web import HTTPError
from tornado.options import options

from apps import BaseRequestHandler
from apps.models import User, Loud, Prize
from utils.decorator import authenticated, validclient
from utils.tools import QDict, make_md5
from utils.escape import json_encode, json_decode

class PrizeHandler(BaseRequestHandler):

    @authenticated
    def get(self, pid):
        if pid:
            prize = Prize.query.get(pid)
            if not prize: raise HTTPError(404)

            info = prize.prize2dict()
            self.render_json(info)
        else:
            q = QDict(
                    uid=self.get_argument('uid'),
                    sort=self.get_argument('qs'),
                    start=int(self.get_argument('st')),
                    num=int(self.get_argument('qn')),
                    )
            query_prizes = Prize.query.filter(user_id==q.uid)

            total = query_prizes.count()
            query_dict = {
                    'uid': q.uid,
                    'qs': q.sort,
                    'st': q.start,
                    'qn': q.num,
                    }

            prize_collection = {
                    'prizes': [e.reply2dict() for e in query_prizes.order_by(q.sort).limit(q.num).offset(q.start)],
                    'total': total,
                    'link': self.full_uri(query_dict),
                    }

            if q.start + q.num < total:
                query_dict['st'] = q.start + q.num
                reply_collection['next'] = self.full_uri(query_dict)

            if q.start > 0:
                query_dict['st'] = max(q.start - q.num, 0)
                reply_collection['prev'] = self.full_uri(query_dict)
           
            self.render_json(prize_collection)


    @authenticated
    def post(self, pid):
        data = self.get_data()

        reply_data = self.get_data()
        if not {'loud_urn', 'user_urn', 'content', 'has_star'} <= set(data):
            raise HTTPError(400, "Bad Request, miss Argument")

        prize = Prize()
        prefix, prize.user_id = data['user_urn'].rsplit(':', 1)
        prefix, prize.loud_id = data['loud_urn'].rsplit(':', 1)
        prize.from_dict(data)

        if prize.save():
            # TODO some thing more 
            # down change the loud status
            self.set_status(201)
            self.set_header('Location', prize.get_link('loud_id'))
        else:
            raise HTTPError(400, "Save the data error.")
