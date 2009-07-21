
import core
import ctypes
import pickle

class Index(object):
    def __init__(self, filename=None, properties=None, owned = True, pagesize = None):
        if properties:
            self.properties = properties
        else:
            self.properties = Property()
            
        if filename:
            self.properties.filename = filename
        
        if pagesize:
            self.properties.pagesize = pagesize
        
        self.handle = core.rt.Index_Create(self.properties.handle)
        self.owned = True
    
    def __del__(self):
        if self.owned:
            if self.handle and core:
                core.rt.Index_Destroy(self.handle)
    
    def insert(self, id, coordinates, obj = None):

        mins = ctypes.c_double*self.properties.dimension
        maxs = ctypes.c_double*self.properties.dimension

        if self.properties.dimension == 2:
            if len(coordinates) != 4:
                raise RTreeError("Coordinates must be in the form minx, miny, maxx, maxy for 2D indexes")
            
            p_mins = mins(ctypes.c_double(coordinates[0]), ctypes.c_double(coordinates[1]))
            p_maxs = maxs(ctypes.c_double(coordinates[2]), ctypes.c_double(coordinates[3]))
        elif self.properties.dimension == 3:
            if len(coordinates) != 6:
                raise RTreeError("Coordinates must be in the form minx, miny, maxx, maxy, minz, maxz for 3D indexes")
            
            p_mins = mins(ctypes.c_double(coordinates[0]), ctypes.c_double(coordinates[1]), ctypes.c_double(coordinates[4]))
            p_maxs = maxs(ctypes.c_double(coordinates[3]), ctypes.c_double(coordinates[4]), ctypes.c_double(coordinates[6]))
        
        if obj:
            pik = pickle.dumps(obj)
            size = len(pik)
            data = ctypes.create_string_buffer(pik)
            data.value = pik
            # data = (ctypes.c_ubyte * size)()
            # for i in range(size):
            #     data[i] = ord(pik[i])
        else:
            data = ctypes.c_ubyte(0)
            size = 0
        core.rt.Index_InsertData(self.handle, id, p_mins, p_maxs, self.properties.dimension, data, size)
    add = insert
    
    def intersection(self, coordinates):
        mins = ctypes.c_double*self.properties.dimension
        maxs = ctypes.c_double*self.properties.dimension

        if self.properties.dimension == 2:
            if len(coordinates) != 4:
                raise RTreeError("Coordinates must be in the form minx, miny, maxx, maxy for 2D indexes")
            
            p_mins = mins(ctypes.c_double(coordinates[0]), ctypes.c_double(coordinates[1]))
            p_maxs = maxs(ctypes.c_double(coordinates[2]), ctypes.c_double(coordinates[3]))
        elif self.properties.dimension == 3:
            if len(coordinates) != 6:
                raise RTreeError("Coordinates must be in the form minx, miny, maxx, maxy, minz, maxz for 3D indexes")
            
            p_mins = mins(ctypes.c_double(coordinates[0]), ctypes.c_double(coordinates[1]), ctypes.c_double(coordinates[4]))
            p_maxs = maxs(ctypes.c_double(coordinates[3]), ctypes.c_double(coordinates[4]), ctypes.c_double(coordinates[6]))
        
        p_num_results = ctypes.c_uint32(0)
       
        items = core.IndexItemH()
        core.rt.Index_Intersects(self.handle, p_mins, p_maxs, self.properties.dimension, ctypes.byref(items), ctypes.byref(p_num_results))
        
        #items = ctypes.cast(items,ctypes.POINTER(ctypes.c_void_p * p_num_results.value))
        results = []
        import pdb;pdb.set_trace()
        for i in range(p_num_results.value):
            it = Item(handle=items[i])
            results.append(it)
        print results
        return [0,1]

class Item(object):
    def __init__(self, handle=None, owned=True):
        if handle:
            self.handle = handle
            
    def get_id(self):
        return core.rt.IndexItem_GetID(self.handle)
    id = property(get_id)

    
class Property(object):
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
        return core.rt.IndexProperty_SetIndexType(self.handle, value)
    type = property(get_index_type, set_index_type)
    
    def get_variant(self):
        return core.rt.IndexProperty_GetIndexVariant(self.handle)
    def set_variant(self, value):
        return core.rt.IndexProperty_SetIndexVariant(self.handle, value)
    variant = property(get_variant, set_variant)

    def get_dimension(self):
        return core.rt.IndexProperty_GetDimension(self.handle)
    def set_dimension(self, value):
        if (value <= 0):
            raise core.RTreeError("Negative or 0 dimensional indexes are not allowed")
        return core.rt.IndexProperty_SetDimension(self.handle, value)
    dimension = property(get_dimension, set_dimension)

    def get_storage(self):
        return core.rt.IndexProperty_GetIndexStorage(self.handle)
    def set_storage(self, value):
        return core.rt.IndexProperty_SetIndexStorage(self.handle, value)
    storage = property(get_storage, set_storage)

    def get_pagesize(self):
        return core.rt.IndexProperty_GetPagesize(self.handle)
    def set_pagesize(self, value):
        if (value <= 0):
            raise core.RTreeError("Pagesize must be > 0")
        return core.rt.IndexProperty_SetPagesize(self.handle, value)
    pagesize = property(get_pagesize, set_pagesize)

    def get_index_capacity(self):
        return core.rt.IndexProperty_GetIndexCapacity(self.handle)
    def set_index_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("index_capacity must be > 0")
        return core.rt.IndexProperty_SetIndexCapacity(self.handle, value)
    index_capacity = property(get_index_capacity, set_index_capacity)

    def get_leaf_capacity(self):
        return core.rt.IndexProperty_GetLeafCapacity(self.handle)
    def set_leaf_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("leaf_capacity must be > 0")
        return core.rt.IndexProperty_SetLeafCapacity(self.handle, value)
    leaf_capacity = property(get_leaf_capacity, set_leaf_capacity)

    def get_index_pool_capacity(self):
        return core.rt.IndexProperty_GetIndexPoolCapacity(self.handle)
    def set_index_pool_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("index_pool_capacity must be > 0")
        return core.rt.IndexProperty_SetIndexPoolCapacity(self.handle, value)
    index_pool_capacity = property(get_index_pool_capacity, set_index_pool_capacity)

    def get_point_pool_capacity(self):
        return core.rt.IndexProperty_GetPointPoolCapacity(self.handle)
    def set_point_pool_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("point_pool_capacity must be > 0")
        return core.rt.IndexProperty_SetPointPoolCapacity(self.handle, value)
    point_pool_capacity = property(get_point_pool_capacity, set_point_pool_capacity)

    def get_region_pool_capacity(self):
        return core.rt.IndexProperty_GetRegionPoolCapacity(self.handle)
    def set_region_pool_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("region_pool_capacity must be > 0")
        return core.rt.IndexProperty_SetRegionPoolCapacity(self.handle, value)
    region_pool_capacity = property(get_region_pool_capacity, set_region_pool_capacity)

    def get_buffering_capacity(self):
        return core.rt.IndexProperty_GetBufferingCapacity(self.handle)
    def set_buffering_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("buffering_capacity must be > 0")
        return core.rt.IndexProperty_SetBufferingCapacity(self.handle, value)
    buffering_capacity = property(get_buffering_capacity, set_buffering_capacity)

    def get_tight_mbr(self):
        return bool(core.rt.IndexProperty_GetEnsureTightMBRs(self.handle))
    def set_tight_mbr(self, value):
        value = bool(value)
        return bool(core.rt.IndexProperty_SetEnsureTightMBRs(self.handle, value))
    tight_mbr = property(get_tight_mbr, set_tight_mbr)

    def get_overwrite(self):
        return bool(core.rt.IndexProperty_GetOverwrite(self.handle))
    def set_overwrite(self, value):
        value = bool(value)
        return bool(core.rt.IndexProperty_SetOverwrite(self.handle, value))
    overwrite = property(get_overwrite, set_overwrite)

    def get_near_minimum_overlap_factor(self):
        return core.rt.IndexProperty_GetNearMinimumOverlapFactor(self.handle)
    def set_near_minimum_overlap_factor(self, value):
        if (value <= 0):
            raise core.RTreeError("near_minimum_overlap_factor must be > 0")
        return core.rt.IndexProperty_SetNearMinimumOverlapFactor(self.handle, value)
    near_minimum_overlap_factor = property(get_near_minimum_overlap_factor, set_near_minimum_overlap_factor)

    def get_writethrough(self):
        return bool(core.rt.IndexProperty_GetWriteThrough(self.handle))
    def set_writethrough(self, value):
        value = bool(value)
        return bool(core.rt.IndexProperty_SetWriteThrough(self.handle, value))
    writethrough = property(get_writethrough, set_writethrough)

    def get_fill_factor(self):
        return core.rt.IndexProperty_GetFillFactor(self.handle)
    def set_fill_factor(self, value):
        return core.rt.IndexProperty_SetFillFactor(self.handle, value)
    fill_factor = property(get_fill_factor, set_fill_factor)

    def get_split_distribution_factor(self):
        return core.rt.IndexProperty_GetSplitDistributionFactor(self.handle)
    def set_split_distribution_factor(self, value):
        return core.rt.IndexProperty_SetSplitDistributionFactor(self.handle, value)
    split_distribution_factor = property(get_split_distribution_factor, set_split_distribution_factor)

    def get_tpr_horizon(self):
        return core.rt.IndexProperty_GetTPRHorizon(self.handle)
    def set_tpr_horizon(self, value):
        return core.rt.IndexProperty_SetTPRHorizon(self.handle, value)
    tpr_horizon = property(get_tpr_horizon, set_tpr_horizon)

    def get_reinsert_factor(self):
        return core.rt.IndexProperty_GetReinsertFactor(self.handle)
    def set_reinsert_factor(self, value):
        return core.rt.IndexProperty_SetReinsertFactor(self.handle, value)
    reinsert_factor = property(get_reinsert_factor, set_reinsert_factor)

    def get_filename(self):
        return core.rt.IndexProperty_GetFileName(self.handle)
    def set_filename(self, value):
        return core.rt.IndexProperty_SetFileName(self.handle, value)
    filename = property(get_filename, set_filename)

    def get_dat_extension(self):
        return core.rt.IndexProperty_GetFileNameExtensionDat(self.handle)
    def set_dat_extension(self, value):
        return core.rt.IndexProperty_SetFileNameExtensionDat(self.handle, value)
    dat_extension = property(get_dat_extension, set_dat_extension)

    def get_idx_extension(self):
        return core.rt.IndexProperty_GetFileNameExtensionIdx(self.handle)
    def set_idx_extension(self, value):
        return core.rt.IndexProperty_SetFileNameExtensionIdx(self.handle, value)
    idx_extension = property(get_idx_extension, set_idx_extension)

    def get_index_id(self):
        return core.rt.IndexProperty_GetIndexID(self.handle)
    def set_index_id(self, value):
        return core.rt.IndexProperty_SetIndexID(self.handle, value)
    index_id = property(get_index_id, set_index_id)