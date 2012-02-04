 # coding:utf-8
 
import pycurl, json, urllib

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
            'status': u"%s #%s# @-乐帮-" % (data['content'], data['address']),
            }
    try:
        http_client.fetch("https://api.weibo.com/2/statuses/update.json",
                body=urllib.urlencode(utf8(content)),
                headers={'Authorization': "OAuth2 %s" % data['token']},
                method='POST',
                )
        rsp = http_client.fetch("http://www.google.com/")
    except httpclient.HTTPError, e:
        print "Error:", e

def send_douban(data):
    pass

def send_renren(data):
    pass

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
            print data
 
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
