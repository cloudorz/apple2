# coding: utf-8
''' Custom the Base Model class.
1. create class query db session
2. create db -> db_sesssion
3. add some method to Base
'''

import urlparse, logging

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import class_mapper, Query
from sqlalchemy.orm.exc import UnmappedClassError, NoResultFound, MultipleResultsFound
from sqlalchemy import Column

from tornado.options import options

# create the Base class
Base = declarative_base()

# transfer app for get the db_session
class SQLAlchemy(object):
    ''' Get the sqlalchemy session
    '''
    def __init__(self):
        self.db_session = None
    
    def init_app(self, app=None):
        if app:
            self.db_session = app.db_session
            Base.db = app.db_session
            Query.rdb = app.redis
            Base.reverse_uri = app.reverse_url

sql_db = SQLAlchemy()

class BaseQuery(Query):
    ''' common custom query
    '''
    # FIXME test it
    def get_by_key(self, tid):
        try:
            obj = self.filter_by(id=tid, block=False).one()
        except (NoResultFound, MultipleResultsFound):
            obj = None
        return obj


class _QueryProperty(object):
    ''' User.query.
    '''
    def __get__(self, obj, obj_cls):
        try:
            mapper = class_mapper(obj_cls)
            if mapper:
                return obj_cls.query_class(mapper, session=sql_db.db_session)
        except UnmappedClassError:
            return None

# this way create class vars is ok, the subclass also can inherit it
Base.query_class = BaseQuery
Base.query = _QueryProperty()

def obj_to_dict(self, include=[]):
    ''' convent the object to the dcit type
    not contain the relating objects
    '''
    #exclude.append('_sa_instance_state')

    return {k:v for k,v in vars(self).items() if k in include}

def obj_from_dict(self, data):
    # PS: not contain the user and not method name
    any(setattr(self, k, v) for k,v in data.items() if k in self._fields)

def obj_save(self):
    if self.can_save():
        try:
            self.db.add(self)
            self.db.commit()
        except Exception, e:
            self.db.rollback()
            logging.warning("Warning: %s" % e.message)
            return False

        return True

def fake_get_urn(self, attr='id'):
    return "urn:%s:%s" % (self.__tablename__, getattr(self, attr))

def obj_get_link(self, attr='id'):
    #return "%s%s" % (options.site_uri, self.reverse_uri(url_name, self.id))
    return urlparse.urljoin(options.site_uri,
            self.reverse_uri(self.__tablename__, getattr(self, attr)))
        

Base.to_dict = obj_to_dict
Base.from_dict = obj_from_dict
Base.save = obj_save
Base.get_urn = fake_get_urn
Base.get_link = obj_get_link
