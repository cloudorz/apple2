 # coding:utf-8
 
import pycurl, json
 
def on_receive(stream):
    
    for b in stream.splitlines():
        try:
            res = json.loads(b)
            data = json.loads(res['value'])
        except:
            pass
        else:
            print data
 
conn = pycurl.Curl()
conn.setopt(pycurl.URL, "http://127.0.0.1:8888/c/snspost")
conn.setopt(pycurl.WRITEFUNCTION, on_receive)
conn.perform()
