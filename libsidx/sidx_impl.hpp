/******************************************************************************
 * $Id$
 *
 * Project:  libsidx - A C API wrapper around libspatialindex
 * Purpose:  C++ object declarations to implement the wrapper.
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
 
#include <stack>
#include <string>
#include <vector>
#include <stdexcept>
#include <sstream>
#include <cstring>

#ifdef _MSC_VER
#include "SpatialIndex.h"
#include <windows.h>
#define STRDUP _strdup
#else
#include <spatialindex/SpatialIndex.h>
#define STRDUP strdup
#endif

#include "sidx_config.h"

Tools::PropertySet* GetDefaults();

class Item 
{
private:
    uint64_t m_id;
    uint8_t* m_data;
    SpatialIndex::Region* m_bounds;
    uint64_t m_length;

public:
    Item(uint64_t id);
    ~Item();

    Item(Item const& other);
    Item& operator=(Item const& other);
    
    uint64_t GetID() const { return m_id; }
    
    void SetData(const uint8_t* data, uint64_t length);
    void GetData(uint8_t** data, uint64_t* length);
    const SpatialIndex::Region* GetBounds() const;
    void SetBounds(const SpatialIndex::Region* );
};

class ObjVisitor : public SpatialIndex::IVisitor
{
private:
    size_t m_indexIO;
    size_t m_leafIO;
    std::vector<Item*> m_vector;
    uint32_t nResults;

public:

    ObjVisitor();
    ~ObjVisitor();

    uint32_t GetResultCount() const { return nResults; }
    std::vector<Item*>& GetResults()  { return m_vector; }
    
    void visitNode(const SpatialIndex::INode& n);
    void visitData(const SpatialIndex::IData& d);
    void visitData(std::vector<const SpatialIndex::IData*>& v);
};

class IdVisitor : public SpatialIndex::IVisitor
{
private:
    std::vector<uint64_t> m_vector;
    uint32_t nResults;

public:

    IdVisitor();
    ~IdVisitor();

    uint32_t GetResultCount() const { return nResults; }
    std::vector<uint64_t>& GetResults()  { return m_vector; }
    
    void visitNode(const SpatialIndex::INode& n);
    void visitData(const SpatialIndex::IData& d);
    void visitData(std::vector<const SpatialIndex::IData*>& v);
};



class BoundsQuery : public SpatialIndex::IQueryStrategy
{
private:
    SpatialIndex::Region* m_bounds;
    
public:

    BoundsQuery();
    ~BoundsQuery() { if (m_bounds !=0) delete m_bounds;}
    void getNextEntry(  const SpatialIndex::IEntry& entry, 
                        SpatialIndex::id_type& nextEntry, 
                        bool& hasNext);
    
    SpatialIndex::Region* GetBounds() const {return m_bounds; }
};

class Error
{
public:

    Error(int code, std::string const& message, std::string const& method);

    /// Copy constructor.
    Error(Error const& other);

    /// Assignment operator.
    Error& operator=(Error const& rhs);

    int GetCode() const { return m_code; };
    const char* GetMessage() const { return m_message.c_str(); };
    const char* GetMethod() const { return m_method.c_str(); };    

private:

    int m_code;
    std::string m_message;
    std::string m_method;
};


class DataStream : public SpatialIndex::IDataStream
{
public:
    DataStream(int (*readNext)(SpatialIndex::id_type* id, double *pMin, double *pMax, uint32_t nDimension, const uint8_t* pData, size_t nDataLength));
    ~DataStream();

    SpatialIndex::IData* getNext();
    bool hasNext() throw (Tools::NotSupportedException);

    size_t size() throw (Tools::NotSupportedException);
    void rewind() throw (Tools::NotSupportedException);

protected:
    SpatialIndex::RTree::Data* m_pNext;
    SpatialIndex::id_type m_id;

private:
    int (*iterfunct)(SpatialIndex::id_type* id, double *pMin, double *pMax, uint32_t nDimension, const uint8_t* pData, size_t nDataLength);
    
    bool readData();

};


class Index
{

public:
    Index(const Tools::PropertySet& poProperties);
    ~Index();

    const Tools::PropertySet& GetProperties() { return m_properties; }

    bool insertFeature(uint64_t id, double *min, double *max);
    
    RTIndexType GetIndexType();
    void SetIndexType(RTIndexType v);

    RTStorageType GetIndexStorage();
    void SetIndexStorage(RTStorageType v);
    
    RTIndexVariant GetIndexVariant();
    void SetIndexVariant(RTStorageType v);
    
    SpatialIndex::ISpatialIndex& index() {return *m_rtree;}
private:

    void Initialize();
    SpatialIndex::IStorageManager* m_storage;
    SpatialIndex::StorageManager::IBuffer* m_buffer;
    SpatialIndex::ISpatialIndex* m_rtree;
    
    Tools::PropertySet m_properties;


    void Setup();
    SpatialIndex::IStorageManager* CreateStorage();
    SpatialIndex::StorageManager::IBuffer* CreateIndexBuffer(SpatialIndex::IStorageManager& storage);
    SpatialIndex::ISpatialIndex* CreateIndex();
};
