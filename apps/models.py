# coding: utf-8

import datetime, hashlib, decimal

from sqlalchemy import sql, Column, String, Integer, Boolean, \
                        DateTime, Float, ForeignKey, Enum, SmallInteger
from sqlalchemy.orm import relation, backref, column_property, synonym
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from tornado.options import options
from tornado.web import HTTPError
from tornado.httputil import url_concat

from utils.coredb import BaseQuery, Base
from utils.escape import json_encode, json_decode


# Queries
class UserQuery(BaseQuery):

    def get_by_email(self, email):
        ''' Get user from users table return the User object 
        or Not exisit and Multi exisit return None
        '''
        # FIXME
        try:
            u = self.filter_by(block=False).filter_by(email=email).one()
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
        if not loud: raise HTTPError(404)
        
        return loud

    def get_by_cycle2(self, user_lat, user_lon):
        return self.get_by_cycle(user_lat, user_lon).filter(Loud.block==False)

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

        return self.filter(sql.or_(Loud.loudcate == 'sys', abs(earth_r*acos(sin(user_lat)*sin(Loud.lat)*cos(user_lon-Loud.lon)+cos(user_lat)*cos(Loud.lat))*pi()/180)<distance))

    def get_by_cycle_key(self, user_lat, user_lon, key):
        return self.get_by_cycle2(user_lat, user_lon).filter(Loud.content.like('%'+key+'%'))


# Models
class Auth(Base):
    __tablename__ = 'auths'

    _fields = (
            'user_id', 
            'app_id',
            'access_token',
            'access_secret',
            'expired',
            'updated',
            'created',
            )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"))
    app_id = Column(Integer, ForeignKey('apps.id', ondelete="CASCADE"))
    access_token = Column(String(64))
    access_secret = Column(String(64))
    expired = Column(Integer)
    updated = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created = Column(DateTime, default=datetime.datetime.now)

    user = relation('User', backref=backref('auths', order_by=created,  cascade="all, delete, delete-orphan"))
    app = relation('App', backref=backref('auths', order_by=created, cascade="all, delete, delete-orphan"))

    def __init__(self, *args, **kwargs):
        super(Auth, self).__init__(*args, **kwargs)

    def can_save(self):
        return self.user_id and self.app_id and self.access_token \
                and self.secret and expired

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    def __repr__(self):
        return "<auth:%s>" % self.key

    def __str__(self):
        return "<auth:%s>" % self.key

    def auth2dict(self):
        include = ['access_token', 'access_secret', 'expired', 'updated', 'created']

        info = self.to_dict(include)
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link()
        info['app'] = self.app.app2dict()
        info['user'] = self.user.user2dict()


class App(Base):
    __tablename__ = 'apps'

    _fields = (
            'name',
            'key',
            'sec',
            'desp',
            )

    id = Column(Integer, primary_key=True)
    name = Column(String(20))
    key = Column(String(20))
    sec = Column(String(32))
    desp = Column(String(100), nullable=True)

    def __init__(self, *args, **kwargs):
        super(App, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<app:%s>" % self.key

    def __str__(self):
        return "<app:%s>" % self.key

    def can_save(self):
        return self.name and self.key and self.sec

    def app2dict(self):
        include = ['name', 'key', 'sec', 'desc']

        info = self.to_dict(include)
        info['link'] = self.get_link()
        info['id'] = self.get_urn_id()


class User(Base):
    __tablename__ = 'users'

    _fields = (
            'email',
            'token',
            'name',
            'phone',
            'avatar',
            'brief',
            'role',
            'block',
            'updated',
            'created',
            )

    query_class = UserQuery

    USER, MERCHANT, ADMIN = 100, 200, 300

    id = Column(Integer, primary_key=True)
    email = Column(String(60), unique=True)
    token = Column(String(32))
    name = Column(String(20))
    phone = Column(String(15), nullable=True)
    avatar = Column(String(100), nullable=True)
    brief = Column(String(70), nullable=True)
    #to_help_num int 0
    #star_num int 0
    #loud_num int 0
    role = Column(SmallInteger, default=USER)
    block = Column(Boolean, default=False)
    updated = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created = Column(DateTime, default=datetime.datetime.now)


    def __init__(self, *args, **kwargs):
        super(User, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<user:%s>" % self.email

    def __str__(self):
        return "<user:%s>" % self.email

    def can_save(self):
        return self.email and self.token and self.name 

    def owner_by(self, u):
        return u and u.id == self.id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    @property
    def is_admin(self):
        return self.role == self.USER

    def authenticate(self, token):
        return self.token == token

    def user2dict(self):
        include=['name', 'avatar', 'phone', 'brief',
                'block', 'role', 'updated', 'created']

        info = self.to_dict(include)
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link()
        info['avatar_link'] = self.get_avatar_link()
        info['loud_num'] = self.loud_num
        info['star_num'] = self.star_num
        info['to_help_num'] = self.to_help_num
        info['prizes_link'] = url_concat('%s%s' % 
               (options.site_uri, self.reverse_uri(Prize.__tablename__, "")),
               {'uid': self.id, 'qs': "created desc", 'st': 0, 'qn': 20})

        return info

    def user2dict4auth(self):
        info = self.to_dict(include=['name', 'token', 'email', 'updated'])
        return info

    def user2dict4redis(self):
        info = self.to_dict(include=['name', 'phone', 'id', 'role'])
        return info

    def user2dict4link(self):
        info = {
                'id': self.get_urn_id(),
                'link': self.get_link(),
                }

        return info

    def get_avatar_link(self):
        return "%s/%s" % (options.static_uri, self.avatar)

    def generate_avatar_path(self):
        if self.email:
            self.avatar = 'i/%s.jpg' % hashlib.md5(str(self.email)).hexdigest()


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
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    loud_id = Column(Integer, ForeignKey('louds.id', ondelete='CASCADE'))
    content = Column(String(70), nullable=True)
    has_star = Column(Boolean, default=False)
    created = Column(DateTime, default=datetime.datetime.now)

    owner = relation('User', backref=backref('prizes', order_by=created, cascade="all, delete, delete-orphan"))
    loud = relation('Loud', backref=backref('prize', cascade="all, delete, delete-orphan"), uselist=False)

    def __init__(self, *args, **kwargs):
        super(Prize, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<prize:%s>" % self.id

    def __str__(self):
        return "<prize:%s>" % self.id

    def can_save(self):
        return self.user_id and self.loud_id

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    def prize2dict(self):
        include = ['content', 'has_star', 'created']

        info = self.to_dict(include)
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link()
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
    created = Column(DateTime, default=datetime.datetime.now)

    user = relation('User', backref=backref('replies', order_by=created,  cascade="all, delete, delete-orphan"))
    loud = relation('Loud', backref=backref('replies', order_by=created,  cascade="all, delete, delete-orphan"))

    def __init__(self, *args, **kwargs):
        super(Reply, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<reply:%s>" % self.id

    def __str__(self):
        return "<reply:%s>" % self.id

    def can_save(self):
        return self.user_id and self.loud_id and self.content \
                and self.lat and self.lon \
                and (self.is_help == True or self.is_help == False)

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    def reply2dict(self):
        include = ['content', 'lat', 'lon', 'flat', 'flon', 'address', 'created']

        info = self.to_dict(include)
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link()
        info['user'] = self.user.user2dict4link()
        #info['loud'] = self.loud.loud2dict()

        return info


class Loud(Base):
    __tablename__ = 'louds'

    _fields = (
            'user_id',
            'paycate',
            'loudcate',
            'content',
            'lat',
            'lon',
            'flat',
            'flon',
            'address',
            'status',
            'updated',
            'created',
            )

    query_class = LoudQuery

    ERR, OVERDUE, SHOW, DONE = 0, 100, 200, 300

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"))
    content = Column(String(70))
    paycate = Column(String(10))
    loudcate = Column(String(10))
    lat = Column(Float, default=0)
    lon = Column(Float, default=0)
    flat = Column(Float, default=0, nullable=True)
    flon = Column(Float, default=0, nullable=True)
    address = Column(String(30), nullable=True)
    status = Column(SmallInteger, default=SHOW)
    updated = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created = Column(DateTime, default=datetime.datetime.now)

    # on delete CASCADE make me a lots to fix it. 
    # use this feature you must do two things:
    # 1) Column ForeignKey set ondelete keyword for database level 
    # 2) mapper on relation set cascade keyword in parent Model for sqlalchemy session level 
    user = relation('User', backref=backref('louds', order_by=created,  cascade="all, delete, delete-orphan"))

    def __init__(self, *args, **kwargs):
        super(Loud, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<loud:%s>" % self.id

    def __str__(self):
        return "<loud:%s>" % self.id

    def can_save(self):
        return self.user_id and self.content and self.lat and self.lon \
                and self.paycate and self.loudcate

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin
    
    def loud2dict(self):
        include=['content', 'paycate', 'loudcate', 'address', 'lat', 'lon',
                'flat', 'flon', 'updated', 'created']

        info = self.to_dict(include)
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link()
        info['user'] = self.user.user2dict4link()
        info['replies_link'] = url_concat('%s%s' % 
               (options.site_uri, self.reverse_uri(Reply.__tablename__, "")),
                {'lid': self.id, 'qs': "created desc", 'st': 0, 'qn': 20})

        return info



# user's all louds number
User.loud_num = column_property(sql.select([sql.func.count(Loud.id)]).\
        where(Loud.user_id==User.id).as_scalar(), deferred=True)

# user's star num
User.star_num = column_property(sql.select([sql.func.count(Prize.user_id)]).\
        where(sql.and_(Prize.user_id==User.id, Prize.has_star==True)).\
        as_scalar(), deferred=True)

# user's help other num
User.to_help_num = column_property(sql.select([sql.func.count(Prize.user_id)]).\
        where(Prize.user_id==User.id).as_scalar(), deferred=True)

# loud's replies number
Loud.reply_num = column_property(sql.select([sql.func.count(Reply.id)]).\
        where(Reply.user_id==Loud.id).as_scalar(), deferred=True)
