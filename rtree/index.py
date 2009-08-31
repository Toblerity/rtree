
import core
import ctypes
try:
    import cPickle as pickle
except ImportError:
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


def _get_bounds(handle, bounds_fn, interleaved):
    pp_mins = ctypes.pointer(ctypes.c_double())
    pp_maxs = ctypes.pointer(ctypes.c_double())
    dimension = ctypes.c_uint32(0)
    
    bounds_fn(handle, 
            ctypes.byref(pp_mins), 
            ctypes.byref(pp_maxs), 
            ctypes.byref(dimension))
    if (dimension.value == 0): return None

    mins = ctypes.cast(pp_mins,ctypes.POINTER(ctypes.c_double \
                                                      * dimension.value))
    maxs = ctypes.cast(pp_maxs,ctypes.POINTER(ctypes.c_double \
                                                      * dimension.value))

    results = [mins.contents[i] for i in range(dimension.value)]
    results += [maxs.contents[i] for i in range(dimension.value)]

    p_mins = ctypes.cast(mins,ctypes.POINTER(ctypes.c_double))
    p_maxs = ctypes.cast(maxs,ctypes.POINTER(ctypes.c_double))
    core.rt.Index_Free(ctypes.cast(p_mins, ctypes.POINTER(ctypes.c_void_p))) 
    core.rt.Index_Free(ctypes.cast(p_maxs, ctypes.POINTER(ctypes.c_void_p)))
    if interleaved: # they want bbox order.    
        return results
    return Index.deinterleave(results)


class Index(object):
    """An R-Tree, MVR-Tree, or TPR-Tree indexing object"""
    
    def __init__(self,  *args, **kwargs):
        """Creates a new index
        
        :param filename:
            The first argument in the constructor is assumed to be a filename 
            determining that a file-based storage for the index should be used.  
            If the first argument is not of type basestring, it is then 
            assumed to be an input index item stream.
        
        :param stream:
            If the first argument in the constructor is not of type basestring, 
            it is assumed to be an interable stream of data that will raise a 
            StopIteration.  It must be in the form defined by the :attr:`interleaved`
            attribute of the index.  The following example would assume 
            :attr:`interleaved` is False::
            
                (id, (minx, maxx, miny, maxy, minz, maxz, ..., ..., mink, maxk), object)

            The object can be None, but you must put a place holder of ``None`` there.
        
        :param interleaved: True or False, defaults to True.
            This parameter determines the coordinate order for all methods that 
            take in coordinates.  

        :param properties: An :class:`index.Property` object 
            This object sets both the creation and instantiation properties 
            for the object and they are passed down into libspatialindex.  
            A few properties are curried from instantiation parameters 
            for you like ``pagesize`` and ``overwrite``
            to ensure compatibility with previous versions of the library.  All 
            other properties must be set on the object.
            
        .. warning::
            The coordinate ordering for all functions are sensitive the the 
            index's :attr:`interleaved` data member.  If :attr:`interleaved` 
            is False, the coordinates must be in the form 
            [xmin, xmax, ymin, ymax, ..., ..., kmin, kmax]. If :attr:`interleaved` 
            is True, the coordinates must be in the form 
            [xmin, ymin, ..., kmin, xmax, ymax, ..., kmax].

        A basic example

        ::

            >>> p = index.Property()
    
            >>> idx = index.Index(properties=p)
            >>> idx
            <rtree.index.Index object at 0x...>
    
        Insert an item into the index::

            >>> idx.insert(4321, (34.3776829412, 26.7375853734, 49.3776829412, 41.7375853734), obj=42)

        Query::
        
            >>> hits = idx.intersection((0, 0, 60, 60), objects=True)
            >>> for i in hits:
            ...     if i.id == 4321:
            ...         i.object
            ...         i.bbox
            42
            [34.3776829412, 26.737585373400002, 49.3776829412, 41.737585373400002]

        """
        try:
            self.properties = kwargs['properties']
        except KeyError:
            self.properties = Property()

        # interleaved True gives 'bbox' order.
        self.interleaved = bool(kwargs.get('interleaved', True))
        
        stream = None
        basename = None
        if args:
            if isinstance(args[0], basestring):
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
        dimension = self.properties.dimension
        
        mins = ctypes.c_double * dimension
        maxs = ctypes.c_double * dimension

        if not self.interleaved:
            coordinates = Index.interleave(coordinates)

        # it's a point make it into a bbox. [x, y] => [x, y, x, y]
        if len(coordinates) == dimension:
            coordinates = coordinates + coordinates

        if len(coordinates) != dimension * 2:
            raise core.RTreeError("Coordinates must be in the form "
                                    "(minx, miny, maxx, maxy) or (x, y) for 2D indexes")

        # so here all coords are in the form:
        # [xmin, ymin, zmin, xmax, ymax, zmax]
        for i in range(dimension):
            if not coordinates[i] <= coordinates[i + dimension]:
                raise core.RTreeError("Coordinates must not have minimums more than maximums")

            p_mins = mins(*[ctypes.c_double(\
                                coordinates[i]) for i in range(dimension)])
            p_maxs = maxs(*[ctypes.c_double(\
                            coordinates[i + dimension]) for i in range(dimension)])

        return (p_mins, p_maxs)

    def _serialize(self, obj, dumps=pickle.dumps):
        serialized = dumps(obj)
        size = len(serialized)

        d = ctypes.create_string_buffer(serialized)
        d.value = serialized
        p = ctypes.pointer(d)

        return size, ctypes.cast(p, ctypes.POINTER(ctypes.c_uint8))

    def insert(self, id, coordinates, obj = None):
        """Inserts an item into the index with the given coordinates.  
        
        :param id: long integer
            A long integer that is the identifier for this index entry.  IDs 
            need not be unique to be inserted into the index, and it is up 
            to the user to ensure they are unique if this is a requirement.

        :param coordinates: sequence or array
            This may be an object that satisfies the numpy array 
            protocol, providing the index's dimension * 2 coordinate 
            pairs representing the mink and maxk coordinates in 
            each dimension defining the bounds of the query window.
        
        :param obj: a pickleable object.  If not None, this object will be 
            stored in the index with the :attr:`id`.

        The following example inserts an entry into the index with id `4321`, 
        and the object it stores with that id is the number `42`.  The coordinate 
        ordering in this instance is the default (interleaved=True) ordering::
        
            >>> idx.insert(4321, (34.3776829412, 26.7375853734, 49.3776829412, 41.7375853734), obj=42)

        """
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        if obj:
            size, data = self._serialize(obj)
        else:
            data = ctypes.c_ubyte(0)
            size = 0
        core.rt.Index_InsertData(self.handle, id, p_mins, p_maxs, self.properties.dimension, data, size)
    add = insert
    
    def intersection(self, coordinates, objects=False, as_list=True):
        """Return ids or objects in the index that intersect the given coordinates.
        
        :param coordinates: sequence or array
            This may be an object that satisfies the numpy array 
            protocol, providing the index's dimension * 2 coordinate 
            pairs representing the mink and maxk coordinates in 
            each dimension defining the bounds of the query window.
        
        :param objects: True or False
            If True, the intersection method will return index objects that 
            were pickled when they were stored with each index entry, as 
            well as the id and bounds of the index entries.
            
        :param as_list: true or False
            If False, the method will return an iterator of the results.
        
        The following example queries the index for any objects any objects 
        that were stored in the index intersect the bounds given in the coordinates::
        
            >>> hits = idx.intersection((0, 0, 60, 60), objects=True)
            >>> for i in hits:
            ...     if i.id == 4321:
            ...         i.object
            ...         i.bbox
            42
            [34.3776829412, 26.737585373400002, 49.3776829412, 41.737585373400002]         
        """

        if objects: return self._intersection_obj(coordinates, as_list)
        
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        
        p_num_results = ctypes.c_uint32(0)
        
        it = ctypes.pointer(ctypes.c_uint64())
        
        core.rt.Index_Intersects_id(    self.handle, 
                                        p_mins, 
                                        p_maxs, 
                                        self.properties.dimension, 
                                        ctypes.byref(it), 
                                        ctypes.byref(p_num_results))

        if as_list:
            return list(self._get_ids(it, p_num_results.value))
        return self._get_ids(it, p_num_results.value)

    
    def _intersection_obj(self, coordinates, as_list):
        
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        
        p_num_results = ctypes.c_uint32(0)
        
        it = ctypes.pointer(ctypes.c_void_p())
        
        core.rt.Index_Intersects_obj(   self.handle, 
                                        p_mins, 
                                        p_maxs, 
                                        self.properties.dimension, 
                                        ctypes.byref(it), 
                                        ctypes.byref(p_num_results))
        if as_list:
            return list(self._get_objects(it, p_num_results.value))
        return self._get_objects(it, p_num_results.value)

    def _get_objects(self, it, num_results):
        # take the pointer, yield the result objects and free
        items = ctypes.cast(it, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p * num_results)))
        its = ctypes.cast(items, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))

        try:
            for i in xrange(num_results):
                yield Item(handle=items[i])
            core.rt.Index_DestroyObjResults(its, num_results)
        except: # need to catch all exceptions, not just rtree.
            core.rt.Index_DestroyObjResults(its, num_results)
            raise

    def _get_ids(self, it, num_results):
        # take the pointer, yield the results  and free
        items = ctypes.cast(it, ctypes.POINTER(ctypes.c_uint64 * num_results))
        its = ctypes.cast(items, ctypes.POINTER(ctypes.c_void_p))

        try:
            for i in xrange(num_results):
                yield items.contents[i]
            core.rt.Index_Free(its)
        except:
            core.rt.Index_Free(its)
            raise

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

        return list(self._get_objects(it, p_num_results.contents.value))
        
    def nearest(self, coordinates, num_results, objects=False):
        """Returns the ``k``-nearest objects to the given coordinates.
        
        :param coordinates: sequence or array
            This may be an object that satisfies the numpy array 
            protocol, providing the index's dimension * 2 coordinate 
            pairs representing the mink and maxk coordinates in 
            each dimension defining the bounds of the query window.
        
        :param num_results: integer
            The number of results to return nearest to the given coordinates.
            If two index entries are equidistant, *both* are returned.  
            This property means that :attr:`num_results` may return more 
            items than specified
        
        :param objects: True or False
            If True, the nearest method will return index objects that 
            were pickled when they were stored with each index entry, as 
            well as the id and bounds of the index entries.
        
        Example of finding the three items nearest to this one::

            >>> hits = idx.nearest((0,0,10,10), 3)
        """
        if objects: return self._nearest_obj(coordinates, num_results)
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        
        p_num_results = ctypes.pointer(ctypes.c_uint32(num_results))
        
        it = ctypes.pointer(ctypes.c_uint64())
        
        core.rt.Index_NearestNeighbors_id(  self.handle, 
                                            p_mins, 
                                            p_maxs, 
                                            self.properties.dimension, 
                                            ctypes.byref(it), 
                                            p_num_results)

        return list(self._get_ids(it, p_num_results.contents.value))

    def get_bounds(self, coordinate_interleaved=None):
        """Returns the bounds of the index
        
        :param coordinate_interleaved: If True, the coordinates are turned 
            in the form [xmin, ymin, ..., kmin, xmax, ymax, ..., kmax], 
            otherwise they are returned as 
            [xmin, xmax, ymin, ymax, ..., ..., kmin, kmax].  If not specified,
            the :attr:`interleaved` member of the index is used, which 
            defaults to True.
            
        """
        if coordinate_interleaved is None:
            coordinate_interleaved = self.interleaved
        return _get_bounds(self.handle, core.rt.Index_GetBounds, coordinate_interleaved)
    bounds = property(get_bounds)

    def delete(self, id, coordinates):
        """Deletes items from the index with the given ``'id'`` within the 
        specified coordinates.
        
        :param id: long integer
            A long integer that is the identifier for this index entry.  IDs 
            need not be unique to be inserted into the index, and it is up 
            to the user to ensure they are unique if this is a requirement.

        :param coordinates: sequence or array
            This may be an object that satisfies the numpy array 
            protocol, providing the index's dimension * 2 coordinate 
            pairs representing the mink and maxk coordinates in 
            each dimension defining the bounds of the query window.
        
        Example::
        
            >>> idx.delete(4321, (34.3776829412, 26.7375853734, 49.3776829412, 41.7375853734) )

        """
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        core.rt.Index_DeleteData(self.handle, id, p_mins, p_maxs, self.properties.dimension)
    
    def valid(self):
        return core.rt.Index_IsValid(self.handle)

    @classmethod
    def deinterleave(self, interleaved):
        """
        [xmin, ymin, xmax, ymax] => [xmin, xmax, ymin, ymax]

        >>> Index.deinterleave([0, 10, 1, 11])
        [0, 1, 10, 11]

        >>> Index.deinterleave([0, 1, 2, 10, 11, 12])
        [0, 10, 1, 11, 2, 12]

        """
        assert len(interleaved) % 2 == 0, ("must be a pairwise list")
        dimension = len(interleaved) / 2
        di = []
        for i in range(dimension):
            di.extend([interleaved[i], interleaved[i + dimension]])
        return di

    @classmethod
    def interleave(self, deinterleaved):
        """
        [xmin, xmax, ymin, ymax, zmin, zmax] => [xmin, ymin, zmin, xmax, ymax, zmax]

        >>> Index.interleave([0, 1, 10, 11])
        [0, 10, 1, 11]

        >>> Index.interleave([0, 10, 1, 11, 2, 12])
        [0, 1, 2, 10, 11, 12]

        >>> Index.interleave((-1, 1, 58, 62, 22, 24))
        [-1, 58, 22, 1, 62, 24]

        """
        assert len(deinterleaved) % 2 == 0, ("must be a pairwise list")
        dimension = len(deinterleaved) / 2
        interleaved = []
        for i in range(2):
            interleaved.extend([deinterleaved[i + j] \
                                for j in range(0, len(deinterleaved), 2)])
        return interleaved
        
    

    def _create_idx_from_stream(self, stream):
        """This function is used to instantiate the index given an 
        iterable stream of data.  """
        
        stream_iter = iter(stream)
        dimension = self.properties.dimension
        darray = ctypes.c_double * dimension
        mins = darray()
        maxs = darray()
        no_data = ctypes.cast(ctypes.pointer(ctypes.c_ubyte(0)), 
                              ctypes.POINTER(ctypes.c_ubyte))

        def py_next_item(p_id, p_mins, p_maxs, p_dimension, p_data, p_length):
            """This function must fill pointers to individual entries that will
            be added to the index.  The C API will actually call this function
            to fill out the pointers.  If this function returns anything other 
            than 0, it is assumed that the stream of data is done."""
            
            try:
                p_id[0], coordinates, obj = stream_iter.next()
            except StopIteration:
               # we're done 
               return -1
            
            # set the id
            if self.interleaved:
                coordinates = Index.deinterleave(coordinates)

            

            # this code assumes the coords ar not interleaved. 
            # xmin, xmax, ymin, ymax, zmin, zmax
            for i in range(dimension):
                mins[i] = coordinates[i*2]
                maxs[i] = coordinates[(i*2)+1]
            
            p_mins[0] = ctypes.cast(mins, ctypes.POINTER(ctypes.c_double))
            p_maxs[0] = ctypes.cast(maxs, ctypes.POINTER(ctypes.c_double))

            # set the dimension
            p_dimension[0] = dimension
            if obj is None:
                p_data[0] = no_data 
                p_length[0] = 0
            else:
                p_length[0], data = self._serialize(obj)
                p_data[0] = ctypes.cast(data, ctypes.POINTER(ctypes.c_ubyte))

            return 0


        next = core.NEXTFUNC(py_next_item)
        return core.rt.Index_CreateWithStream(self.properties.handle, next)

# An alias to preserve backward compatibility
Rtree = Index

class Item(object):
    """A container for index entries"""
    def __init__(self, handle=None, owned=False):
        """There should be no reason to instantiate these yourself.  Items are 
        created automatically when you do an .insert() given the parameters of the 
        function."""
        
        if handle:
            self.handle = handle

        self.owned = owned
            
        self.id = core.rt.IndexItem_GetID(self.handle)
        
        self.object = None
        self.object = self.get_object()
        self.bbox = _get_bounds(self.handle, core.rt.IndexItem_GetBounds, True)
        self.bounds = Index.deinterleave(self.bbox) 

    def get_data(self):
        if self.object: return self.object
        
        length = ctypes.c_uint64(0)
        d = ctypes.pointer(ctypes.c_uint8(0))
        core.rt.IndexItem_GetData(self.handle, ctypes.byref(d), ctypes.byref(length))
        if not length.value:
            return None
        return ctypes.string_at(d, length.value)
    
    def get_object(self):
        # short circuit this so we only do it at construction time
        if self.object: return self.object
        
        data = self.get_data()
        if data:
            o = pickle.loads(data)
            return o
        return None
    

class Property(object):
    """An index property object is a container that contains a number of 
    settable index properties.  Many of these properties must be set at 
    index creation times, while others can be used to adjust performance 
    or behavior."""
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
    """Index type. Valid index type values are  
        :data:`RT_RTree`, :data:`RT_MVTree`, or :data:`RT_TPRTree`.  Only 
        RT_RTree (the default) is practically supported at this time."""
    
    def get_variant(self):
        return core.rt.IndexProperty_GetIndexVariant(self.handle)
    def set_variant(self, value):
        return core.rt.IndexProperty_SetIndexVariant(self.handle, value)

    variant = property(get_variant, set_variant)
    """Index variant.  Valid index variant values are
    :data:`RT_Linear`, :data:`RT_Quadratic`, and :data:`RT_Star`"""

    def get_dimension(self):
        return core.rt.IndexProperty_GetDimension(self.handle)
    def set_dimension(self, value):
        if (value <= 0):
            raise core.RTreeError("Negative or 0 dimensional indexes are not allowed")
        return core.rt.IndexProperty_SetDimension(self.handle, value)
        
    dimension = property(get_dimension, set_dimension)
    """Index dimension.  Must be greater than 0, though a dimension of 1 might 
    have undefined behavior."""

    def get_storage(self):
        return core.rt.IndexProperty_GetIndexStorage(self.handle)
    def set_storage(self, value):
        return core.rt.IndexProperty_SetIndexStorage(self.handle, value)

    storage = property(get_storage, set_storage)
    """Index storage.  :data:`RT_Disk` or :data:`RT_Memory`.  If a filename
    is passed as the first parameter to :class:index.Index, :data:`RT_Disk` is 
    assumed.  Otherwise, :data:`RT_Memory` is the default."""

    def get_pagesize(self):
        return core.rt.IndexProperty_GetPagesize(self.handle)
    def set_pagesize(self, value):
        if (value <= 0):
            raise core.RTreeError("Pagesize must be > 0")
        return core.rt.IndexProperty_SetPagesize(self.handle, value)
        
    pagesize = property(get_pagesize, set_pagesize)
    """The pagesize when disk storage is used.  It is ideal to ensure that your 
    index entries fit within a single page for best performance.  """

    def get_index_capacity(self):
        return core.rt.IndexProperty_GetIndexCapacity(self.handle)
    def set_index_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("index_capacity must be > 0")
        return core.rt.IndexProperty_SetIndexCapacity(self.handle, value)
        
    index_capacity = property(get_index_capacity, set_index_capacity)
    """Index capacity"""

    def get_leaf_capacity(self):
        return core.rt.IndexProperty_GetLeafCapacity(self.handle)
    def set_leaf_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("leaf_capacity must be > 0")
        return core.rt.IndexProperty_SetLeafCapacity(self.handle, value)
        
    leaf_capacity = property(get_leaf_capacity, set_leaf_capacity)
    """Leaf capacity"""

    def get_index_pool_capacity(self):
        return core.rt.IndexProperty_GetIndexPoolCapacity(self.handle)
    def set_index_pool_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("index_pool_capacity must be > 0")
        return core.rt.IndexProperty_SetIndexPoolCapacity(self.handle, value)
        
    index_pool_capacity = property(get_index_pool_capacity, set_index_pool_capacity)
    """Index pool capacity"""

    def get_point_pool_capacity(self):
        return core.rt.IndexProperty_GetPointPoolCapacity(self.handle)
    def set_point_pool_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("point_pool_capacity must be > 0")
        return core.rt.IndexProperty_SetPointPoolCapacity(self.handle, value)
        
    point_pool_capacity = property(get_point_pool_capacity, set_point_pool_capacity)
    """Point pool capacity"""

    def get_region_pool_capacity(self):
        return core.rt.IndexProperty_GetRegionPoolCapacity(self.handle)
    def set_region_pool_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("region_pool_capacity must be > 0")
        return core.rt.IndexProperty_SetRegionPoolCapacity(self.handle, value)
        
    region_pool_capacity = property(get_region_pool_capacity, set_region_pool_capacity)
    """Region pool capacity"""

    def get_buffering_capacity(self):
        return core.rt.IndexProperty_GetBufferingCapacity(self.handle)
    def set_buffering_capacity(self, value):
        if (value <= 0):
            raise core.RTreeError("buffering_capacity must be > 0")
        return core.rt.IndexProperty_SetBufferingCapacity(self.handle, value)
        
    buffering_capacity = property(get_buffering_capacity, set_buffering_capacity)
    """Buffering capacity"""

    def get_tight_mbr(self):
        return bool(core.rt.IndexProperty_GetEnsureTightMBRs(self.handle))
    def set_tight_mbr(self, value):
        value = bool(value)
        return bool(core.rt.IndexProperty_SetEnsureTightMBRs(self.handle, value))
        
    tight_mbr = property(get_tight_mbr, set_tight_mbr)
    """Uses tight bounding rectangles"""

    def get_overwrite(self):
        return bool(core.rt.IndexProperty_GetOverwrite(self.handle))
    def set_overwrite(self, value):
        value = bool(value)
        return bool(core.rt.IndexProperty_SetOverwrite(self.handle, value))
        
    overwrite = property(get_overwrite, set_overwrite)
    """Overwrite existing index files"""

    def get_near_minimum_overlap_factor(self):
        return core.rt.IndexProperty_GetNearMinimumOverlapFactor(self.handle)
    def set_near_minimum_overlap_factor(self, value):
        if (value <= 0):
            raise core.RTreeError("near_minimum_overlap_factor must be > 0")
        return core.rt.IndexProperty_SetNearMinimumOverlapFactor(self.handle, value)
        
    near_minimum_overlap_factor = property(get_near_minimum_overlap_factor, set_near_minimum_overlap_factor)
    """Overlap factor for MVRTrees"""

    def get_writethrough(self):
        return bool(core.rt.IndexProperty_GetWriteThrough(self.handle))
    def set_writethrough(self, value):
        value = bool(value)
        return bool(core.rt.IndexProperty_SetWriteThrough(self.handle, value))
        
    writethrough = property(get_writethrough, set_writethrough)
    """Write through caching"""

    def get_fill_factor(self):
        return core.rt.IndexProperty_GetFillFactor(self.handle)
    def set_fill_factor(self, value):
        return core.rt.IndexProperty_SetFillFactor(self.handle, value)
        
    fill_factor = property(get_fill_factor, set_fill_factor)
    """Index node fill factor before branching"""

    def get_split_distribution_factor(self):
        return core.rt.IndexProperty_GetSplitDistributionFactor(self.handle)
    def set_split_distribution_factor(self, value):
        return core.rt.IndexProperty_SetSplitDistributionFactor(self.handle, value)
        
    split_distribution_factor = property(get_split_distribution_factor, set_split_distribution_factor)
    """Split distribution factor"""

    def get_tpr_horizon(self):
        return core.rt.IndexProperty_GetTPRHorizon(self.handle)
    def set_tpr_horizon(self, value):
        return core.rt.IndexProperty_SetTPRHorizon(self.handle, value)
        
    tpr_horizon = property(get_tpr_horizon, set_tpr_horizon)
    """TPR horizon"""

    def get_reinsert_factor(self):
        return core.rt.IndexProperty_GetReinsertFactor(self.handle)
    def set_reinsert_factor(self, value):
        return core.rt.IndexProperty_SetReinsertFactor(self.handle, value)
        
    reinsert_factor = property(get_reinsert_factor, set_reinsert_factor)
    """Reinsert factor"""

    def get_filename(self):
        return core.rt.IndexProperty_GetFileName(self.handle)
    def set_filename(self, value):
        return core.rt.IndexProperty_SetFileName(self.handle, value)
        
    filename = property(get_filename, set_filename)
    """Index filename for disk storage"""

    def get_dat_extension(self):
        return core.rt.IndexProperty_GetFileNameExtensionDat(self.handle)
    def set_dat_extension(self, value):
        return core.rt.IndexProperty_SetFileNameExtensionDat(self.handle, value)
        
    dat_extension = property(get_dat_extension, set_dat_extension)
    """Extension for .dat file"""

    def get_idx_extension(self):
        return core.rt.IndexProperty_GetFileNameExtensionIdx(self.handle)
    def set_idx_extension(self, value):
        return core.rt.IndexProperty_SetFileNameExtensionIdx(self.handle, value)

    idx_extension = property(get_idx_extension, set_idx_extension)
    """Extension for .idx file"""

    def get_index_id(self):
        return core.rt.IndexProperty_GetIndexID(self.handle)
    def set_index_id(self, value):
        return core.rt.IndexProperty_SetIndexID(self.handle, value)
        
    index_id = property(get_index_id, set_index_id)
    """First node index id"""
