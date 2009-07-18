
import core
import ctypes


class IndexProperty(object):
    def __init__(self, handle = None, owned=True):
        if handle:
            self.handle = handle
        else:
            self.handle = core.rt.IndexProperty_Create()
        self.owned = owned
    def __del__(self):
        if self.owned:
            if self.handle and core:
                core.rt.IndexProperty_Destroy(self.handle)
    
    def get_index_type(self):
        return core.rt.IndexProperty_GetIndexType(self.handle)
    def set_index_type(self, value):
#        print 'setting index type to %d'%value
        return core.rt.IndexProperty_SetIndexType(self.handle, value)
    type = property(get_index_type, set_index_type)