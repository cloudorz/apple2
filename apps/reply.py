# coding: utf-8


from tornado.web import HTTPError
from tornado.options import options

from apps import BaseRequestHandler
from apps.models import User, Loud, Reply
from utils.decorator import authenticated, availabelclient
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
    def post(self, rid):

        self.reply_data = self.get_data()
        lat, lon = self.reply_data['lat'], self.reply_data['lon']

        mars_location_uri = "%s%s" % (options.geo_uri, '/e2m/%f,%f' % (lat, lon))
        http_client = tornado.httpclient.AsyncHTTPClient()
        http_client.fetch(mars_location_uri, callback=self.on_e2m_fetch)
        
    def on_e2m_fetch(self, rsp):
        if rsp.error: raise HTTPError(500)

        geo = self.dejson(rsp.body)
        self.reply_data['flat'], self.reply_data['flon'] = geo.values()

        mars_addr_uri = "%s%s" % (options.geo_uri, '/m2addr/%f,%f' % (geo['lat'], geo['lon']))
        http_client = tornado.httpclient.AsyncHTTPClient()
        http_client.fetch(mars_addr_uri, callback=self.on_m2addr_fetch)

    def on_m2addr_fetch(self, rsp):
        if rsp.error: raise HTTPError(500)

        if rsp.body:
            policital, self.reply_data['address'] = rsp.body.split('#')

        reply = Reply()
        reply.user_id = self.current_user.id

        reply.from_dict(self.reply_data)

        if reply.save():
            self.set_status(201)
            self.set_header('Location', reply.get_link('reply'))
        else:
            self.set_status(400)

        self.finish()

