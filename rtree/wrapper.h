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

#ifndef WRAPPER_H_INCLUDED
#define WRAPPER_H_INCLUDED

#include "idx_config.h"


IDX_C_START

IndexH Index_Create(const char* pszFilename, IndexProperties* properties);
void Index_Delete(IndexH index);
RTError Index_DeleteData(IndexH index, uint64_t id, double* pdMin, double* pdMax, uint32_t nDimension);
RTError Index_InsertData(IndexH index, uint64_t id, double* pdMin, double* pdMax, uint32_t nDimension);
RTError Index_IsValid(IndexH index);
RTError Index_Intersects(IndexH index, uint64_t* ids, uint32_t nCount, double* pdMin, double pdMax, uint32_t nDimension);


RtreeIndex RtreeIndex_new(char* filename, uint32_t nPagesize, int load);
void RtreeIndex_del(RtreeIndex index);
int RtreeIndex_deleteData(RtreeIndex index, uint64_t id, 
        double *min, double *max);
int RtreeIndex_insertData(RtreeIndex index, uint64_t id, 
        double *min, double *max);
int RtreeIndex_isValid(RtreeIndex index);
PyObject *RtreeIndex_intersects(RtreeIndex index, double *min, double *max);
PyObject *RtreeIndex_nearestNeighbors(RtreeIndex index, uint32_t num_results, double *min, double *max);

IDX_C_END

#endif