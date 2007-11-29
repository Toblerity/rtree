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


namespace SpatialIndex
{
  class IStorageManager;
  class ISpatialIndex;
  class Region;
  
  namespace StorageManager
  {
    class IBuffer;
  }
}


class GISPySpatialIndex
{

public:
  GISPySpatialIndex();
  GISPySpatialIndex(const char* pszFilename);
  GISPySpatialIndex(const char* pszFilename, unsigned long nPageSize);
  ~GISPySpatialIndex();
  
  bool insertFeature(long id, double *min, double *max);
  SpatialIndex::ISpatialIndex& index() {return *mRTree;}

private:
  void Initialize();
  SpatialIndex::IStorageManager* mStorageManager;
  SpatialIndex::StorageManager::IBuffer* mStorage;
  SpatialIndex::ISpatialIndex* mRTree;
};

