# coding: utf-8

import hashlib, logging

import tornado.httpclient

from sqlalchemy import sql

from tornado import gen
from tornado.web import asynchronous, HTTPError
from tornado.options import options

from apps import BaseRequestHandler
from apps.models import User, Loud, Reply, Device, Prize
from apps.rdbm import Message
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
            query_replies = Reply.query.filter(Reply.loud_id==q.lid)
            prizes = Prize.query.filter(Prize.loud_id==q.lid)
            prize_uids = list(set(e.user.get_urn() for e in prizes if e))

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
                    'prizes': prize_uids,
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
        if not {'lat', 'lon', 'content', 'is_help', 'urn'} <= set(reply_data):
            raise HTTPError(400, "Bad Request, miss Argument")

        prefix, loud_id = reply_data['urn'].rsplit(':', 1)

        # the loud precondtion OK
        loud = Loud.query.get_or_404(loud_id)
        if loud.is_past_due():
            self.set_status(412)
            self.render_json({'status': loud.OVERDUE,
                'msg': 'Precondition error, loud status changed'})
            self.finish()
            return

        if loud.be_done():
            self.set_status(412)
            self.render_json({'status': loud.DONE,
                'msg': 'Precondition error, loud status changed'})
            self.finish()
            return

        http_client = tornado.httpclient.AsyncHTTPClient()

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

        reply = Reply()
        reply.user_id = self.current_user.id
        reply.loud_id = loud_id

        reply.from_dict(reply_data)

        # update the user last location
        self.current_user.lat, self.current_user.lon = reply_data['lat'], reply_data['lon']

        if reply.save():
            self.set_status(201)
            self.set_header('Location', reply.get_link())
            relative_users = User.query.filter(
                    sql.or_(
                        sql.and_(
                            User.id==reply.loud.user.id,
                            User.id!=reply.user_id),
                        User.replies.any(sql.and_(
                            Reply.loud_id==reply.loud_id,
                            Reply.user_id!=reply.user_id)
                )))
            msg = Message(reply, [e.id for e in relative_users])
            msg.create()

            # send to apns for help msg
            d = Device.query.get(reply.loud.user.deviceid)
            dtoken = d and d.dtoken
            if dtoken:
                sns_data = {
                        'token': dtoken,
                        'secret': 'apns',
                        'label': "apns",
                        'content': u"@%s 给你提供了帮助" % self.current_user.name,
                        }
                http_client = tornado.httpclient.HTTPClient()
                try:
                    http_client.fetch(
                            options.mquri,
                            body="queue=snspost&value=%s" % self.json(sns_data),
                            method='POST',
                            )
                except httpclient.HTTPError, e:
                    pass
        else:
            raise HTTPError(500, "Save data error.")

        self.finish()
