# coding: utf-8


from tornado import gen
from tornado.web import asynchronous, HTTPError
from tornado.options import options

from apps import BaseRequestHandler
from apps.models import User, Loud, Reply
from utils.decorator import authenticated, validclient
from utils.tools import generate_password, QDict, make_md5
from utils.escape import json_encode, json_decode


class ReplyHandler(BaseRequestHandler):

    @authenticated
    def get(self, rid):
        if rid:
            reply = Reply.query.get(rid)
            if not reply: raise HTTPError(404)

            info = reply.reply2dict()
            self.render_json(info)
        else:
            q = QDict(
                    lid=self.get_argument('lid'),
                    sort=self.get_argument('qs'),
                    start=int(self.get_argument('st')),
                    num=int(self.get_argument('qn')),
                    )
            query_replies = Reply.query.filter(loud_id==q.lid)

            total = query_replies.count()
            query_dict = {
                    'lid': q.lid,
                    'qs': q.sort,
                    'st': q.start,
                    'qn': q.num,
                    }

            reply_collection = {
                    'replies': [e.reply2dict() for e in query_replies.order_by(q.sort).limit(q.num).offset(q.start)],
                    'total': total,
                    'link': self.full_uri(query_dict),
                    }

            if q.start + q.num < total:
                query_dict['st'] = q.start + q.num
                reply_collection['next'] = self.full_uri(query_dict)

            if q.start > 0:
                query_dict['st'] = max(q.start - q.num, 0)
                reply_collection['prev'] = self.full_uri(query_dict)
           
            self.render_json(reply_collection)

    @authenticated
    @asynchronous
    @gen.engine
    def post(self, rid):

        reply_data = self.get_data()
        http_client = tornado.httpclient.AsyncHTTPClient()

        lat, lon = reply_data['lat'], reply_data['lon']
        mars_location_uri = "%s/e2m/%f,%f" % (options.geo_uri, reply_data['lat'], reply_data['lon'])

        # first request for mars location
        location_rsp = yield gen.Task(http_client.fetch, mars_location_uri)

        reply_data['flat'], reply_data['flon'] = reply_data['lat'], reply_data['lon']
        if not location_rsp.error:
            try:
                geo = self.dejson(location_rsp.body)
                reply_data['flat'], reply_data['flon'] = geo['lat'], geo['lon']
            except (ValueError, TypeError):
                pass

        mars_addr_uri = "%s/m2addr/%f,%f" % (options.geo_uri, reply_data['flat'], reply_data['flon'])

        # second reuest for address for mars location
        addr_rsp = yield gen.Task(http_client.fetch, mars_addr_uri)

        if not addr_rsp.error and addr_rsp.body:
            policital, reply_data['address'] = addr_rsp.body.split('#')

        reply = reply()
        reply.user_id = self.current_user.id

        reply.from_dict(reply_data)

        if reply.save():
            self.set_status(201)
            self.set_header('Location', reply.get_link())
        else:
            raise HTTPError(500, "Save data error.")

        self.finish()
