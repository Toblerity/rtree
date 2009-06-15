/*
# =============================================================================
# Rtree spatial index. Copyright (C) 2009 Howard Butler
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
# Contact email: hobu.inc at gmail dot com
# =============================================================================
*/

#ifndef SIDX_API_H_INCLUDED
#define SIDX_API_H_INCLUDED

#include "sidx_config.h"

IDX_C_START

IndexH Index_Create(const char* pszFilename, IndexProperties* properties);
void Index_Delete(IndexH index);
RTError Index_DeleteData(IndexH index, uint64_t id, double* pdMin, double* pdMax, uint32_t nDimension);
RTError Index_InsertData(IndexH index, uint64_t id, double* pdMin, double* pdMax, uint32_t nDimension);
RTError Index_IsValid(IndexH index);
RTError Index_Intersects(IndexH index, uint64_t* ids, uint32_t nCount, double* pdMin, double pdMax, uint32_t nDimension);

IDX_C_END

#endif