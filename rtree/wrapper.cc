/*
# =============================================================================
# Rtree spatial index. Copyright (C) 2006 Ancient World Mapping Center
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place, Suite 330, Boston, MA 02111-1307 USA
#
# Contact email: sgillies@frii.com
# =============================================================================
*/

#include "gispyspatialindex.h"
#include "Python.h"
#include <SpatialIndex.h>

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
        PyList_Append(ids, Py_BuildValue("l", d.getIdentifier()));
    }

    void visitData(std::vector<const IData*>& v) {}

private:
    PyObject *ids;
};


extern "C"
GISPySpatialIndex *
RtreeIndex_new()
{
    return new GISPySpatialIndex;
}

extern "C"
void
RtreeIndex_del(GISPySpatialIndex *index)
{
    delete index;
}

extern "C"
void
RtreeIndex_insertData(GISPySpatialIndex *index, long id,
                      double *min, double *max)
{
  /* TODO: handle possible exceptions */
  index->mRTree->insertData(0, 0, Tools::Geometry::Region(min, max, 2), id);
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
    const Tools::Geometry::Region *region = new Tools::Geometry::Region(min, max, 2);
     index->mRTree->intersectsWithQuery(
        (*region), (*visitor)
    );
    delete region;
    delete visitor;
    return ids;
}

