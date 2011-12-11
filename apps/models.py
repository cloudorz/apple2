# coding: utf-8

import datetime, hashlib, decimal

from sqlalchemy import sql, Column, String, Integer, Boolean, \
                        DateTime, Float, ForeignKey, Enum, SmallInteger
from sqlalchemy.orm import relation, backref, column_property, synonym
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from tornado.options import options

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

        return self.filter(sql.or_(Loud.grade==0, abs(earth_r*acos(sin(user_lat)*sin(Loud.lat)*cos(user_lon-Loud.lon)+cos(user_lat)*cos(Loud.lat))*pi()/180)<distance))

    def get_by_cycle_key(self, user_lat, user_lon, key):
        return self.get_by_cycle2(user_lat, user_lon).filter(Loud.content.like('%'+key+'%'))


# Models
class Auth(Base):
    __tablename__ = 'auths'

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
        info['link'] = self.get_link('auth')
        info['app'] = self.app.app2dict()
        info['user'] = self.user.user2dict()


class App(Base):
    __tablename__ = 'apps'

    id = Column(Integer, primary_key=True)
    name = Column(String(20))
    key = Column(String(20))
    sec = Column(String(32))
    desc = Column(String(100), nullable=True)

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
        info['link'] = self.get_link('app')
        info['id'] = self.get_urn_id()


class User(Base):
    __tablename__ = 'users'

    query_class = UserQuery

    NORMAL, MERCHANT, ADMIN = 100, 200, 300

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
    is_admin = Column(SmallInteger, default=NORMAL)
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

    def authenticate(self, token):
        return self.token == token

    def user2dict(self, u):
        include=['email', 'name', 'avatar', 'phone', 'brief',
                'block', 'is_admin', 'updated', 'created']

        info = self.to_dict(include)
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link('user')
        info['avatar_link'] = self.get_avatar_link()
        info['loud_num'] = self.loud_num
        info['star_num'] = self.star_num
        info['to_help_num'] = self.to_help_num

        return info

    def user2dict4auth(self):
        info = self.to_dict(include=['name', 'token', 'email', 'updated'])
        return info

    def user2dict4redis(self):
        info = self.to_dict(include=['name', 'phone', 'id', 'is_admin'])
        return info

    def get_avatar_link(self):
        return "%s/%s" % (options.static_uri, self.avatar)

    def generate_avatar_path(self):
        if self.email:
            self.avatar = 'i/%s.jpg' % hashlib.md5(str(self.email)).hexdigest()


class PayCategory(Base):
    __tablename__ = 'paycates'

    id = Column(Integer, primary_key=True)
    label = Column(String(10), unique=True)
    name = Column(String(10))
    help_text = Column(String(100), nullable=True)

    def __init__(self, *args, **kwargs):
        super(PayCategory, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<pay category:%s>" % self.label

    def __str__(self):
        return "<pay category:%s>" % self.label

    def can_save(self):
        return self.name and self.label

    def paycate2dict(self):
        include = ['name', 'label', 'help_text']

        info = self.to_dict(include)
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link()

        return info


class LoudCategory(Base):
    __tablename__ = 'loudcates'

    id = Column(Integer, primary_key=True)
    label = Column(String(10), unique=True)
    name = Column(String(10))
    help_text = Column(String(100), nullable=True)

    def __init__(self, *args, **kwargs):
        super(LoudCategory, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<loud category:%s>" % self.label

    def __str__(self):
        return "<loud category:%s>" % self.label

    def can_save(self):
        return self.label and self.name

    def loudcate2dict(self):
        include = ['name', 'label', 'help_text']

        info = self.to_dict(include)
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link('loudcate')

        return info


class Prize(Base):
    __tablename__ = 'prizes'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
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
        info['link'] = self.get_link('prize')
        info['user'] = self.user2dict()
        info['loud'] = self.loud2dict()

        return info


class Reply(Base):
    __tablename__ = 'replies'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    loud_id = Column(Integer, ForeignKey('louds.id', ondelete='CASCADE'))
    content = Column(String(70))
    lat = Column(Float, default=0)
    lon = Column(Float, default=0)
    flat = Column(Float, default=0, nullable=True)
    flon = Column(Float, default=0, nullable=True)
    address = Column(String(30), nullable=True)
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
                and self.lat and self.lon

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin

    def reply2dict(self):
        include = ['content', 'lat', 'lon', 'flat', 'flon', 'address', 'created']

        info = self.to_dict(include)
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link('reply')
        info['user'] = self.user.user2dict()
        info['loud'] = self.loud.loud2dict()

        return info


class Loud(Base):
    __tablename__ = 'louds'

    query_class = LoudQuery

    SHOW, DONE, ERR = 100, 200, 0

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"))
    paycate_id = Column(Integer, ForeignKey('paycates.id', ondelete="CASCADE"))
    loudcate_id = Column(Integer, ForeignKey('loudcates.id', ondelete="CASCADE"))
    content = Column(String(70))
    lat = Column(Float, default=0)
    lon = Column(Float, default=0)
    flat = Column(Float, default=0, nullable=True)
    flon = Column(Float, default=0, nullable=True)
    address = Column(String(30), nullable=True)
    grade = Column(Integer, default=5)
    status = Column(SmallInteger, default=SHOW)
    updated = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created = Column(DateTime, default=datetime.datetime.now)

    # on delete CASCADE make me a lots to fix it. 
    # use this feature you must do two things:
    # 1) Column ForeignKey set ondelete keyword for database level 
    # 2) mapper on relation set cascade keyword in parent Model for sqlalchemy session level 
    user = relation('User', backref=backref('louds', order_by=created,  cascade="all, delete, delete-orphan"))
    paycate = relation('PayCategory', backref=backref('louds', order_by=created,  cascade="all, delete, delete-orphan"))
    loudcate = relation('LoudCategory', backref=backref('louds', order_by=created,  cascade="all, delete, delete-orphan"))

    def __init__(self, *args, **kwargs):
        super(Loud, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<loud:%s>" % self.id

    def __str__(self):
        return "<loud:%s>" % self.id

    def can_save(self):
        return self.user_id and self.content and self.lat and self.lon \
                and self.paycate_id and self.loudcate_id

    def owner_by(self, u):
        return u and u.id == self.user_id

    def admin_by(self, u):
        return self.owner_by(u) or u.is_admin
    
    def loud2dict(self):
        include=['content', 'grade', 'address', 'lat', 'lon', 'flat',
            'flon', 'created']

        info = self.to_dict()
        info['id'] = self.get_urn_id()
        info['link'] = self.get_link('loud')
        info['user'] = self.user.user2dict()

        return info



# user's all louds number
User.loud_num = column_property(sql.select([sql.func.count(Loud.id)]).\
        where(Loud.user_id==User.id).as_scalar(), deferred=True)

# user's star num
User.star_num = column_property(sql.select([sql.func.count(Prize.id)]).\
        where(sql.and_(Prize.user_id==User.id, Prize.has_star==True)).\
        as_scalar(), deferred=True)

# user's help other num
User.to_help_num = column_property(sql.select([sql.func.count(Prize.id)]).\
        where(Prize.user_id==User.id).as_scalar(), deferred=True)
