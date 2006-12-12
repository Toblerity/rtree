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

#ifdef __cplusplus
extern "C" {
#endif

typedef struct RtreeIndex_t *RtreeIndex;

RtreeIndex RtreeIndex_new();
void RtreeIndex_del(RtreeIndex index);
void RtreeIndex_insertData(RtreeIndex index, long id, 
        double *min, double *max);
PyObject *RtreeIndex_intersects(RtreeIndex index, double *min, double *max);

#ifdef __cplusplus
} // extern "C"
#endif
