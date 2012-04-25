# coding: utf-8

import hashlib, datetime, logging

import tornado.httpclient

from sqlalchemy import sql

from tornado import gen
from tornado.web import asynchronous, HTTPError
from tornado.options import options
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from apps import BaseRequestHandler
from apps.models import User, Loud, Reply, Auth
from utils.decorator import authenticated
from utils.tools import QDict, pretty_time_str


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
    @asynchronous
    @gen.engine
    def post(self, lid):

        loud_data = self.get_data()
        # if virtual help will 
        if loud_data['loudcate'] == 'virtual':
            loud_data['expired'] += datetime.timedelta(days=365)
        http_client = tornado.httpclient.AsyncHTTPClient()

        mars_location_uri = "%s/e2m/%f,%f" % (options.geo_uri, loud_data['lat'], loud_data['lon'])

        # first request for mars location
        location_rsp = yield gen.Task(http_client.fetch, mars_location_uri)

        loud_data['flat'], loud_data['flon'] = loud_data['lat'], loud_data['lon']
        if not location_rsp.error:
            try:
                geo = self.dejson(location_rsp.body)
                loud_data['flat'], loud_data['flon'] = geo['lat'], geo['lon']
            except (ValueError, TypeError):
                pass

        mars_addr_uri = "%s/m2addr/%f,%f" % (options.geo_uri, loud_data['flat'], loud_data['flon'])

        # second reuest for address for mars location
        addr_rsp = yield gen.Task(http_client.fetch, mars_addr_uri)

        if not addr_rsp.error and addr_rsp.body:
            policital, loud_data['address'] = addr_rsp.body.split('#')

        loud = Loud()
        loud.user_id = self.current_user.id

        #if self.current_user.is_admin:
        #    # admin's loud loud category is 'sys'
        #    loud_data['loudcate'] = 'sys'

        loud.from_dict(loud_data)

        # update the user last location
        self.current_user.lat, self.current_user.lon = loud_data['lat'], loud_data['lon']

        if loud.save():
            self.set_status(201)
            self.set_header('Location', loud.get_link())

            # send to sns
            if loud_data['weibo'] or loud_data['renren'] or loud_data['douban']:
                mqurl = "http://localhost:8888/"

                auth_query = Auth.query.filter(Auth.user_id==self.current_user.id)
                if loud_data['weibo']:
                    try:
                        weibo_auth = auth_query.filter(Auth.site_label==Auth.WEIBO).one()
                    except (NoResultFound, MultipleResultsFound):
                        pass
                    else:
                        sns_data = loud.loud2dict4sns(weibo_auth)
                        sns_data['token'] = weibo_auth.access_token
                        sns_data['secret'] = weibo_auth.access_secret
                        sns_data['label'] = Auth.WEIBO
                        rsp = yield gen.Task(http_client.fetch,
                                mqurl,
                                method='POST',
                                body='queue=snspost&value=%s' % self.json(sns_data),
                                )

                if loud_data['renren']:
                    try:
                        renren_auth = auth_query.filter(Auth.site_label==Auth.RENREN).one()
                    except (NoResultFound, MultipleResultsFound):
                        pass
                    else:
                        sns_data = loud.loud2dict4sns(renren_auth)
                        sns_data['token'] = renren_auth.access_token
                        sns_data['secret'] = renren_auth.access_secret
                        sns_data['label'] = Auth.RENREN
                        rsp = yield gen.Task(http_client.fetch,
                                mqurl,
                                method='POST',
                                body='queue=snspost&value=%s' % self.json(sns_data),
                                )

                if loud_data['douban']:
                    try:
                        douban_auth = auth_query.filter(Auth.site_label==Auth.DOUBAN).one()
                    except (NoResultFound, MultipleResultsFound):
                        pass
                    else:
                        sns_data = loud.loud2dict4sns(douban_auth)
                        sns_data['token'] = douban_auth.access_token
                        sns_data['secret'] = douban_auth.access_secret
                        sns_data['label'] = Auth.DOUBAN
                        rsp = yield gen.Task(http_client.fetch,
                                mqurl,
                                method='POST',
                                body='queue=snspost&value=%s' % self.json(sns_data),
                                )

        else:
            raise HTTPError(500, "Save data error.")

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

    @authenticated
    def get(self):
        condition = self.get_argument('q')
        if ':' in condition:
            field, value = condition.split(':')
        else:
            raise HTTPError(400, "condition's format field:value")

        handle_q = {
                'author': lambda userkey: Loud.query\
                        .filter(Loud.user.has(User.userkey==userkey))\
                        .filter(Loud.status!=Loud.DONE),
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

            gmt_now = datetime.datetime.utcnow()
            self.set_header('Last-Modified', pretty_time_str(gmt_now))
	    # make etag prepare
	    self.cur_louds = loud_collection['louds']

        else:
            raise HTTPError(400, "Bad Request, search condtion is not allowed.")

        self.render_json(loud_collection)

    def compute_etag(self):
        hasher = hashlib.sha1()
	if 'cur_louds' in self.__dict__:
	    any(hasher.update(e) for e in sorted("%s-%s" % (loud['id'], loud['updated']) for loud in self.cur_louds))

        return '"%s"' % hasher.hexdigest()


class OfferHelpUsersHandler(BaseRequestHandler):

    @authenticated
    def get(self, lid):
        #offers = User.query.filter(User.replies.any(sql.and_(Reply.loud_id==lid, Reply.is_help==True)))
        offers = User.query.filter(User.replies.any(sql.and_(Reply.loud_id==lid)))
        offer_list = [e.user2dict4link() for e in offers]

        self.render_json(offer_list)
