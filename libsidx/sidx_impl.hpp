#include <stack>
#include <string>
#include <vector>
#include <stdexcept>
#include <sstream>

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

class Error
{
public:

    Error(int code, std::string const& message, std::string const& method);

    /// Copy constructor.
    Error(Error const& other);

    /// Assignment operator.
    Error& operator=(Error const& rhs);

    // TODO - mloskot: What about replacing string return by copy with const char* ?
    //        char const* GetMethod() const { return m_method.c_str(); }, etc.

    int GetCode() const { return m_code; };
    const char* GetMessage() const { return m_message.c_str(); };
    const char* GetMethod() const { return m_method.c_str(); };    

private:

    int m_code;
    std::string m_message;
    std::string m_method;
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


class IndexProperty
{

public:
    IndexProperty();
    ~IndexProperty() {};

    IndexProperty& operator=(IndexProperty const& rhs);
    IndexProperty(IndexProperty const& other);
        
    RTIndexType GetIndexType() const {return m_type;}
    void SetIndexType( RTIndexType& v ) {m_type = v;}
    
    uint32_t GetDimension() const {return m_dimension;}
    void SetDimension( uint32_t& v ) {m_dimension = v;}
    
    RTIndexVariant GetIndexVariant() const { return m_variant; }
    void SetIndexVariant( RTIndexVariant& v ) { m_variant = v; }
    
    RTStorageType GetIndexStorage() const { return m_storage; }
    void SetIndexStorage( RTStorageType& v ) { m_storage = v; }

    uint32_t GetIndexCapacity() const { return m_index_capacity; }
    void SetIndexCapacity( uint32_t& v ) { m_index_capacity = v; }
    
    uint32_t GetLeafCapacity() const { return m_leaf_capacity; }
    void SetLeafCapacity( uint32_t& v ) { m_leaf_capacity = v; }

    uint32_t GetPagesize() const { return m_pagesize; }
    void SetPagesize( uint32_t& v ) { m_pagesize = v; }
    
    double GetTPRHorizon() const { return m_tpr_horizon; }
    void SetTPRHorizon( double& v ) { m_tpr_horizon = v; }
    
    double GetFillFactor() const { return m_fillfactor; }
    void SetFillFactor( double& v ) { m_fillfactor = v; }

private:

    RTIndexType m_type;
    uint32_t m_dimension;
    RTIndexVariant m_variant;
    RTStorageType m_storage;
    uint32_t m_index_capacity;
    uint32_t m_leaf_capacity;
    uint32_t m_pagesize;
    double m_tpr_horizon;
    double m_fillfactor;
};

class Index
{

public:
    Index(const char* pszFilename, const IndexProperty& poProperties);
    ~Index();

    const IndexProperty& GetProperties() { return m_properties; }

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
    
    IndexProperty m_properties;
    
    


    void Setup();
    SpatialIndex::IStorageManager* CreateStorage(std::string& filename);
    SpatialIndex::StorageManager::IBuffer* CreateIndexBuffer(SpatialIndex::IStorageManager& storage);
    SpatialIndex::ISpatialIndex* CreateIndex();
    SpatialIndex::ISpatialIndex* LoadIndex();
    bool ExternalIndexExists(std::string& filename);
};
