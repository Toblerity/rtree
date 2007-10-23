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

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

typedef struct RtreeIndex_t *RtreeIndex;

RtreeIndex RtreeIndex_new(char* filename, unsigned long nPagesize, int load);
void RtreeIndex_del(RtreeIndex index);
int RtreeIndex_deleteData(RtreeIndex index, long id, 
        double *min, double *max);
int RtreeIndex_insertData(RtreeIndex index, long id, 
        double *min, double *max);
int RtreeIndex_isValid(RtreeIndex index);
PyObject *RtreeIndex_intersects(RtreeIndex index, double *min, double *max);
PyObject *RtreeIndex_nearestNeighbors(RtreeIndex index, uint32_t num_results, double *min, double *max);
#ifdef __cplusplus
} // extern "C"
#endif
