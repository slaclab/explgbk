'''
Various small utilties.
'''
import json

from bson import ObjectId
from datetime import datetime

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        elif isinstance(o, datetime):
            # Use var d = new Date(str) in JS to deserialize
            # d.toJSON() in JS to convert to a string readable by datetime.strptime(str, '%Y-%m-%dT%H:%M:%S.%fZ')
            return o.isoformat()
        return json.JSONEncoder.default(self, o)
