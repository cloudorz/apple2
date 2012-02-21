 # coding:utf-8
 
import pycurl, json, urllib, hashlib, time, uuid, binascii, logging

import tornado.ioloop

from tornado import httpclient
from tornado.escape import utf8
from tornado.auth import _oauth_signature
# apns lib
from apns import APNs, Payload

# keys & secrets 
douban_consumer_key="0855a87df29f2eac1900f979d7dd8c04"
douban_consumer_secret="7524926f6171b225"
weibo_app_key="563114544"
weibo_app_secret="ac88e78e4c5037839cbbb9c92369bdef"
renren_app_key="8f9607b8f2d4446fbc798597dc1dcdd4"
renren_app_secret="c8bfb41852ae40589f268007205fce13"

http_client = httpclient.HTTPClient()
#apns = APNs(use_sandbox=True, cert_file='tcert.pem', key_file='tkey.unencrypted.pem')
apns = APNs(use_sandbox=False, cert_file='cert.pem', key_file='key.unencrypted.pem')

def handle_request(rsp):
    if rsp.error:
        logging.warning( "Error: %s", rsp.error)

def send_weibo(data):
    content = {
            'status': utf8(data['content']),
            }
    try:
        rsp = http_client.fetch("https://api.weibo.com/2/statuses/update.json",
                body=urllib.urlencode(content),
                headers={'Authorization': "OAuth2 %s" % data['token']},
                method='POST',
                )
    except httpclient.HTTPError, e:
        logging.warning( "Error Weibo: %s", e)

def _oauth_request_parameters(url, access_token, parameters={}, method="GET"):
    consumer_token = {
            'key': unicode(douban_consumer_key),
            'secret': unicode(douban_consumer_secret),
            }
    base_args = dict(
        oauth_consumer_key=consumer_token["key"],
        oauth_token=access_token["key"],
        oauth_signature_method="HMAC-SHA1",
        oauth_timestamp=str(int(time.time())),
        oauth_nonce=binascii.b2a_hex(uuid.uuid4().bytes),
        oauth_version='1.0',
    )
    args = {}
    args.update(base_args)
    args.update(parameters)
    signature = _oauth_signature(consumer_token, method, url, args, access_token)
    base_args["oauth_signature"] = signature

    return base_args

def to_header(realm='', parameters=None):
    """Serialize as a header for an HTTPAuth request."""
    auth_header = 'OAuth realm="%s"' % realm
    # Add the oauth parameters.
    if parameters:
        auth_header = "%s, %s" % (auth_header, ', '.join('%s="%s"' % (k, urllib.quote(str(v))) for
            k,v in parameters.items() if k[:6] == 'oauth_'))
    return {'Authorization': auth_header}

def send_douban(data):
    url = "http://api.douban.com/miniblog/saying"
    content  = '<?xml version="1.0" encoding="UTF-8"?>\
                        <entry xmlns:ns0="http://www.w3.org/2005/Atom" xmlns:db="http://www.douban.com/xmlns/">\
                        <content>%s</content>\
                        </entry>' % utf8(data['content'])
    access_token = {
            'key': data['token'],
            'secret': data['secret'],
            }
    oauth = _oauth_request_parameters(url, access_token, method='POST')
    headers = to_header(parameters=oauth)
    headers['Content-Type'] = 'Application/atom+xml; charset=utf-8'

    try:
        rsp = http_client.fetch(url,
                body=content,
                headers=headers,
                method='POST',
                )
    except httpclient.HTTPError, e:
        logging.warning( "Error douban: %s", e)

def send_renren(data):
    params = {
            'method': "status.set",
            'v': "1.0",
            'format': "JSON",
            'access_token': utf8(data['token']),
            'status':utf8(data['content']),
            }
    params['sig'] = sig(params)

    try:
        rsp = http_client.fetch("http://api.renren.com/restserver.do",
                body=urllib.urlencode(params),
                method='POST',
                )
    except httpclient.HTTPError, e:
        logging.warning( "Error renren: %s", e)

def send_apns(data):
    payload = Payload(alert=utf8(data['content']), sound="default")
    apns.gateway_server.send_notification(data['token'], payload)

def sig(params):
    params_str = ''.join(sorted("%s=%s" % (k, utf8(v)) for k, v in params.items()))
    v = "%s%s" % (params_str, renren_app_secret)

    return hashlib.md5(v).hexdigest()

def on_receive(stream):

    sends = {
            'weibo': send_weibo,
            'renren': send_renren,
            'douban': send_douban,
            'apns': send_apns,
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
