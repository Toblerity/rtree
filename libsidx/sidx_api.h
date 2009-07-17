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

IndexH Index_Create(IndexPropertyH properties);
void Index_Destroy(IndexH index);
IndexPropertyH Index_GetProperties(IndexH index);

RTError Index_DeleteData(   IndexH index, 
                            uint64_t id, 
                            double* pdMin, 
                            double* pdMax, 
                            uint32_t nDimension);
                            
RTError Index_InsertData(   IndexH index, 
                            uint64_t id, 
                            double* pdMin, 
                            double* pdMax, 
                            uint32_t nDimension, 
                            const uint8_t* pData, 
                            size_t nDataLength);
                            
uint32_t Index_IsValid(IndexH index);

RTError Index_Intersects(   IndexH index, 
                            double* pdMin, 
                            double* pdMax, 
                            uint32_t nDimension, 
                            IndexItemH* items, 
                            uint32_t* nResults);

RTError Index_NearestNeighbors( IndexH index, 
                                double* pdMin, 
                                double* pdMax, 
                                uint32_t nDimension, 
                                IndexItemH* items, 
                                uint32_t* nResults);

void IndexItem_Destroy(IndexItemH item);

RTError IndexItem_GetData(uint8_t* data, uint32_t* length);


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

RTError IndexProperty_SetLeafPoolCapacity(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetLeafPoolCapacity(IndexPropertyH iprop);

RTError IndexProperty_SetIndexPoolCapacity(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetIndexPoolCapacity(IndexPropertyH iprop);

RTError IndexProperty_SetRegionPoolCapacity(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetRegionPoolCapacity(IndexPropertyH iprop);

RTError IndexProperty_SetPointPoolCapacity(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetPointPoolCapacity(IndexPropertyH iprop);

RTError IndexProperty_SetBufferingCapacity(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetBufferingCapacity(IndexPropertyH iprop);

RTError IndexProperty_SetEnsureTightMBRs(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetEnsureTightMBRs(IndexPropertyH iprop);

RTError IndexProperty_SetOverwrite(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetOverwrite(IndexPropertyH iprop);

RTError IndexProperty_SetNearMinimumOverlapFactor(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetNearMinimumOverlapFactor(IndexPropertyH iprop);

RTError IndexProperty_SetWriteThrough(IndexPropertyH iprop, uint32_t value);
uint32_t IndexProperty_GetWriteThrough(IndexPropertyH iprop);

RTError IndexProperty_SetFillFactor(IndexPropertyH iprop, double value);
double IndexProperty_GetFillFactor(IndexPropertyH iprop);

RTError IndexProperty_SetSplitDistributionFactor(IndexPropertyH iprop, double value);
double IndexProperty_GetSplitDistributionFactor(IndexPropertyH iprop);

RTError IndexProperty_SetTPRHorizon(IndexPropertyH iprop, double value);
double IndexProperty_GetTPRHorizon(IndexPropertyH iprop);

RTError IndexProperty_SetReinsertFactor(IndexPropertyH iprop, double value);
double IndexProperty_GetReinsertFactor(IndexPropertyH iprop);

RTError IndexProperty_SetFileName(IndexPropertyH iprop, const char* value);
char* IndexProperty_GetFileName(IndexPropertyH iprop);


    
IDX_C_END

#endif