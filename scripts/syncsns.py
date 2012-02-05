 # coding:utf-8
 
import pycurl, json, urllib, hashlib

import tornado.ioloop

from tornado import httpclient
from tornado.escape import utf8

# keys & secrets 
douban_consumer_key="0855a87df29f2eac1900f979d7dd8c04",
douban_consumer_secret="7524926f6171b225",
weibo_app_key="563114544",
weibo_app_secret="ac88e78e4c5037839cbbb9c92369bdef",
renren_app_key="8f9607b8f2d4446fbc798597dc1dcdd4",
renren_app_secret="c8bfb41852ae40589f268007205fce13",

http_client = httpclient.HTTPClient()

def handle_request(rsp):
    if rsp.error:
        print "Error:", rsp.error

def send_weibo(data):
    content = {
            'status': utf8(data['content']),
            }
    try:
        http_client.fetch("https://api.weibo.com/2/statuses/update.json",
                body=urllib.urlencode(content),
                headers={'Authorization': "OAuth2 %s" % data['token']},
                method='POST',
                )
    except httpclient.HTTPError, e:
        print "Error Weibo:", e

def send_douban(data):
    pass

def send_renren(data):
    params = {
            'method': "status.set",
            'v': "1.0",
            'format': "JSON",
            'access_token': data['token'],
            'status': utf8(data['content']),
            }
    params['sig'] = sig(params)

    try:
        rsp = http_client.fetch("http://api.renren.com/restserver.do",
                body=urllib.urlencode(params),
                method='POST',
                )
    except httpclient.HTTPError, e:
        print "Error renren:", e
    else:
        print rsp.body


def sig(params):
    params_str = ''.join(sorted("%s=%s" % (k, utf8(v)) for k,v in params.items()))
    v = "%s%s" % (params_str, renren_app_secret)

    return hashlib.md5(v).hexdigest()

def on_receive(stream):

    sends = {
            'weibo': send_weibo,
            'renren': send_renren,
            'douban': send_douban,
            }
    
    for b in stream.splitlines():
        try:
            res = json.loads(b)
            data = json.loads(res['value'])
        except:
            pass
        else:
            sends[data['label']](data)
 
def waiting_and_send_data():
    # waiting for data
    conn = pycurl.Curl()
    conn.setopt(pycurl.URL, "http://127.0.0.1:8888/c/snspost")
    conn.setopt(pycurl.WRITEFUNCTION, on_receive)
    conn.perform()

def main():
    waiting_and_send_data()
    # FIXME can work?
    #tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
