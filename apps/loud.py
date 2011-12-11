# coding: utf-8

import hashlib, datetime, sys

import tornado.httpclient
from tornado.web import HTTPError
from tornado.options import options

from apps import BaseRequestHandler
from apps.models import User, Loud
from utils.decorator import authenticated
from utils.tools import QDict


class LoudHandler(BaseRequestHandler):
    # wait for test TODO

    @authenticated
    def get(self, lid):
        loud = Loud.query.get(lid)

        if loud:
            loud_dict = loud.loud2dict()
            self.render_json(loud_dict)
        else:
            self.set_status(404)
            self.finsh()

    @authenticated
    def post(self, lid):

        # the precondtion the max 3 louds.
        #loud_count = Loud.query.get_louds().filter(Loud.user.has(User.phone==self.current_user.phone)).count()
        #if loud_count >= 3:
        #    raise HTTPError(412)

        data = self.get_data()
        self.wrap_mars_addr(data)

        loud = Loud()
        loud.user_id = self.current_user.id

        if self.current_user.is_admin:
            # admin's loud
            data['grade'] = 0

        loud.from_dict(data)

        if loud.save():
            self.set_status(201)
            self.set_header('Location', loud.get_link())
        else:
            self.set_status(400)

        self.finsh()

    @authenticated
    def delete(self, lid):
        loud = Loud.query.get(lid)
        if loud.admin_by(self.current_user):
            self.db.delete(loud)
            self.db.commit()

        self.finsh()

    def wrap_mars_addr(self, data):

        assert 'lat' in data and 'lon' in data, "The data must have location infomation"
        lat, lon = data['lat'], data['lon']

        flat, flon = self.e2m(lat, lon)
        if flat and flon:
            data['flat'], data['flon'] = flat, flon
            addr = self.m2addr(flat, flon)

            if addr:
                # addrr like 'China,Zhejiang,Hangzhou,xihuqu#yugu.rd218'
                policital, data['address'] = addr.split('#')

    def e2m(self, lat, lon):
        mars_location_uri = "%s%s" % (options.geo_uri, '/e2m/%f,%f' % (lat, lon))
        http = tornado.httpclient.HTTPClient()
        try:
            rsp = http.fetch(mars_location_uri)
        except tornado.httpclient.HTTPError, e:
            res = None, None
        else:
            geo = self.dejson(rsp.body)
            res = geo.get('lat', None), geo.get('lon', None)

        return res

    def m2addr(self, lat, lon):
        mars_addr_uri = "%s%s" % (options.geo_uri, '/m2addr/%f,%f' % (lat, lon))
        http = tornado.httpclient.HTTPClient()
        try:
            rsp = http.fetch(mars_addr_uri)
        except tornado.httpclient.HTTPError, e:
            res = None
        else:
            res = rsp.body

        return res


class SearchLoudHandler(BaseRequestHandler):
    # wait for test TODO

    @authenticated
    def get(self):
        condition = self.get_argument('q')
        if ':' in condition:
            field, value = condition.split(':')
        else:
            raise HTTPError(400)

        handle_q = {
                'author': lambda email: Loud.query\
                        .filter(Loud.user.has(User.email==email)),
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

            gmt_now = datetime.datetime.now() - datetime.timedelta(hours=8)
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
            raise HTTPError(400)

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
            raise HTTPError(304)

        self.render_json({'count': new_loud_count})

    @property
    def last_modified_time(self):
        ims = self.request.headers.get('If-Modified-Since', None)
        ims_time = datetime.datetime(1970,1,1,0,0)

        if ims:
            ims_time = datetime.datetime.strptime(ims, '%a, %d %b %Y %H:%M:%S %Z') + datetime.timedelta(hours=8)

        return ims_time
