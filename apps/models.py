# coding: utf-8

import datetime, decimal, uuid

from sqlalchemy import sql, Column, String, Integer, Boolean, \
                        DateTime, Float, ForeignKey, Enum, SmallInteger
from sqlalchemy.orm import relation, backref, column_property, synonym
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from tornado.options import options
from tornado.web import HTTPError
from tornado.httputil import url_concat

from utils.coredb import BaseQuery, Base
from utils.escape import json_encode, json_decode
from utils.tools import QDict, make_md5

# using utcnow for all now time
now = datetime.datetime.utcnow
PAYCATE = {
        'food': u"请你吃饭",
        'drink': u"请你喝饮料",
        'movie': u"请你看电影",
        'gift': u"送你小礼物",
        'money': u"现金奖励",
        'other': u"其他",
        }
LOUDCATE = {
        'pinche': u"顺路拼车",
        'delivery': u"征人跑腿",
        'virtual': u"随便问问",
        'handyman': u"来人修理",
        'jobs': u"招贤纳士",
        'other': u"其他",
        }

# Queries
class UserQuery(BaseQuery):

    def get_by_userkey(self, userkey):
        ''' Get user from users table return the User object 
        or Not exisit and Multi exisit return None
        '''
        # FIXME
        try:
            u = self.filter_by(block=False).filter_by(userkey=userkey).one()
            self.session.commit()
        except (NoResultFound, MultipleResultsFound):
            u = None
        except:
            self.session.rollback()
            raise

        #return self.get_users().filter_by(phone=phn).first()
        return u
    

class LoudQuery(BaseQuery):

    def get_or_404(self, lid):
        loud = self.get(lid)
        if not loud: raise HTTPError(404, "此求助信息不存在, 请更新求助列表")
        
        return loud

    def get_by_cycle2(self, user_lat, user_lon):
        return self.get_by_cycle(user_lat, user_lon).filter(Loud.status==Loud.SHOW)

    def cycle_update(self, user_lat, user_lon, updated):
        return self.get_by_cycle(user_lat, user_lon).filter(Loud.updated>=updated)

    def get_by_cycle(self, user_lat, user_lon):

        # geo args
        earth_r, distance = options.er, options.cr

        # ignore user's small movement lat: 55.66m, lon: 54.93m
        user_lat = decimal.Decimal(user_lat).quantize(decimal.Decimal('0.0001'))
        user_lon = decimal.Decimal(user_lon).quantize(decimal.Decimal('0.0001'))

        # mysql functions 
        acos, sin, cos, pi, abs = sql.func.acos, sql.func.sin, sql.func.cos, sql.func.pi, sql.func.abs

        return self.filter(Loud.expired > now()).\
                filter(sql.or_(Loud.loudcate == 'sys',
                    Loud.loudcate == 'virtual',
                    abs(earth_r*acos(sin(user_lat)*sin(Loud.lat)*cos(user_lon-Loud.lon)+cos(user_lat)*cos(Loud.lat))*pi()/180)<distance))

    def get_by_cycle_key(self, user_lat, user_lon, key):
        return self.get_by_cycle2(user_lat, user_lon).filter(Loud.content.like('%'+key+'%'))


class AppQuery(BaseQuery):

    def get_from_redis_or_db(self, appkey):

        key = "app:%s" % appkey
        app_dict = self.rdb.hgetall(key)
        if app_dict:
            app = QDict(app_dict)
        else:
            app = self.get(appkey)
            self.rdb.hmset(key, app.app2auth())

        return app

    
class Device(Base):

    __tablename__ = 'devices'

    _fields = (
            'uid',
            'dtoken',
            'update',
            'created',
            )
    
    uid = Column(String(50), primary_key=True)
    dtoken = Column(String(80))
    updated = Column(DateTime, default=now, onupdate=now)
    created = Column(DateTime, default=now)

    def __init__(self, *args, **kwargs):
        super(Device, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<%s:%s>" % (self.__tablename__, self.uid)

    def __str__(self):
        return "<%s:%s>" % (self.__tablename__, self.uid)

    def can_save(self):
        return self.uid and self.dtoken


class App(Base):

    __tablename__ = 'apps'

    query_class = AppQuery

    _fields = (
            'name',
            'appkey',
            'secret',
            'created',
            )

    appkey = Column(String(30), primary_key=True)
    name = Column(String(20))
    secret = Column(String(32))
    created = Column(DateTime, default=now)

    def __init__(self, *args, **kwargs):
        super(App, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<%s:%s>" % (self.__tablename__, self.appkey)

    def __str__(self):
        return "<%s:%s>" % (self.__tablename__, self.appkey)

    def can_save(self):
        return self.name and self.appkey and self.secret

    def generate_secret(self):
        self.secret = uuid.uuid4().get_hex()

    def app2dict(self):
        include = ['name', 'appkey', 'secret', 'created']
        info = self.to_dict(include)
        info['id'] = self.get_urn('appkey')
        info['link'] = self.get_link('appkey')

        return info

    def app2auth(self):
        include = ['name', 'appkey', 'secret', 'created']
        info = self.to_dict(include)

        return info


class Auth(Base):
    __tablename__ = 'auths'

    _fields = (
            'site_user_id',
            'user_id', 
            'site_label',
            'access_token',
            'access_secret',
            'expired',
            'updated',
            'created',
            )

    WEIBO, RENREN, DOUBAN = 'weibo', 'renren', 'douban'

    site_user_id = Column(String(30), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"))
    site_label = Column(String(20))
    access_token = Column(String(64))
    access_secret = Column(String(64))
    expired = Column(Integer, default=-1)
    updated = Column(DateTime, default=now, onupdate=now)
    created = Column(DateTime, default=now)

    user = relation('User', backref=backref('auths', order_by=created,  cascade="all, delete, delete-orphan"))

    def __init__(self, *args, **kwargs):
        super(Auth, self).__init__(*args, **kwargs)

    def can_save(self):
        return self.user_id and self.site_user_id \
                and self.access_token  and self.access_secret

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    def get_outer_id(self):
        return self.site_user_id[len(self.site_label)+1:]

    def __repr__(self):
        return "<%s:%s>" % (self.__tablename__, self.site_user_id)

    def __str__(self):
        return "<%s:%s>" % (self.__tablename__, self.site_user_id)

    def auth2dict(self):
        include = list(set(self._fields) - {'user_id'})

        info = self.to_dict(include)
        info['id'] = self.get_urn('site_user_id')
        info['link'] = self.get_link()
        info['user'] = self.user.user2dict4link()


class User(Base):
    __tablename__ = 'users'

    _fields = (
            'userkey',
            'secret',
            'name',
            'phone',
            'deviceid',
            'avatar',
            'brief',
            'lat',
            'lon',
            'role',
            'block',
            'updated',
            'created',
            )

    query_class = UserQuery

    USER, MERCHANT, ADMIN = 100, 200, 300

    id = Column(Integer, primary_key=True)
    userkey = Column(String(30), unique=True)
    secret = Column(String(32))
    name = Column(String(20))
    phone = Column(String(15), nullable=True)
    deviceid = Column(String(50))
    avatar = Column(String(100), nullable=True)
    brief = Column(String(70), nullable=True)
    lat = Column(Float, nullable=True, default=-1)
    lon = Column(Float, nullable=True, default=-1)
    #to_help_num int 0
    #be_helped_num int 0
    #star_num int 0
    #loud_num int 0
    role = Column(SmallInteger, default=USER)
    block = Column(Boolean, default=False)
    updated = Column(DateTime, default=now, onupdate=now)
    created = Column(DateTime, default=now)


    def __init__(self, *args, **kwargs):
        super(User, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<%s:%s>" % (self.__tablename__, self.userkey)

    def __str__(self):
        return "<%s:%s>" % (self.__tablename__, self.userkey)

    def can_save(self):
        return self.userkey and self.secret and self.name and self.deviceid

    def owner_by(self, u):
        return u and u.id == self.id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    @property
    def is_admin(self):
        return self.role == self.ADMIN

    @property
    def is_merchant(self):
        return self.role == self.MERCHANT

    def authenticate(self, secret):
        return self.secret == secret

    def user2dict(self):
        include=['name', 'avatar', 'phone', 'brief',
                'block', 'role', 'updated', 'created']

        info = self.to_dict(include)
        info['id'] = self.get_urn()
        info['link'] = self.get_link()
        info['avatar_link'] = self.get_avatar_link()
        info['loud_num'] = self.loud_num
        info['star_num'] = self.star_num
        info['to_help_num'] = self.to_help_num
        info['be_helped_num'] = self.be_helped_num
        #info['prizes_link'] = url_concat('%s%s' % 
        #       (options.site_uri, self.reverse_uri(Prize.__tablename__, "")),
        #       {'uid': self.id, 'qs': "created desc", 'st': 0, 'qn': 20})

        return info

    def user2dict4auth(self):

        include = ['name', 'secret', 'userkey', 'updated', 'phone', 'brief']
        info = self.to_dict(include)
        info['id'] = self.get_urn()
        info['link'] = self.get_link()
        info['avatar_link'] = self.get_avatar_link()
        info['auths'] = {e.site_label:e.get_link('site_user_id') for e in self.auths}

        return info

    def user2dict4redis(self):
        info = self.to_dict(include=['name', 'phone', 'id', 'role'])
        return info

    def user2dict4link(self, *args):
        include = {'name'}
        if args:
            include.update(args)

        info = self.to_dict(include)
        info['id'] = self.get_urn()
        info['link'] = self.get_link()
        info['avatar_link'] = self.get_avatar_link()

        for e in args:
            if e.endswith('_num'):
                info[e] = getattr(self, e)

        return info

    def user2dict4right(self):
        info = self.to_dict({'userkey', 'secret', 'name'})
        info['id'] = self.get_urn()
        info['link'] = self.get_link()

        return info

    def get_avatar_link(self):
        link = ''
        if self.avatar:
            if self.avatar.startswith('http://'):
                link = self.avatar
            else:
                link = "%s/%s" % (options.static_uri, self.avatar)

        return link

    def generate_avatar_path(self):
        self.avatar = 'i/%s.jpg' % self.userkey

    def generate_secret(self):
        self.secret = uuid.uuid4().get_hex()


class Prize(Base):
    __tablename__ = 'prizes'

    _fields = (
            'user_id',
            'loud_id',
            'content',
            'has_star',
            'created',
            )

    #id = Column(Integer, primary_key=True)
    loud_id = Column(Integer, ForeignKey('louds.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    content = Column(String(70), nullable=True)
    has_star = Column(Boolean, default=False)
    created = Column(DateTime, default=now)

    user = relation('User', backref=backref('prizes', order_by=created, cascade="all, delete, delete-orphan"))
    loud = relation('Loud', backref=backref('prizes', cascade="all, delete, delete-orphan"))

    def __init__(self, *args, **kwargs):
        super(Prize, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<%s:%s>" % (self.__tablename__, self.loud_id)

    def __str__(self):
        return "<%s:%s>" % (self.__tablename__, self.loud_id)

    def can_save(self):
        return self.user_id and self.loud_id

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    def prize2dict(self):
        include = ['content', 'has_star', 'created']

        info = self.to_dict(include)
        info['id'] = self.get_urn('loud_id')
        info['link'] = self.get_link('loud_id')
        info['provider'] = self.loud.user.user2dict4link()
        #info['loud'] = self.loud.loud2dict()

        return info


class Reply(Base):
    __tablename__ = 'replies'

    _fields = (
            'user_id',
            'loud_id',
            'content',
            'lat',
            'lon',
            'flat',
            'flon',
            'address',
            'is_help',
            'created',
            )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    loud_id = Column(Integer, ForeignKey('louds.id', ondelete='CASCADE'))
    content = Column(String(70))
    lat = Column(Float, default=0)
    lon = Column(Float, default=0)
    flat = Column(Float, default=0, nullable=True)
    flon = Column(Float, default=0, nullable=True)
    address = Column(String(30), nullable=True)
    is_help = Column(Boolean)
    created = Column(DateTime, default=now)

    user = relation('User', backref=backref('replies', order_by=created,  cascade="all, delete, delete-orphan"))
    loud = relation('Loud', backref=backref('replies', order_by=created,  cascade="all, delete, delete-orphan"))

    def __init__(self, *args, **kwargs):
        super(Reply, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<%s:%s>" % (self.__tablename__, self.id)

    def __str__(self):
        return "<%s:%s>" % (self.__tablename__, self.id)

    def can_save(self):
        return self.user_id and self.loud_id and self.content \
                and self.lat and self.lon \
                and (self.is_help == True or self.is_help == False)

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    def reply2dict(self):
        include = list(set(self._fields) - {'user_id', 'loud_id'})

        info = self.to_dict(include)
        info['id'] = self.get_urn()
        info['link'] = self.get_link()
        if self.is_help:
            info['user'] = self.user.user2dict4link('phone')
        else:
            info['user'] = self.user.user2dict4link()

        #info['loud'] = self.loud.loud2dict()

        return info


class Loud(Base):
    __tablename__ = 'louds'

    _fields = (
            'user_id',
            'paycate',
            'paydesc',
            'loudcate',
            'content',
            'lat',
            'lon',
            'flat',
            'flon',
            'address',
            'status',
            'expired',
            'updated',
            'created',
            )

    query_class = LoudQuery

    # P.S overdue can't to test for status
    ERR, OVERDUE, SHOW, DONE = 0, 100, 200, 300

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"))
    content = Column(String(70))
    paycate = Column(String(10))
    paydesc = Column(String(30), nullable=True)
    loudcate = Column(String(10))
    lat = Column(Float, default=0)
    lon = Column(Float, default=0)
    flat = Column(Float, default=0, nullable=True)
    flon = Column(Float, default=0, nullable=True)
    address = Column(String(30), nullable=True)
    status = Column(SmallInteger, default=SHOW)
    expired = Column(DateTime) # TODO some default?
    updated = Column(DateTime, default=now, onupdate=now)
    created = Column(DateTime, default=now)

    # on delete CASCADE make me a lots to fix it. 
    # use this feature you must do two things:
    # 1) Column ForeignKey set ondelete keyword for database level 
    # 2) mapper on relation set cascade keyword in parent Model for sqlalchemy session level 
    user = relation('User', backref=backref('louds', order_by=created,  cascade="all, delete, delete-orphan"))

    def __init__(self, *args, **kwargs):
        super(Loud, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<%s:%s>" % (self.__tablename__, self.id)

    def __str__(self):
        return "<%s:%s>" % (self.__tablename__, self.id)

    def can_save(self):
        return self.user_id and self.content and self.lat and self.lon \
                and self.paycate and self.loudcate and self.expired

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    def is_past_due(self):
        return self.expired < now()

    def be_done(self):
        return self.status == self.DONE
    
    def loud2dict(self):
        include = set(self._fields) - {'user_id'}

        info = self.to_dict(include)
        info['id'] = self.get_urn()
        info['link'] = self.get_link()
        info['user'] = self.user.user2dict4link('role', 'to_help_num', 'star_num')
        info['reply_num'] = self.reply_num
        info['help_num'] = self.help_num
        info['replies_link'] = url_concat('%s%s' % 
               (options.site_uri, self.reverse_uri(Reply.__tablename__, "")),
                {'lid': self.id, 'qs': "created desc", 'st': 0, 'qn': 20})

        return info



# user's all louds number

    def loud2dict4sns(self, auth):

        pay = PAYCATE[self.paycate]
        if self.paydesc and self.paydesc.strip():
            pay += ',' + self.paydesc
        
        if auth.site_label == auth.WEIBO:
            suffix = u'@-乐帮-'
        elif auth.site_label == auth.DOUBAN:
            suffix = u'关注乐帮小站http://site.douban.com/135015/'
        elif auth.site_label == auth.RENREN:
            suffix = u'@乐帮'
        else:
            suffix = u''

        info = {
                'content': u"#%s# %s 报酬:%s #%s# %s" % (LOUDCATE[self.loudcate], self.content, pay, self.address, suffix),
                }

        return info



# user's all louds number
User.loud_num = column_property(sql.select([sql.func.count(Loud.id)]).\
        where(Loud.user_id==User.id).as_scalar(), deferred=True)

# user's star num
User.star_num = column_property(sql.select([sql.func.count(Prize.user_id)]).\
        where(sql.and_(Prize.user_id==User.id, Prize.has_star==True)).\
        as_scalar(), deferred=True)

User.be_helped_num = column_property(sql.select([sql.func.count(Loud.user_id)]).\
        where(sql.and_(Loud.user_id==User.id, Loud.status==Loud.DONE)).\
        as_scalar(), deferred=True)

# user's help other num
User.to_help_num = column_property(sql.select([sql.func.count(Prize.user_id)]).\
        where(Prize.user_id==User.id).as_scalar(), deferred=True)

# loud's replies number
Loud.reply_num = column_property(sql.select([sql.func.count(Reply.id)]).\
        where(Reply.loud_id==Loud.id).as_scalar(), deferred=True)

Loud.help_num = column_property(sql.select([sql.func.count(Reply.id)]).\
        where(sql.and_(Reply.loud_id==Loud.id, Reply.is_help==True)).as_scalar(), deferred=True)
