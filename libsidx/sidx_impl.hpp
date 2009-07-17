#include <stack>
#include <string>
#include <vector>
#include <stdexcept>
#include <sstream>

#ifdef _MSC_VER
#include "SpatialIndex.h"
#include <windows.h>
#else
#include <spatialindex/SpatialIndex.h>
#include <pthread.h>
#define HAVE_PTHREAD_H 1
#endif

#include "sidx_config.h"

class Item 
{
private:
    uint64_t m_id;
    uint8_t* m_data;
    uint32_t m_length;
    
    // block copy operations
    Item(Item const& other);
    Item& operator=(Item const& other);
    
public:
    Item(uint64_t id);
    ~Item();
    void SetData(const uint8_t* data, uint64_t length);
    void GetData(uint8_t* data, uint64_t* length);
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

class Lock
{
public:

    Lock() {};
    ~Lock() {};
private:
    
}; // Lock


class Shared : public Lock
{
public:

#if HAVE_PTHREAD_H
    Shared(pthread_rwlock_t* pLock) : m_pLock(pLock) {pthread_rwlock_rdlock(m_pLock);}
    ~Shared() {pthread_rwlock_unlock(m_pLock);}
private:
    pthread_rwlock_t* m_pLock;
#endif

}; // Shared


class Exclusive
{
public:
#if HAVE_PTHREAD_H
    Exclusive(pthread_rwlock_t* pLock): m_pLock(pLock) {pthread_rwlock_wrlock(m_pLock);}
    ~Exclusive() {pthread_rwlock_unlock(m_pLock);}

private:
    pthread_rwlock_t* m_pLock;
#endif
}; // ExclusiveLock


class Visitor : public SpatialIndex::IVisitor
{
private:
    size_t m_indexIO;
    size_t m_leafIO;
    std::vector<Item*> m_vector;
    std::string m_idxFilename;
    

public:

    Visitor();
    ~Visitor();

    void visitNode(const SpatialIndex::INode& n);
    void visitData(const SpatialIndex::IData& d);
    void visitData(std::vector<const SpatialIndex::IData*>& v);
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
    
    bool m_Initialized;
    bool m_idxExists;
    SpatialIndex::id_type m_idxId;
    
    RTIndexType m_idxType;
    RTStorageType m_idxStorage;
    
    Tools::PropertySet m_properties;


    void Setup();
    SpatialIndex::IStorageManager* CreateStorage();
    SpatialIndex::StorageManager::IBuffer* CreateIndexBuffer(SpatialIndex::IStorageManager& storage);
    SpatialIndex::ISpatialIndex* CreateIndex();
    SpatialIndex::ISpatialIndex* LoadIndex();
    bool ExternalIndexExists(std::string& filename);
};
