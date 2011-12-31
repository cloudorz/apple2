# coding: utf-8

import hashlib, datetime, sys
import logging

import tornado.httpclient
from tornado.web import HTTPError
from tornado.options import options

from apps import BaseRequestHandler
from apps.models import User, Loud
from utils.decorator import authenticated
from utils.tools import QDict


class LoudHandler(BaseRequestHandler):

    @authenticated
    def get(self, lid):
        loud = Loud.query.get(lid)

        if loud:
            loud_dict = loud.loud2dict()
            self.render_json(loud_dict)
        else:
            self.set_status(404)
            self.finish()

    @authenticated
    @tornado.web.asynchronous
    def post(self, lid):

        self.loud_data = self.get_data()
        lat, lon = self.loud_data['lat'], self.loud_data['lon']

        mars_location_uri = "%s%s" % (options.geo_uri, '/e2m/%f,%f' % (lat, lon))
        http_client = tornado.httpclient.AsyncHTTPClient()
        http_client.fetch(mars_location_uri, callback=self.on_e2m_fetch)

    def on_e2m_fetch(self, rsp):

        if rsp.error:
            msg = "Error response %s fetching %s" % (rsp.error, rsp.request.url)
            logging.warning(msg)
            raise HTTPError(500, msg)

        geo = self.dejson(rsp.body)
        self.loud_data['flat'], self.loud_data['flon'] = geo.values()

        mars_addr_uri = "%s%s" % (options.geo_uri, '/m2addr/%f,%f' % (geo['lat'], geo['lon']))
        http_client = tornado.httpclient.AsyncHTTPClient()
        http_client.fetch(mars_addr_uri, callback=self.on_m2addr_fetch)

    def on_m2addr_fetch(self, rsp):

        if rsp.error:
            msg = "Error response %s fetching %s" % (rsp.error, rsp.request.url)
            logging.warning(msg)
            raise HTTPError(500, msg)

        if rsp.body:
            policital, self.loud_data['address'] = rsp.body.split('#')

        loud = Loud()
        loud.user_id = self.current_user.id

        #if self.current_user.is_admin:
        #    # admin's loud loud category is 'sys'
        #    self.loud_data['loudcate'] = 'sys'

        loud.from_dict(self.loud_data)

        if loud.save():
            self.set_status(201)
            self.set_header('Location', loud.get_link())
        else:
            self.set_status(400)

        self.finish()

    @authenticated
    def put(self, lid):

        loud = Loud.query.get(lid)
        if loud and loud.admin_by(self.current_user):
            data = self.get_data()
            loud.from_dict(data)
            loud.save()
        else:
            raise HTTPError(403, "The loud is not existed or No permission to operate")

        self.set_status(200)
        self.finish()

    @authenticated
    def delete(self, lid):
        loud = Loud.query.get(lid)
        if loud and loud.admin_by(self.current_user):
            self.db.delete(loud)
            self.db.commit()

        self.set_status(200)
        self.finish()


class SearchLoudHandler(BaseRequestHandler):
    # wait for test TODO

    @authenticated
    def get(self):
        condition = self.get_argument('q')
        if ':' in condition:
            field, value = condition.split(':')
        else:
            raise HTTPError(400, "condition's format field:value")

        handle_q = {
                'author': lambda userkey: Loud.query\
                        .filter(Loud.user.has(User.userkey==userkey)),
                'position': lambda data: Loud.query\
                        .get_by_cycle2(*data.split(',')),
                'key': lambda data: Loud.query\
                        .get_by_cycle_key(*data.split(',')),
                }

        if field in handle_q:
            q = QDict(
                    q=condition,
                    v=value,
                    sort=self.get_argument('qs'),
                    start=int(self.get_argument('st')),
                    num=int(self.get_argument('qn')),
                    )
            query_louds = handle_q[field](q.v)

            gmt_now = datetime.datetime.utcnow()
            self.set_header('Last-Modified', gmt_now.strftime('%a, %d %b %Y %H:%M:%S GMT'))

            # composite the results collection
            total = query_louds.count()
            query_dict = {
                    'q': q.q,
                    'qs': q.sort,
                    'st': q.start,
                    'qn': q.num,
                    }

            loud_collection = {
                    'louds': [e.loud2dict() for e in query_louds.order_by(q.sort).limit(q.num).offset(q.start)],
                    'total': total,
                    'link': self.full_uri(query_dict),
                    }

            if q.start + q.num < total:
                query_dict['st'] = q.start + q.num
                loud_collection['next'] = self.full_uri(query_dict)

            if q.start > 0:
                query_dict['st'] = max(q.start - q.num, 0)
                loud_collection['prev'] = self.full_uri(query_dict)

            # make etag prepare
            self.cur_louds = loud_collection['louds']
        else:
            raise HTTPError(400, "Bad Request, search condtion is not allowed.")

        self.render_json(loud_collection)
    
    def compute_etag(self):

        hasher = hashlib.sha1()
        if 'cur_louds' in self.__dict__:
            any(hasher.update(e) for e in sorted(loud['id'] for loud in self.cur_louds))

        return '"%s"' % hasher.hexdigest()


class UpdatedLoudHandler(BaseRequestHandler):
    # wait for test TODO

    @authenticated
    def get(self):
        
        lat = self.get_argument('lat')
        lon = self.get_argument('lon')
        new_loud_count = Loud.query.cycle_update(lat, lon, self.last_modified_time).count()

        if new_loud_count <= 0:
            raise HTTPError(304, "Not changed.")

        self.render_json({'count': new_loud_count})

    @property
    def last_modified_time(self):
        ims = self.request.headers.get('If-Modified-Since', None)
        ims_time = datetime.datetime(1970,1,1,0,0)

        if ims:
            ims_time = datetime.datetime.strptime(ims, '%a, %d %b %Y %H:%M:%S %Z')

        return ims_time
