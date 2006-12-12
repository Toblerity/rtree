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

#include <Python.h>

namespace SpatialIndex
{
  class IStorageManager;
  class ISpatialIndex;

  namespace StorageManager
  {
    class IBuffer;
  }
}

namespace Tools
{
  namespace Geometry
  {
    class Region;
  }
}

class GISPySpatialIndex
{

public:
  GISPySpatialIndex();
  ~GISPySpatialIndex();
  bool insertFeature(long id, double *min, double *max);
  /*void deleteFeature(QgsFeature& f);*/
  PyObject *intersects(double *min, double *max);
  SpatialIndex::IStorageManager* mStorageManager;
  SpatialIndex::StorageManager::IBuffer* mStorage;
  SpatialIndex::ISpatialIndex* mRTree;
};

