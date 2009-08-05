
import core
import ctypes
import pickle

import os
import os.path


RT_Memory = 0
RT_Disk = 1

RT_Linear = 0
RT_Quadratic = 1
RT_Star = 2

RT_RTree = 0
RT_MVRTree = 1
RT_TPRTree = 2

sidx_version = core.rt.SIDX_Version()

class Index(object):
    def __init__(self,  *args, **kwargs):

        try:
            self.properties = kwargs['properties']
        except KeyError:
            self.properties = Property()
        
        stream = None
        basename = None
        if args:
            if isinstance(args[0], str):
                basename = args[0]
            else:
                stream = args[0]
        
        if not stream:
            try:
                args[1]
                stream = args[1]
            except:
                pass
            
        if basename:
            self.properties.storage = RT_Disk
            self.properties.filename = basename

            # check we can read the file
            f = os.path.join('.'.join([basename,self.properties.idx_extension]))

            # assume if the file exists, we're not going to overwrite it
            # unless the user explicitly set the property to do so
            if os.path.exists(os.path.abspath(f)):                
                self.properties.overwrite = False

                # assume we're fetching the first index_id.  If the user
                # set it, we'll fetch that one.
                try:
                    self.properties.index_id
                except core.RTreeError:
                    self.properties.index_id=1
            p = os.path.abspath(f)
            d = os.path.dirname(p)
            if not os.access(d, os.W_OK):
                message = "Unable to open file '%s' for index storage"%f
                raise IOError(message)
        else:
            self.properties.storage = RT_Memory

        try:
            self.properties.pagesize = int(kwargs['pagesize'])
        except KeyError:
            pass
            
        try:
            self.properties.overwrite = bool(kwargs['overwrite'])
        except KeyError:
            pass
        
        if stream:
            self.handle = self._create_idx_from_stream(stream)
        else:
            self.handle = core.rt.Index_Create(self.properties.handle)
        self.owned = True
    
    def __del__(self):
        try:
            self.owned
        except AttributeError:
            # we were partially constructed.  We're going to let it leak
            # in that case
            return
        if self.owned:
            if self.handle and core:
                core.rt.Index_Destroy(self.handle)
    
    def get_coordinate_pointers(self, coordinates):

        try:
            iter(coordinates)
        except TypeError:
            raise TypeError('Bounds must be a sequence')

        
        mins = ctypes.c_double*self.properties.dimension
        maxs = ctypes.c_double*self.properties.dimension

        if self.properties.dimension == 2:
            if len(coordinates) == 4:
                if  (coordinates [0] > coordinates[2]) or \
                    (coordinates[1] > coordinates[3]):
                    raise core.RTreeError("Coordinates must not have minimums more than maximums")

                p_mins = mins(  ctypes.c_double(coordinates[0]), 
                                ctypes.c_double(coordinates[1]))

                p_maxs = maxs(  ctypes.c_double(coordinates[2]), 
                                ctypes.c_double(coordinates[3]))

            elif len(coordinates) == 2:
                p_mins = mins(  ctypes.c_double(coordinates[0]), 
                                ctypes.c_double(coordinates[1]))
                                
                p_maxs = maxs(  ctypes.c_double(coordinates[0]), 
                                ctypes.c_double(coordinates[1]))
            else:
                raise core.RTreeError(  "Coordinates must be in the form "
                                        "(minx, miny, maxx, maxy) or (x, y) for 2D indexes")

        elif self.properties.dimension == 3:
            if  (coordinates[0] > coordinates[3]) or \
                (coordinates[1] > coordinates[4]) or \
                (coordinates[4] > coordinates[5]):
                raise core.RTreeError("Coordinates must not have minimums more than maximums")

            if len(coordinates) != 6:
                raise core.RTreeError(  "Coordinates must be in the form "
                                        "(minx, miny, maxx, maxy, minz, maxz) for 3D indexes")
            
            p_mins = mins(  ctypes.c_double(coordinates[0]), 
                            ctypes.c_double(coordinates[1]), 
                            ctypes.c_double(coordinates[4]))

            p_maxs = maxs(  ctypes.c_double(coordinates[3]), 
                            ctypes.c_double(coordinates[4]), 
                            ctypes.c_double(coordinates[5]))
        
        return (p_mins, p_maxs)

    def insert(self, id, coordinates, obj = None):

        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        if obj:
            pik = pickle.dumps(obj)
            size = len(pik)
            d = ctypes.create_string_buffer(pik)
            d.value = pik
            
            p = ctypes.pointer(d)
            data = ctypes.cast(p, ctypes.POINTER(ctypes.c_uint8))
            # data = (ctypes.c_ubyte * size)()
            # for i in range(size):
            #     data[i] = ord(pik[i])
        else:
            data = ctypes.c_ubyte(0)
            size = 0
        core.rt.Index_InsertData(self.handle, id, p_mins, p_maxs, self.properties.dimension, data, size)
    add = insert
    
    def intersection(self, coordinates, objects=False):
        if objects: return self._intersection_obj(coordinates)
        
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        
        p_num_results = ctypes.c_uint32(0)
        
        it = ctypes.pointer(ctypes.c_uint64())
        
        core.rt.Index_Intersects_id(    self.handle, 
                                        p_mins, 
                                        p_maxs, 
                                        self.properties.dimension, 
                                        ctypes.byref(it), 
                                        ctypes.byref(p_num_results))

        items = ctypes.cast(it,ctypes.POINTER(ctypes.c_uint64 * p_num_results.value))

        results = []

        for i in range(p_num_results.value):
            results.append(items.contents[i])
        
        
        its = ctypes.cast(items,ctypes.POINTER(ctypes.c_void_p))
        core.rt.Index_Free(its)
        
        return results
    
    def _intersection_obj(self, coordinates):
        
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        
        p_num_results = ctypes.c_uint32(0)
        
        it = ctypes.pointer(ctypes.c_void_p())
        
        core.rt.Index_Intersects_obj(   self.handle, 
                                        p_mins, 
                                        p_maxs, 
                                        self.properties.dimension, 
                                        ctypes.byref(it), 
                                        ctypes.byref(p_num_results))

        items = ctypes.cast(it,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p * p_num_results.value)))

        results = []

        for i in range(p_num_results.value):
            it = Item(handle=items[i])
            results.append(it)
        
        items = ctypes.cast(items,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
        core.rt.Index_DestroyObjResults(items, p_num_results.value)
        
        return results

    def _nearest_obj(self, coordinates, num_results):
        
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        
        p_num_results = ctypes.pointer(ctypes.c_uint32(num_results))
                
        it = ctypes.pointer(ctypes.c_void_p())
        
        core.rt.Index_NearestNeighbors_obj( self.handle, 
                                            p_mins, 
                                            p_maxs, 
                                            self.properties.dimension, 
                                            ctypes.byref(it), 
                                            p_num_results)

        items = ctypes.cast(it,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p * p_num_results.contents.value)))
        
        results = []

        for i in range(p_num_results.contents.value):
            it = Item(handle=items[i])
            results.append(it)
        
        its = ctypes.cast(items,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
        core.rt.Index_DestroyObjResults(its, p_num_results.contents.value)
        return results
        
    def nearest(self, coordinates, num_results, objects=False):
        if objects: return self._nearest_obj(coordinates, num_results)
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        
        p_num_results = ctypes.pointer(ctypes.c_uint32(num_results))
        # p_num_results.contents = ctypes.c_uint32(num_results)
        
        it = ctypes.pointer(ctypes.c_uint64())
        
        core.rt.Index_NearestNeighbors_id(  self.handle, 
                                            p_mins, 
                                            p_maxs, 
                                            self.properties.dimension, 
                                            ctypes.byref(it), 
                                            p_num_results)


        # import pdb;pdb.set_trace()
        items = ctypes.cast(it,ctypes.POINTER(ctypes.c_uint64 * p_num_results.contents.value))

        results = []
#        import pdb;pdb.set_trace()
        for i in range(p_num_results.contents.value):
            results.append(items.contents[i])
        
        its = ctypes.cast(items,ctypes.POINTER(ctypes.c_void_p))
        core.rt.Index_Free(its)
        
        return results
    
    def delete(self, id, coordinates):
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        core.rt.Index_DeleteData(self.handle, id, p_mins, p_maxs, self.properties.dimension)
    
    def valid(self):
        return core.rt.Index_IsValid(self.handle)
    
    def get_bounds(self):
        pp_mins = ctypes.pointer(ctypes.c_double())
        pp_maxs = ctypes.pointer(ctypes.c_double())
        dimension = ctypes.c_uint32(0)
        
        core.rt.Index_GetBounds(self.handle, 
                                ctypes.byref(pp_mins), 
                                ctypes.byref(pp_maxs), 
                                ctypes.byref(dimension))
        if (dimension.value == 0): return None

        mins = ctypes.cast(pp_mins,ctypes.POINTER(ctypes.c_double * dimension.value))
        maxs = ctypes.cast(pp_maxs,ctypes.POINTER(ctypes.c_double * dimension.value))
        results = []
        for i in range(dimension.value):
            results.append(mins.contents[i])
            results.append(maxs.contents[i])

        p_mins = ctypes.cast(mins,ctypes.POINTER(ctypes.c_double))
        p_maxs = ctypes.cast(maxs,ctypes.POINTER(ctypes.c_double))
        core.rt.Index_Free(ctypes.cast(p_mins, ctypes.POINTER(ctypes.c_void_p)))
        core.rt.Index_Free(ctypes.cast(p_maxs, ctypes.POINTER(ctypes.c_void_p)))
                
        return results
    bounds = property(get_bounds)

    def _create_idx_from_stream(self, stream):
        """A stream of data need that needs to be an iterator that will raise a 
        StopIteration.  It must be in the following form:

        (id, (minx, maxx, miny, maxy, minz, maxz, ..., ..., mink, maxk), object)

        The object can be None, but you must put a place holder of 'None' there.
        Because of the desire for kD support, we must not interleave the 
        coordinates when using a stream."""
        
        stream_iter = iter(stream)

        def py_next_item(p_id, p_mins, p_maxs, p_dimension, p_data, p_length):

            
            try:
                item = stream_iter.next()
            except StopIteration:
               # we're done 
               return -1
            
            # set the id
            p_id[0] = item[0]
            
            # set the mins
            coordinates = item[1]
            darray = ctypes.c_double * self.properties.dimension
            mins = darray()
            maxs = darray()
            for i in range(self.properties.dimension):
                mins[i] = coordinates[i*2]
                maxs[i] = coordinates[(i*2)+1]
            
            p_mins[0] = ctypes.cast(mins, ctypes.POINTER(ctypes.c_double))
            p_maxs[0] = ctypes.cast(maxs, ctypes.POINTER(ctypes.c_double))

            # set the dimension
            p_dimension[0] = self.properties.dimension
            obj = item[2]
            if obj:

                pik = pickle.dumps(obj)
                size = len(pik)
                d = ctypes.create_string_buffer(pik)
                d.value = pik
            
                p = ctypes.pointer(d)
                data = ctypes.cast(p, ctypes.POINTER(ctypes.c_ubyte))

            else:
                data = ctypes.pointer(ctypes.c_ubyte(0))
                size = 0
            
            p_data[0] = ctypes.cast(data, ctypes.POINTER(ctypes.c_ubyte)) #ctypes.pointer(ctypes.c_ubyte(0))
            p_length[0] = size


            return 0


        next = core.NEXTFUNC(py_next_item)
        return core.rt.Index_CreateWithStream(self.properties.handle, next)
        
class Rtree(Index):
    def __init__(self, *args, **kwargs):
        
        super(Rtree, self).__init__(*args, **kwargs)


class Item(object):
    def __init__(self, handle=None, owned=False):
        if handle:
            self.handle = handle
        self.owned = owned
            
        self.id = core.rt.IndexItem_GetID(self.handle)
        
        self.object = None
        self.object = self.get_object()
        self.bounds = None
        self.bounds = self.get_bounds()

    def get_data(self):
        if self.object: return self.object
        
        length = ctypes.c_uint64(0)
        d = ctypes.pointer(ctypes.c_uint8(0))
        core.rt.IndexItem_GetData(self.handle, ctypes.byref(d), ctypes.byref(length))
        if not length.value:
            return None
        data = ctypes.cast(d, ctypes.POINTER(ctypes.c_ubyte * length.value))
        output = []
        
        # this is dumb, someone smarter please fix - hobu
        for i in range(length.value):
            output.append(chr(data.contents[i]))
        output = ''.join(output)
        return output
    
    def get_object(self):
        # short circuit this so we only do it at construction time
        if self.object: return self.object
        
        data = self.get_data()
        if data:
            o = pickle.loads(data)
            return o
        return None
    
    def get_bounds(self):
        # import pdb;pdb.set_trace()
        if self.bounds: return self.bounds
        
        pp_mins = ctypes.pointer(ctypes.c_double())
        pp_maxs = ctypes.pointer(ctypes.c_double())
        dimension = ctypes.c_uint32(0)
        
        core.rt.IndexItem_GetBounds(self.handle, 
                                    ctypes.byref(pp_mins), 
                                    ctypes.byref(pp_maxs), 
                                    ctypes.byref(dimension))
        
        if not dimension.value: return None

        mins = ctypes.cast(pp_mins,ctypes.POINTER(ctypes.c_double * dimension.value))
        maxs = ctypes.cast(pp_maxs,ctypes.POINTER(ctypes.c_double * dimension.value))
        results = []
        for i in range(dimension.value):
            results.append(mins.contents[i])
            results.append(maxs.contents[i])

        p_mins = ctypes.cast(mins,ctypes.POINTER(ctypes.c_double))
        p_maxs = ctypes.cast(maxs,ctypes.POINTER(ctypes.c_double))
        core.rt.Index_Free(ctypes.cast(p_mins, ctypes.POINTER(ctypes.c_void_p)))
        core.rt.Index_Free(ctypes.cast(p_maxs, ctypes.POINTER(ctypes.c_void_p)))
                
        return results


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