__import__('os').environ.setdefault('DJANGO_SETTINGS_MODULE', 'csc.django_settings')
import mongoengine as mon
from mongoengine.queryset import DoesNotExist
import db_config
from conceptdb.log import Log

def connect_to_mongodb(dbname='conceptdb',
                       host=db_config.MONGODB_HOST,
                       username=db_config.MONGODB_USER,
                       password=db_config.MONGODB_PASSWORD):
    """
    Connect to the given MongoDB database. By default, it will connect to
    'conceptdb' with the settings given in db_config.py, but any of these
    settings can be overridden.

    For example, to use an expendable test database, use dbname='test'
    instead.

    The majority of the methods in csc.conceptdb will not work until
    after you have used connect_to_mongodb successfully.
    """
    mon.connect(dbname, host=host, username=username, password=password)

class ConceptDBDocument(object):
    """
    A base class that provides some common functionality beyond what the
    mongoengine.Document class provides.

    It would be much better Python style if this class inherited from
    mongoengine.Document, but a bug in mongoengine prevents it from having
    multiple levels of subclasses! Our workaround for now is that every
    class of document should inherit from (ConceptDBDocument, mon.Document).
    """
    @classmethod
    def get(cls, key):
        result = cls.objects.with_id(key)
        if result is None: raise DoesNotExist
        return result

    @classmethod
    def create(cls, **fields):
        object = cls(**fields)
        object.save()
        return object

    def update(self, **fields):
        query = self.__class__.objects(id=self.id)
        update = {}
        for key, value in fields.items():
            update['set__'+key] = value
        result = query.update_one(**update)
        Log.record_update(self, fields)
        return result

    def append(self, fieldname, value):
        query = self.__class__.objects(id=self.id)
        update = {
            'push__'+fieldname: value
        }
        result = query.update_one(**update)
        Log.record_append(self, {fieldname: value})
        return result
    
    def save(self):
        self.check_consistency()
        prevstate = None
        if getattr(self, '_id', None) is not None:
            prevstate = self.__class__.objects.with_id(self._id)
        
        result = mon.Document.save(self)
        if prevstate is None:
            Log.record_new(self)
        else:
            Log.record_diff(self, prevstate)
        return result

    def serialize(self):
        return self.serialize_inner(self)

    def serialize_inner(self, obj):
        if isinstance(obj, (mon.Document, mon.EmbeddedDocument)):
            d = {}
            for field in obj._fields:
                value = getattr(obj, field)
                value = self.serialize_inner(value)
                d[field] = value
            return d
        elif isinstance(obj, dict):
            d = {}
            for key, value in obj.items():
                value = self.serialize_inner(value)
                d[field] = value
            return d
        elif isinstance(obj, list):
            l = [self.serialize_inner(value) for value in obj]
            return l
        else: return obj

    def __repr__(self):
        assignments = ['%s=%r' % (key, value) for key, value in self.serialize().items()]
        assignments.sort()
        return "%s(%s)" % (self.__class__.__name__,
                           ', '.join(assignments))

    def __str__(self):
        return repr(self)
