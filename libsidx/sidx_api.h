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

IndexH Index_Create(const char* pszFilename, IndexPropertyH properties);
void Index_Delete(IndexH index);
RTError Index_DeleteData(IndexH index, uint64_t id, double* pdMin, double* pdMax, uint32_t nDimension);
RTError Index_InsertData(IndexH index, uint64_t id, double* pdMin, double* pdMax, uint32_t nDimension);
RTError Index_IsValid(IndexH index);
RTError Index_Intersects(IndexH index, uint64_t* ids, uint32_t nCount, double* pdMin, double pdMax, uint32_t nDimension);

RTError IndexProperty_SetIndexType(IndexPropertyH iprop, RTIndexType value);
RTIndexType IndexProperty_GetIndexType(IndexPropertyH iprop);

RTError IndexProperty_SetDimension(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetDimension(IndexPropertyH iprop);

RTError IndexProperty_SetIndexVariant(IndexPropertyH iprop, RTIndexVariant value);
RTIndexVariant IndexProperty_GetIndexVariant(IndexPropertyH iprop);

RTError IndexProperty_SetIndexStorage(IndexPropertyH iprop, RTStorageType value);
RTStorageType IndexProperty_GetIndexStorage(IndexPropertyH iprop);

RTError IndexProperty_SetIndexCapacity(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetIndexCapacity(IndexPropertyH iprop);

RTError IndexProperty_SetLeafCapacity(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetLeafCapacity(IndexPropertyH iprop);

RTError IndexProperty_SetPagesize(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetPagesize(IndexPropertyH iprop);

RTError IndexProperty_SetTPRHorizon(IndexPropertyH iprop, double value);
double IndexProperty_GetTPRHorizon(IndexPropertyH iprop);

RTError IndexProperty_SetFillFactor(IndexPropertyH iprop, double value);
double IndexProperty_GetFillFactor(IndexPropertyH iprop);

    
IDX_C_END

#endif