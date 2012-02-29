#!/usr/bin/env python
# coding: utf-8
'''
    name: majia manager
    brief: manage the majia for lebang.
    version: 0.1 beta
    author: cloud
    mail: cloudcry@gmail.com
'''

import functools
import binascii, uuid, time, cStringIO
import json, pycurl, urlparse, urllib, hmac, hashlib, base64, datetime


BASEURI = 'http://i.n2u.in'
ADMIN = {
        'userkey': 'weibo_1987513781',
        'secret': '490ee5421944427db77a78548c99aaa9',
        } 
PUPPET = None
LOUDS = []

APP_KEY = "pc2012022801"
APP_SECRET = "9f4f1603321c40b1914976bc51381878"


class AInput(object):
    ''' This class will create a object with a simpler coding interface to retrieve console raw_input
    '''

    def __init__(self, msg=""):
       ''' This will create a instance of araw_input object
       '''
       self.data = ""  # Initialize a empty data variable
       if not msg == "":
          self.ask(msg)
 
    def ask(self, msg, req=0):
       ''' This will display the prompt and retrieve the user raw_input.
       '''
       if req == 0:
          self.data = raw_input(msg)  # Save the user raw_input to a local object variable
       else:
          self.data = raw_input(msg + " (Require)")
 
       # Verify that the information was entered and its not empty. This will accept a space character. Better Validation needed
       if req == 1 and self.data == "":
          self.ask(msg, req)
 
    def getString(self):
       ''' Returns the user raw_input as String
       '''
       return self.data

    def getInteger(self):
       ''' Returns the user raw_input as a Integer
       '''
       data = None
       while data is None:
           try:
               data = int(self.data)
           except ValueError:
               print "错误：请输入整数值"
               self.ask("请重新输入正确值: ")
               data = None

       return data 
 
    def getNumber(self):
       ''' Returns the user raw_input as a Float number
       '''
       data = None
       while data is None:
           try:
               data = float(self.data)
           except ValueError:
               print "错误：请输入浮点数"
               self.ask("请重新输入正确值: ")
               data = None

       return data
 

class Request(object):

    md = {
        'GET'  : (pycurl.HTTPGET, 1),
        'PUT'  : (pycurl.PUT, 1), 
        'POST' : (pycurl.POST, 1),
        'DELETE' : (pycurl.CUSTOMREQUEST, 'DELETE'),
    }
    rcd = {
        200 : 'Ok',
        201 : 'Created',
        401 : 'Bad Request',
        401 : 'Unauthorized',
        403 : 'Forbidden',
        404 : 'Not Found',
        504 : 'Gateway Timeout',
        505 : 'Http Version Not Supported',
    }

    def __init__(self, uri, user=ADMIN, all=False):
        self.uri = all and str(uri) or urlparse.urljoin(BASEURI, uri)
        self.user = user
        self.auth_paras = self._auth_paras()
        self.buf = cStringIO.StringIO()

    def get(self):
        self.method = 'GET'
        self._request()
        if self.code == 200:
            data = json.loads(self.buf.getvalue().splitlines()[0])
            return data

    def post(self, body=None):
        self.method = 'POST'
        self._request(body)
        if self.code == 201:
            return 'OK'           

    def put(self, body=None):
        self.method = 'PUT'
        self._request(body)
        if self.code == 200:
            return 'OK'

    def delete(self):
        self.method = 'DELETE'
        self._request()
        if self.code == 200:
            return 'OK'

    def _request(self, body=None):
        headers = ['Content-Type: application/json', 'Accept: application/json']
        headers.append(self.to_header()) 

        conn = pycurl.Curl()
        #conn.setopt(pycurl.VERBOSE, 1)
        conn.setopt(pycurl.URL, self.uri)
        conn.setopt(*self.md[self.method])
        conn.setopt(pycurl.HTTPHEADER, headers)
        conn.setopt(pycurl.WRITEFUNCTION, self.buf.write)
        if self.method in ('PUT', 'POST') and body:
            conn.setopt(pycurl.POSTFIELDS, body)
        conn.perform()
        self.code = int(conn.getinfo(pycurl.HTTP_CODE))
        conn.close()

    def get_normalized_method(self):
        return self.method.upper()

    def get_normalized_http_url(self):
        parts = urlparse.urlparse(self.uri)
        scheme, netloc, path = parts[:3]
        normalized_url = scheme.lower() + "://" + netloc.lower() + path
        return normalized_url

    def get_normalized_parameters(self):
        querystr = urlparse.urlparse(self.uri).query
        args = self._query_args_a0(querystr)
        args.update({k: v for k, v in self.auth_paras.items()
            if k[:5] == 'auth_' and k != 'auth_signature'})
        key_values = args.items()
        key_values.sort()

        res = '&'.join('%s=%s' % (self._url_escape(str(k)), self._url_escape(str(v))) for k, v in key_values)
        return res

    def _query_args_a0(self, s):
        query_args = urlparse.parse_qs(s, keep_blank_values=False)
        return {k: urllib.unquote(v[0]) for k, v in query_args.items()}

    def _signature(self):
        sig = (
                self._url_escape(self.get_normalized_method()),
                self._url_escape(self.get_normalized_http_url()),
                self._url_escape(self.get_normalized_parameters()), 
                )
        key = '%s&%s' % (self._url_escape(APP_SECRET), self._url_escape(self.user['secret']))
        raw = '&'.join(sig)

        # hmac object
        hashed = hmac.new(key, raw, hashlib.sha1)

        return base64.b64encode(hashed.digest())

    def _url_escape(self, s):
        return urllib.quote(s, safe='~')

    def _auth_paras(self):
        paras = {
                'auth_app_key': APP_KEY,
                'auth_user_key': self.user['userkey'],
                'auth_timestamp': str(int(time.time())),
                'auth_once': binascii.b2a_hex(uuid.uuid4().bytes),
                'auth_signature_method': 'HMAC-SHA1',
                }
        return paras

    def to_header(self, realm=''):
        auth_header = 'Auth realm="%s"' % realm
        self.auth_paras['auth_signature'] = self._signature()

        if self.auth_paras:
            for k, v in self.auth_paras.items():
                if k[:5] == 'auth_':
                    auth_header += ', %s="%s"' % (k, self._url_escape(str(v)))

        #return {'Authorization': auth_header}
        return "Authorization: %s" % auth_header


def prompt():
    if PUPPET:
        msg_step(u"马甲: %s(%s)" % (PUPPET['name'], PUPPET['userkey']))
    print "---------------------------"
    print "1 -> 化身为马甲*"
    print "2 -> 发送求助"
    print "3 -> 附近列表"
    print "4 -> 我的列表"
    print "5 -> 评论列表"
    print "6 -> 评论"
    print "7 -> 删除求助"
    print "8 -> 删除马甲"
    print "9 -> 添加新马甲*"
    print "10 -> 马甲列表*"
    print "0 -> 退出"
    print "---------------------------"


# error process
def msg_error(msg):
    print "$$$$$ ERR: %s $$$$$" % msg

def msg_flash(msg):
    print "##### %s #####" % msg

def msg_step(msg):
    print ">>> %s" % msg

def puppet(method):
    @functools.wraps(method)
    def wrapper():
        if not PUPPET:
            msg_error("请先化身为马甲")
            return
        return method()
    return wrapper

def enter():
    msg_step("验证Admin的权限...")
    c = Request("/admin/check")
    res = c.get()
    if res:
        msg_flash("授权进入")
    else:
        msg_error("无权操作")
        quit()

def quit():
    msg_flash("Quit")
    exit()

def add_avatar():
    msg_step("请填入马甲信息")
    name = AInput("姓名: ").getString()
    userkey = AInput("userkey: ").getString()
    brief = AInput("简介: ").getString()

    data = {
            'name': name,
            'userkey': userkey,
            'brief': brief,
            }
    data_json = json.dumps(data)

    c = Request("/admin/avatar/")
    res = c.post(data_json)

    if res == 'OK':
        msg_flash("马甲添加成功")
    else:
        msg_error("马甲添加失败，请重新添加")

def become_avatar():
    uk = AInput("化身用户的userkey: ").getString()
    c = Request("/admin/avatar/%s" % uk)
    res = c.get()
    if res:
        global PUPPET 
        PUPPET = res
        msg_flash("化身成功")
    else:
        msg_error("化身失败")

def list_paycate():
    print "报酬类型列表"
    print "    food: 请你吃饭"
    print "    drink: 请你喝饮料"
    print "    movie: 请你看电影"
    print "    gift: 送你小礼物"
    print "    money: 现金奖励"
    print "    other: 其他"

def list_loudcate():
    print "求助类型列表"
    print "    pinche: 顺路拼车"
    print "    delivery: 征人跑腿"
    print "    virtual: 随便问问"
    print "    handyman: 来人修理"
    print "    jobs: 招贤纳士"
    print "    other: 其他"

@puppet
def send_loud():
    list_loudcate()
    list_paycate()
    data = dict(
        loudcate=AInput("求助类型: ").getString(),
        paycate=AInput("报酬类型: ").getString(),
        paydesc=AInput("报酬简述: ").getString(),
        content=AInput("困难描述: ").getString(),
        lat=AInput("纬度: ").getNumber(),
        lon=AInput("经度: ").getNumber(),
        due=AInput("有效期(小时): ").getInteger(),
        weibo=False,
        renren=False,
        douban=False,
    )
    data['expired'] = (datetime.datetime.utcnow() + datetime.timedelta(hours=data['due'])).isoformat()

    data_json = json.dumps(data)
    c = Request("/l/", PUPPET)
    res = c.post(data_json)

    if res == 'OK':
        msg_flash("发送求助成功")
    else:
        msg_error("求助发送失败")

def show_list():

    msg = {
            0: u"错误",
            100: u"过期",
            200: u"求助中",
            300: u"完成",
            }
    
    print "=" * 20
    print u"总共 %s 条" % len(LOUDS)
    n = 0
    for loud in LOUDS:
        expired = datetime.datetime.strptime(loud['expired'], '%Y-%m-%dT%H:%M:%S')
        if expired < datetime.datetime.utcnow():
            loud['status'] = 100
        entry = u"No.%d -> 状态{%s} 内容{%s} 求助者{%s} 回应数{%d} 时间{%s}" % \
                ( n, msg[loud['status']], loud['content'], loud['user']['name'], loud['reply_num'], loud['created'])
        print entry
        n += 1

    print "=" * 20

@puppet
def nearby_list():
    lat = AInput("纬度: ").getNumber()
    lon = AInput("经度: ").getNumber()
    qs = dict(
            q='position:%s,%s' % (lat, lon),
            qs='created desc',
            st=0,
            qn=200,
            )
    url = "/s?%s" % urllib.urlencode(qs)
    c = Request(url, PUPPET)
    data = c.get()
    if data:
        global LOUDS
        LOUDS = data['louds']
        show_list()
    else:
        msg_error("获取列表出错")

@puppet
def my_list():
    qs = dict(
            q='author:%s' % PUPPET['userkey'],
            qs='created desc',
            st=0,
            qn=200,
            )
    url = "/s?%s" % urllib.urlencode(qs)
    c = Request(url, PUPPET)
    data = c.get()
    if data:
        global LOUDS
        LOUDS = data['louds']
        show_list()
    else:
        msg_error("获取列表出错")

def show_reply_list(data):

    print "=" * 20
    print u"总共 %s 条" % data['total']
    n = 0
    for reply in data['replies']:
        entry = u"No.%d -> 内容{%s} 评论者{%s} 时间{%s}" % \
                ( n, reply['content'], reply['user']['name'], reply['created'])
        print entry
        n += 1

    print "=" * 20

@puppet
def reply_list():
    if not LOUDS:
        msg_error("求助列表为空, 请先获取列表")
        return
    no = AInput("求助信息序号: ").getInteger()
    if no < 0 or no > len(LOUDS) - 1:
        msg_error("序号超出范围")
        return
    loud = LOUDS[no]
    c = Request(loud['replies_link'], PUPPET, all=True) 
    data = c.get()
    if data:
        show_reply_list(data)
    else:
        msg_error("获取评论列表失败")

@puppet
def reply():
    if not LOUDS:
        msg_error("求助列表为空, 请先获取列表")
        return
    no = AInput("求助信息序号: ").getInteger()
    if no < 0 or no > len(LOUDS) - 1:
        msg_error("序号超出范围")
        return
    loud = LOUDS[no]

    data = {
            'content': AInput("内容: ").getString(),
            'lat': AInput("纬度: ").getNumber(),
            'lon': AInput("经度: ").getNumber(),
            'is_help': False,
            'urn': loud['id'],
            }
    data_json = json.dumps(data)
    c = Request('/reply/', PUPPET)
    res = c.post(data_json)
    if res == 'OK':
        msg_flash("评论成功")
    else:
        msg_error("评论失败")

@puppet
def del_loud():
    if not LOUDS:
        msg_error("求助列表为空, 请先获取列表")
        return
    no = AInput("求助信息序号: ").getInteger()
    if no < 0 or no > len(LOUDS) - 1:
        msg_error("序号超出范围")
        return
    loud = LOUDS[no]
    c = Request(loud['link'], PUPPET, all=True)
    res = c.delete()
    if res == 'OK':
        msg_flash("成功删除求助")
    else:
        msg_error("删除求助失败")

@puppet
def del_avatar():
    sure = AInput("确认$$你真的要删除当前这个马甲$$ (y/n)").getString()
    global PUPPET
    if sure.upper() == 'Y':
        c = Request(PUPPET['link'], PUPPET, all=True)
        res = c.delete()
        if res == 'OK':
            PUPPET = None
            msg_flash("马甲删除成功")
        else:
            msg_error("删除失败")

def show_avatar_list(data):

    print "=" * 20
    print u"总共 %s 条" % data['total']
    n = 0
    for user in data['users']:
        entry = u"No.%d -> 昵称{%s} userkey{%s} secret{%s}" % \
                ( n, user['name'], user['userkey'], user['secret'])
        print entry
        n += 1

    print "=" * 20

def avatar_list():
    qs = dict(
            q='eva_',
            qs='created desc',
            st=0,
            qn=200,
            )
    url = "/admin/avatar/?%s" % urllib.urlencode(qs)
    c = Request(url)
    data = c.get()
    if data:
        show_avatar_list(data)
    else:
        msg_error("获取列表出错")
    pass

COMMANDS = {
        0: quit,
        1: become_avatar,
        2: send_loud,
        3: nearby_list,
        4: my_list,
        5: reply_list,
        6: reply,
        7: del_loud,
        8: del_avatar,
        9: add_avatar,
        10: avatar_list,
        }

def main():
    enter()
    while 1:
        prompt()
        while 1:
            code = AInput("请输入你的选项并按回车: ").getInteger()
            if code in COMMANDS:
                break
        command = COMMANDS[code]
        command()

 
if __name__ == '__main__':
        main()
