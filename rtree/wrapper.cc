/*
# =============================================================================
# Rtree spatial index. Copyright (C) 2007 Sean C. Gillies
#
# This library is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License 
# along with this library; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Contact email: sgillies@frii.com
# =============================================================================
*/

#include "gispyspatialindex.h"
#include "Python.h"

#ifdef _MSC_VER
#include "SpatialIndex.h"
#else
#include <spatialindex/SpatialIndex.h>
#endif

using namespace SpatialIndex;

class PyListVisitor : public IVisitor
{
public:
    PyListVisitor(PyObject *o)
    {
        ids = o;
        Py_INCREF(ids);
    }
    
    ~PyListVisitor()
    {
        Py_DECREF(ids);
    }
    
    void visitNode(const INode & n) {}
    
    void visitData(const IData & d)
    {
        PyList_Append(ids, PyLong_FromLongLong(d.getIdentifier()));
    }

    void visitData(std::vector<const IData*>& v) {}

private:
    PyObject *ids;
};


extern "C"
GISPySpatialIndex *
RtreeIndex_new(char* filename, unsigned long nPageLength, int load)
{
    if (!filename)
        return new GISPySpatialIndex;
    else
    {
        if (load == 1)
        {
            return new GISPySpatialIndex(filename);
        }
        else
        {
            if (!nPageLength) nPageLength=4096;
            return new GISPySpatialIndex(filename, nPageLength);
        }
    }
}

extern "C"
void
RtreeIndex_del(GISPySpatialIndex *index)
{
    delete index;
}

extern "C"
int
RtreeIndex_insertData(GISPySpatialIndex *index, uint64_t id,
                      double *min, double *max)
{
    try {	
        index->index().insertData(0, 0, SpatialIndex::Region(min, max, 2), id);
        return 1;
    }
    catch (Tools::Exception& e) {
        PyErr_SetString(PyExc_TypeError, e.what().c_str());
        return 0;
    }
}

extern "C"
int
RtreeIndex_deleteData(GISPySpatialIndex *index, uint64_t id,
                      double *min, double *max)
{
    try {	
        index->index().deleteData(SpatialIndex::Region(min, max, 2), id);
        return 1;
    }
    catch (Tools::Exception& e) {
        PyErr_SetString(PyExc_TypeError, e.what().c_str());
        return NULL;
    }
  
}

extern "C"
PyObject *
RtreeIndex_intersects(GISPySpatialIndex *index, double *min, double *max)
{
    /* get intersecting data */
    int count=0;
    PyObject *ids;

    ids = PyList_New((size_t)count);
    PyListVisitor *visitor = new PyListVisitor(ids);

    try {	
        const SpatialIndex::Region *region = new SpatialIndex::Region(min, max, 2);
        index->index().intersectsWithQuery((*region), (*visitor));
        delete region;
        delete visitor;
        return ids;
    }
    catch (Tools::Exception& e) {
        PyErr_SetString(PyExc_TypeError, e.what().c_str());
        delete visitor;
        return NULL;
    }

}

extern "C"
int
RtreeIndex_isValid(GISPySpatialIndex *index)
{
  try {	
      return (int) index->index().isIndexValid();
  }
  catch (...) {
     // isIndexValid throws an exception for empty indexes which we'll assume is valid
	return 1; 
  }
}

extern "C"
PyObject *
RtreeIndex_nearestNeighbors(GISPySpatialIndex *index, uint32_t num_results, double *min, double *max)
{
    /* get intersecting data */
    int count=0;
    PyObject *ids;

    ids = PyList_New((size_t)count);
    PyListVisitor *visitor = new PyListVisitor(ids);
    try {	
        const SpatialIndex::Region *region = new SpatialIndex::Region(min, max, 2);
        index->index().nearestNeighborQuery(num_results, (*region), (*visitor));
        delete region;
        delete visitor;
        return ids;
    }
    catch (Tools::Exception& e) {
        PyErr_SetString(PyExc_TypeError, e.what().c_str());
        delete visitor;
        return NULL;
    }
    
}

