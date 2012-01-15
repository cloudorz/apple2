# coding: utf-8

from apps import BaseRequestHandler
from apps.models import Loud, Reply
from apps.rdbm import Message, ReadMessage

class UpdatedLoudHandler(BaseRequestHandler):
    # wait for test TODO

    @authenticated
    def get(self):
        
        lat = self.get_argument('lat')
        lon = self.get_argument('lon')
        new_loud_count = Loud.query.cycle_update(lat, lon, self.last_modified_time).count()

        if new_loud_count <= 0:
            raise HTTPError(304, "Not changed.")

        self.render_json({'count': new_loud_count})

    @property
    def last_modified_time(self):
        ims = self.request.headers.get('If-Modified-Since', None)
        ims_time = datetime.datetime(1970,1,1,0,0)

        if ims:
            ims_time = datetime.datetime.strptime(ims, '%a, %d %b %Y %H:%M:%S %Z')

        return ims_time


