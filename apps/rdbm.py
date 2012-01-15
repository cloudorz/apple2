# coding: utf-8

import datetime, hashlib, decimal
from tornado.options import options

from utils.escape import json_encode, json_decode
from utils.tools import time2str, str2time, QDict


now = datetime.datetime.utcnow

def rdb_init_app(app=None):
    if app:
        BasicRdbModel.rdb = app.redis
        BasicRdbModel.reverse_uri = app.reverse_url


class BasicRdbModel(object):

    def maintainlist(self):
        pass

    def generate_score(self, cur=now(), base=datetime.datetime(year=2012, month=1, day=1)):
        return (cur - base).total_seconds()


class Message(BasicRdbModel):
    
    def __init__(self, reply, user_ids):
        self.reply = reply
        self.key = 'msg:%d' % reply.id 
        self.to_ids = user_ids

    def create(self):
        self.add_owner()
        info = {}
        if self.reply.is_help:
            info['label'] = 'help'
        else:
            info['label'] = 'reply'
        info['user'] = self.owner_key
        info['created'] = now()

        self.rdb.hmset(self.key, info)
        self.rdb.expire(self.key, 7*24*3600)
        self.add2users()

    def add_owner(self):
        owner = self.reply.loud.user
        self.owner_key = 'link:user:%d' % owner.id
        self.rdb.hmset(self.owner_key, owner.user2dict4link())

    def add2users(self):
        score = self.generate_score()

        for uid in self.to_ids:
            self.rdb.zadd('user:msg:%d' % uid, self.key, score)


class ReadMessage(BasicRdbModel):

    def __init__(self, uid, last=None):
        self.key = 'user:msg:%d' % uid
        self.nowtime = now()
        if last is None:
            last = self.nowtime - datetime.timedelta(days=7)
        self.last = last

    def getMessages(self):
        self.maintainlist()
        mkeys = self.rdb.zrevrangebyscore(
                self.key,
                self.generate_score(),
                self.generate_score(self.last)
                )
        msgs = []
        for key in mkeys:
            msg = self.rdb.hgetall(key)
            msg['user'] = self.rdb.hgetall(msg['user'])
            msgs.append(msg)

        return msgs

    def maintainlist(self):
        self.rdb.zremrangebyscore(self.key, 0, self.generate_score(self.nowtime))

