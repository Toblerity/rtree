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

#ifdef _MSC_VER
#include "SpatialIndex.h"
#else
#include <spatialindex/SpatialIndex.h>
#endif


#include "gispyspatialindex.h"

using namespace SpatialIndex;

void GISPySpatialIndex::Initialize()
{
  unsigned int capacity = 10;
  bool writeThrough = false;
  mStorage = StorageManager::createNewRandomEvictionsBuffer(*mStorageManager, capacity, writeThrough);

  // R-Tree parameters
  double fillFactor = 0.7;
  unsigned long indexCapacity = 10;
  unsigned long leafCapacity = 10;
  unsigned long dimension = 2;
  RTree::RTreeVariant variant = RTree::RV_RSTAR;

  // create R-tree
  id_type indexId=1;
  mRTree = RTree::createNewRTree(*mStorage, fillFactor, indexCapacity,
                                 leafCapacity, dimension, variant, indexId); 
   

}
GISPySpatialIndex::GISPySpatialIndex()
{

  mStorageManager = StorageManager::createNewMemoryStorageManager();
  
  Initialize();
}

// Load a persisted index
GISPySpatialIndex::GISPySpatialIndex(const char* filename)
{

  std::string oFilename = std::string(filename);
  mStorageManager = StorageManager::loadDiskStorageManager(oFilename);

  unsigned int capacity = 10;
  bool writeThrough = false;
  mStorage = StorageManager::createNewRandomEvictionsBuffer(*mStorageManager, capacity, writeThrough);

  // load R-tree
  long indexId= 1;
  mRTree = RTree::loadRTree(*mStorage, indexId); 

}

// Create a new index
GISPySpatialIndex::GISPySpatialIndex(const char* filename, unsigned long pagesize)
{

  std::string oFilename = std::string(filename);
  mStorageManager = StorageManager::createNewDiskStorageManager(oFilename, pagesize);

  Initialize();

}

GISPySpatialIndex:: ~GISPySpatialIndex()
{
  delete mRTree;
  delete mStorage;
  delete mStorageManager;
}

