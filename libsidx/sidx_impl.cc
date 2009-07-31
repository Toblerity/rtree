/******************************************************************************
 * $Id$
 *
 * Project:  libsidx - A C API wrapper around libspatialindex
 * Purpose:  C++ objects to implement the wrapper.
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

Item::Item( uint64_t id): 
            m_data(0), 
            m_bounds(0), 
            m_length(0)
{
    m_id = id;
}

Item::~Item()
{
    if (m_data != 0)
        delete m_data;
    if (m_bounds != 0)
        delete m_bounds;
}

Item::Item(Item const& other) : m_id(other.m_id), 
                                m_length(other.m_length)
{
    void *p = 0;
    if (m_length > 0) {
        m_data = new uint8_t[m_length];
        p = std::memcpy(m_data, other.m_data, m_length);
    } else
        m_data = 0;

    if (other.m_bounds != 0) 
        m_bounds = other.m_bounds->clone();
    else 
        m_bounds = 0;
    
}

Item& Item::operator=(Item const& rhs)
{

    if (&rhs != this )
    {
        void *p = 0;
        m_id = rhs.m_id;
        m_length = rhs.m_length;

        if (m_length > 0) {
            m_data = new uint8_t[m_length];
            p = std::memcpy(m_data, rhs.m_data, m_length);
        } else
            m_data = 0;
            
        if (rhs.m_bounds != 0)
            m_bounds = rhs.m_bounds->clone();
        else 
            m_bounds = 0;
    }
    return *this;
}
    
void Item::SetData(const uint8_t* data, uint64_t length) 
{
    m_length = length;
    
    // Don't do anything if we have no length
    if (m_length < 1) return;
    
    m_data = new uint8_t[length];
    
    if (length > 0 && m_data != 0) {
        memcpy(m_data, data, length);
    }
}

void Item::GetData(uint8_t** data, uint64_t *length) 
{
    *length = m_length;
    *data = m_data;
}

const SpatialIndex::Region* Item::GetBounds() const 
{
    if (m_bounds == 0) 
        return 0;
    else
        return m_bounds;
}

void Item::SetBounds( const SpatialIndex::Region* b)
{
    m_bounds = new SpatialIndex::Region(*b);
}

ObjVisitor::ObjVisitor(): nResults(0)
{
}

ObjVisitor::~ObjVisitor()
{
    std::vector<Item*>::iterator it;
    for (it = m_vector.begin(); it != m_vector.end(); it++) {
        delete *it;
    }

}

void ObjVisitor::visitNode(const SpatialIndex::INode& n)
{
    if (n.isLeaf()) m_leafIO++;
    else m_indexIO++;
}

void ObjVisitor::visitData(const SpatialIndex::IData& d)
{
    SpatialIndex::IShape* pS;
    d.getShape(&pS);
    SpatialIndex::Region *r = new SpatialIndex::Region();
    pS->getMBR(*r);
    // std::cout <<"found shape: " << *r << " dimension: " <<pS->getDimension() << std::endl;


    // data should be an array of characters representing a Region as a string.
    uint8_t* data = 0;
    size_t length = 0;
    d.getData(length, &data);

    Item* item = new Item(d.getIdentifier());
    item->SetData(data, length);
    item->SetBounds(r);


    delete pS;
    delete r;
    delete[] data;
    
    nResults += 1;
    
    m_vector.push_back(item);
}

void ObjVisitor::visitData(std::vector<const SpatialIndex::IData*>& v)
{
    // std::cout << v[0]->getIdentifier() << " " << v[1]->getIdentifier() << std::endl;
}


IdVisitor::IdVisitor(): nResults(0)
{
}

IdVisitor::~IdVisitor()
{

}

void IdVisitor::visitNode(const SpatialIndex::INode& n)
{

}

void IdVisitor::visitData(const SpatialIndex::IData& d)
{
    nResults += 1;
    
    m_vector.push_back(d.getIdentifier());
}

void IdVisitor::visitData(std::vector<const SpatialIndex::IData*>& v)
{
}

BoundsQuery::BoundsQuery() 
{
    m_bounds = new SpatialIndex::Region;
}

void BoundsQuery::getNextEntry( const SpatialIndex::IEntry& entry, 
                                SpatialIndex::id_type& nextEntry, 
                                bool& hasNext) 
{
    SpatialIndex::IShape* ps;
    entry.getShape(&ps);
    ps->getMBR(*m_bounds);
    delete ps;
        
    hasNext = false;
}



DataStream::DataStream(int (*readNext)(SpatialIndex::id_type * id, double *pMin, double *pMax, uint32_t nDimension, const uint8_t* pData, size_t nDataLength)) :m_pNext(0)
{
    iterfunct = readNext;
    bool read = readData();
}

DataStream::~DataStream()
{
    if (m_pNext != 0) delete m_pNext;
}

bool DataStream::readData()
{
    SpatialIndex::id_type* id=0;
    double **pMin=0;
    double **pMax=0;
    uint32_t *nDimension=0;
    const uint8_t** pData=0;
    size_t *nDataLength=0;
    
    int ret = iterfunct(id, *pMin, *pMax, *nDimension, *pData, *nDataLength);

    // The callback should return anything other than 0 
    // when it is done.
    if (ret) return false;
    

    SpatialIndex::Region r = SpatialIndex::Region(*pMin, *pMax, *nDimension);
    m_pNext = new SpatialIndex::RTree::Data(*nDataLength, (byte*)*pData, r, *id);
    
     // std::cout << "Read point " << r <<  "Id: " << m_id << std::endl;
    return true;
}


SpatialIndex::IData* DataStream::getNext()
{
    if (m_pNext == 0) return 0;

    SpatialIndex::RTree::Data* ret = m_pNext;
    m_pNext = 0;
    readData();
    return ret;
}

bool DataStream::hasNext() throw (Tools::NotSupportedException)
{
    std::cout << "LASIndexDataStream::hasNext called ..." << std::endl;
    return (m_pNext != 0);
}

size_t DataStream::size() throw (Tools::NotSupportedException)
{
    throw Tools::NotSupportedException("Operation not supported.");
}

void DataStream::rewind() throw (Tools::NotSupportedException)
{
    throw Tools::NotSupportedException("Operation not supported.");
    std::cout << "LASIndexDataStream::rewind called..." << std::endl;

    // if (m_pNext != 0)
    // {
    //  delete m_pNext;
    //  m_pNext = 0;
    // }
}

Error::Error(int code, std::string const& message, std::string const& method) :
    m_code(code),
    m_message(message),
    m_method(method)
{
}

Error::Error(Error const& other) :
    m_code(other.m_code),
    m_message(other.m_message),
    m_method(other.m_method)
{
}

Error& Error::operator=(Error const& rhs)
{
    if (&rhs != this)
    {
        m_code = rhs.m_code;
        m_message = rhs.m_message;
        m_method = rhs.m_method;

    }
    return *this;
}

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

Tools::PropertySet* GetDefaults()
{
    Tools::PropertySet* ps = new Tools::PropertySet;
    
    Tools::Variant var;
    
    // Rtree defaults
    
    var.m_varType = Tools::VT_DOUBLE;
    var.m_val.dblVal = 0.7;
    ps->setProperty("FillFactor", var);
    
    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 100;
    ps->setProperty("IndexCapacity", var);
    
    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 100;
    ps->setProperty("LeafCapacity", var);
    
    var.m_varType = Tools::VT_LONG;
    var.m_val.lVal = SpatialIndex::RTree::RV_RSTAR;
    ps->setProperty("TreeVariant", var);

    // var.m_varType = Tools::VT_LONGLONG;
    // var.m_val.llVal = 0;
    // ps->setProperty("IndexIdentifier", var);
    
    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 32;
    ps->setProperty("NearMinimumOverlapFactor", var);
    
    var.m_varType = Tools::VT_DOUBLE;
    var.m_val.dblVal = 0.4;
    ps->setProperty("SplitDistributionFactor", var);

    var.m_varType = Tools::VT_DOUBLE;
    var.m_val.dblVal = 0.3;
    ps->setProperty("ReinsertFactor", var);

    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 2;
    ps->setProperty("Dimension", var);
        
    var.m_varType = Tools::VT_BOOL;
    var.m_val.bVal = true;
    ps->setProperty("EnsureTightMBRs", var);
    
    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 100;
    ps->setProperty("IndexPoolCapacity", var);
    
    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 100;
    ps->setProperty("LeafPoolCapacity", var);

    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 1000;
    ps->setProperty("RegionPoolCapacity", var);

    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 500;
    ps->setProperty("PointPoolCapacity", var);

    // horizon for TPRTree
    var.m_varType = Tools::VT_DOUBLE;
    var.m_val.dblVal = 20.0;
    ps->setProperty("Horizon", var);
    
    // Buffering defaults
    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 10;
    ps->setProperty("Capacity", var);
    
    var.m_varType = Tools::VT_BOOL;
    var.m_val.bVal = false;
    ps->setProperty("WriteThrough", var);
    
    // Disk Storage Manager defaults
    var.m_varType = Tools::VT_BOOL;
    var.m_val.bVal = true;
    ps->setProperty("Overwrite", var);
    
    var.m_varType = Tools::VT_PCHAR;
    var.m_val.pcVal = const_cast<char*>("");
    ps->setProperty("FileName", var);
    
    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = 4096;
    ps->setProperty("PageSize", var);
    
    // Our custom properties related to whether 
    // or not we are using a disk or memory storage manager

    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = RT_Disk;
    ps->setProperty("IndexStorageType", var);

    var.m_varType = Tools::VT_ULONG;
    var.m_val.ulVal = RT_RTree;
    ps->setProperty("IndexType", var);

    var.m_varType = Tools::VT_PCHAR;
    var.m_val.pcVal = const_cast<char*>("dat");
    ps->setProperty("FileNameDat", var);

    var.m_varType = Tools::VT_PCHAR;
    var.m_val.pcVal = const_cast<char*>("idx");
    ps->setProperty("FileNameIdx", var);
    return ps;
}