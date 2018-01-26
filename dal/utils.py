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

def escape_chars_for_mongo(attrname):
    '''
    Mongo uses the '$' and '.' characters for query syntax. So, if your attributes have these characters, they get converted to dictionaires etc.
    EPICS variables use the '.' character quite a bit.
    We replace these with their unicode equivalents
    '.' gets replaced with U+FF0E
    '$' gets replaced with U+FF04
    This will cause interesting query failures; but there does not seem to be a better choice.
    For example, use something like so to find the param - db.runs.findOne({}, {"params.AMO:HFP:MMS:72\uFF0ERBV": 1})
    '''
    return attrname.replace(".", u"\uFF0E").replace("$", u"\uFF04")
