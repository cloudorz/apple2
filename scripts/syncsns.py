 # coding:utf-8
 
import pycurl, json

import ioloop

form tornado import httpclient

# keys & secrets 
douban_consumer_key="0855a87df29f2eac1900f979d7dd8c04",
douban_consumer_secret="7524926f6171b225",
weibo_app_key="563114544",
weibo_app_secret="ac88e78e4c5037839cbbb9c92369bdef",
renren_app_key="8f9607b8f2d4446fbc798597dc1dcdd4",
renren_app_secret="c8bfb41852ae40589f268007205fce13",

http_client = httpclient.AsyncHTTPClient()

def handle_request(rsp):
    if rsp.error:
        print "Error:", rsp.error

def send_weibo(data):
    body = data['content']
    http_client.fetch("https://api.weibo.com/2/statuses/update.json",
            body=body,
            callback=handle_request,
            headers={'Authorization': "OAuth2 %s" % data['token']},
            method='POST',
            )

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
    # FIXME can work?
    ioloop.IOLoop.instance().start()

    print 'fuck'
    waiting_and_send_data()


if __name__ == '__main__':
    main()
