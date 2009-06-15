#include <stack>
#include <string>
#include <vector>
#include <stdexcept>

#ifdef _MSC_VER
#include "SpatialIndex.h"
#else
#include <spatialindex/SpatialIndex.h>
#endif

#include "sidx_config.h"

class Item 
{
private:
    uint64_t m_id;
    uint8_t* m_data;
    
    // block copy operations
    Item(Item const& other);
    Item& operator=(Item const& other);
    
public:
    Item(uint64_t);
    ~Item();
    void SetData(uint8_t* data, uint64_t length);
};

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
    Index(const char* pszFilename, const IndexProperties* poProperties);
    ~Index();

    IndexProperties* GetProperties() { return m_properties; }

    bool insertFeature(uint64_t id, double *min, double *max);

private:

    void Initialize();
    SpatialIndex::IStorageManager* m_storage;
    SpatialIndex::StorageManager::IBuffer* m_buffer;
    SpatialIndex::ISpatialIndex* m_rtree;
    std::string m_idxFilename;
    
    bool m_Initialized;
    bool m_idxExists;
    SpatialIndex::id_type m_idxId;
    
    IndexProperties* m_properties;
    
    


    void Setup();
    SpatialIndex::IStorageManager* CreateStorage(std::string& filename);
    SpatialIndex::StorageManager::IBuffer* CreateIndexBuffer(SpatialIndex::IStorageManager& storage);
    SpatialIndex::ISpatialIndex* CreateIndex();
    SpatialIndex::ISpatialIndex* LoadIndex();
    bool ExternalIndexExists(std::string& filename);
};
