/******************************************************************************
 * $Id$
 *
 * Project:  libsidx - A C API wrapper around libspatialindex
 * Purpose:  C++ objects to implement the index.
 * Author:   Howard Butler, hobu.inc@gmail.com
 *
 ******************************************************************************
 * Copyright (c) 2009, Howard Butler
 *
 * All rights reserved.
 * 
 * This library is free software; you can redistribute it and/or modify it under
 * the terms of the GNU Lesser General Public License as published by the Free
 * Software Foundation; either version 2.1 of the License, or (at your option)
 * any later version.

 * This library is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
 * details.
 * 
 * You should have received a copy of the GNU Lesser General Public License 
 * along with this library; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 ****************************************************************************/

#include "sidx_impl.hpp"

SpatialIndex::ISpatialIndex* Index::CreateIndex() 
{
    using namespace SpatialIndex;
    
    ISpatialIndex* index = 0;
    
    Tools::Variant var;

    if (GetIndexType() == RT_RTree) {

        try{
            index = RTree::returnRTree(  *m_buffer, m_properties); 

        } catch (Tools::Exception& e) {
            std::ostringstream os;
            os << "Spatial Index Error: " << e.what();
            throw std::runtime_error(os.str());
        }    
    }

    else if (GetIndexType() == RT_MVRTree) {

        try{
            index = MVRTree::returnMVRTree(  *m_buffer, m_properties); 

        } catch (Tools::Exception& e) {
            std::ostringstream os;
            os << "Spatial Index Error: " << e.what();
            throw std::runtime_error(os.str());
        }   
    }

    else if (GetIndexType() == RT_TPRTree) {

        try{
            index = TPRTree::returnTPRTree(  *m_buffer,m_properties); 

        } catch (Tools::Exception& e) {
            std::ostringstream os;
            os << "Spatial Index Error: " << e.what();
            throw std::runtime_error(os.str());
        }   
    }

    return index;
}


Index::Index(const Tools::PropertySet& poProperties) 
{
    
    Setup();
    
    m_properties = poProperties;

    Initialize();
}


Index::~Index() 
{
    // std::cout << "~Index called" << std::endl;
    
    if (m_rtree != 0)
        delete m_rtree;
    if (m_buffer != 0)
        delete m_buffer;
    if (m_storage != 0)
        delete m_storage;

}




SpatialIndex::StorageManager::IBuffer* Index::CreateIndexBuffer(SpatialIndex::IStorageManager& storage)
{
    using namespace SpatialIndex::StorageManager;
    IBuffer* buffer = 0;
    try{
        if ( m_storage == 0 ) throw std::runtime_error("Storage was invalid to create index buffer");
        buffer = returnRandomEvictionsBuffer(storage, m_properties);
    } catch (Tools::Exception& e) {
        std::ostringstream os;
        os << "Spatial Index Error: " << e.what();
        throw std::runtime_error(os.str());
    }
    return buffer;
}


SpatialIndex::IStorageManager* Index::CreateStorage()
{
    using namespace SpatialIndex::StorageManager;
    
    // std::cout << "index type:" << GetIndexType() << std::endl;
    SpatialIndex::IStorageManager* storage = 0;
    std::string filename("");
    
    Tools::Variant var;
    var = m_properties.getProperty("FileName");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_PCHAR)
            throw std::runtime_error("Index::CreateStorage: Property FileName must be Tools::VT_PCHAR");
        
        filename = std::string(var.m_val.pcVal);
    }
    
    if (GetIndexStorage() == RT_Disk) {
        if (filename.empty()) {
                std::ostringstream os;
                os << "Spatial Index Error: filename was empty.  Set IndexStorageType to RT_Memory";
                throw std::runtime_error(os.str());
        }
            try{
                // std::cout << "creating new DiskStorage " << filename << std::endl;            
                storage = returnDiskStorageManager(m_properties);
                return storage;
            } catch (Tools::Exception& e) {
                std::ostringstream os;
                os << "Spatial Index Error: " << e.what();
                throw std::runtime_error(os.str());
            }         

    } else if (GetIndexStorage() == RT_Memory) {

        try{
            // std::cout << "creating new createNewVLRStorageManager " << filename << std::endl;            
            storage = returnMemoryStorageManager(m_properties);
            return storage;
        } catch (Tools::Exception& e) {
            std::ostringstream os;
            os << "Spatial Index Error: " << e.what();
            throw std::runtime_error(os.str());
        } 
                    
    }
    return storage;               
}




void Index::Initialize()
{
    m_storage = CreateStorage();
    m_buffer = CreateIndexBuffer(*m_storage);
    m_rtree = CreateIndex();
}

void Index::Setup()

{   
    m_buffer = 0;
    m_storage = 0;
    m_rtree = 0;
}

RTIndexType Index::GetIndexType() 
{
    Tools::Variant var;
    var = m_properties.getProperty("IndexType");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG)
            throw std::runtime_error("Index::GetIndexType: Property IndexType must be Tools::VT_ULONG");
        
        return static_cast<RTIndexType>(var.m_val.ulVal);
    }
    
    // if we didn't get anything, we're returning an error condition
    return RT_InvalidIndexType;
    
}
void Index::SetIndexType(RTIndexType v)
{
    Tools::Variant var;
    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = v;
    m_properties.setProperty("IndexType", var);
}

RTStorageType Index::GetIndexStorage()
{

    Tools::Variant var;
    var = m_properties.getProperty("IndexStorageType");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG)
            throw std::runtime_error("Index::GetIndexStorage: Property IndexStorageType must be Tools::VT_ULONG");
        
        return static_cast<RTStorageType>(var.m_val.ulVal);
    }
    
    // if we didn't get anything, we're returning an error condition
    return RT_InvalidStorageType;
}

void Index::SetIndexStorage(RTStorageType v)
{
    Tools::Variant var;
    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = v;
    m_properties.setProperty("IndexStorageType", var);
}

RTIndexVariant Index::GetIndexVariant()
{

    Tools::Variant var;
    var = m_properties.getProperty("TreeVariant");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG)
            throw std::runtime_error("Index::GetIndexVariant: Property TreeVariant must be Tools::VT_ULONG");
        
        return static_cast<RTIndexVariant>(var.m_val.ulVal);
    }
    
    // if we didn't get anything, we're returning an error condition
    return RT_InvalidIndexVariant;
}

void Index::SetIndexVariant(RTStorageType v)
{
    using namespace SpatialIndex;
    Tools::Variant var;

    if (GetIndexType() == RT_RTree) {
        var.m_val.ulVal = static_cast<RTree::RTreeVariant>(v);
        m_properties.setProperty("TreeVariant", var);
    } else if (GetIndexType() == RT_MVRTree) {
        var.m_val.ulVal = static_cast<MVRTree::MVRTreeVariant>(v);
        m_properties.setProperty("TreeVariant", var);   
    } else if (GetIndexType() == RT_TPRTree) {
        var.m_val.ulVal = static_cast<TPRTree::TPRTreeVariant>(v);
        m_properties.setProperty("TreeVariant", var);   
    }
}