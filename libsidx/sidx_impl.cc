#include "sidx_impl.hpp"

Item::Item(uint64_t id)
{
    m_id = id;
    m_data = 0;
}

Item::~Item()
{
    if (m_data != 0)
        delete m_data;
}

void Item::SetData(uint8_t* data, uint64_t length) 
{
    m_data = new uint8_t[length];
}

Visitor::Visitor()
{
}

Visitor::~Visitor()
{
    std::vector<Item*>::iterator it;
    for (it = m_vector.begin(); it != m_vector.end(); it++) {
        delete *it;
    }

}

void Visitor::visitNode(const SpatialIndex::INode& n)
{
            std::cout << "visitNode" << std::endl;
    if (n.isLeaf()) m_leafIO++;
    else m_indexIO++;
}

void Visitor::visitData(const SpatialIndex::IData& d)
{
    SpatialIndex::IShape* pS;
    d.getShape(&pS);
    SpatialIndex::Region *r = new SpatialIndex::Region();
    pS->getMBR(*r);
    std::cout <<"found shape: " << *r << " dimension: " <<pS->getDimension() << std::endl;

    delete pS;
    delete r;

    // data should be an array of characters representing a Region as a string.
    uint8_t* data = 0;
    size_t length = 0;
    d.getData(length, &data);

    Item* item = new Item(d.getIdentifier());
    item->SetData(data, length);


    delete[] data;

    m_vector.push_back(item);
}

void Visitor::visitData(std::vector<const SpatialIndex::IData*>& v)
{
    std::cout << v[0]->getIdentifier() << " " << v[1]->getIdentifier() << std::endl;
}



SpatialIndex::ISpatialIndex* Index::CreateIndex() 
{
    using namespace SpatialIndex;
    
    ISpatialIndex* index = 0;
    
    

    
    if (m_properties->type == RT_RTree) {
        RTree::RTreeVariant variant;

        if (m_properties->variant == RT_Linear) variant = RTree::RV_LINEAR;
        if (m_properties->variant == RT_Quadratic) variant = RTree::RV_QUADRATIC;
        if (m_properties->variant == RT_Star) variant = RTree::RV_RSTAR;
        try{
            index = RTree::createNewRTree(  *m_buffer, 
                                            0.7, 
                                            m_properties->index_capacity,
                                            m_properties->leaf_capacity,
                                            m_properties->dimension,
                                            variant,
                                            m_idxId); 

            bool ret = index->isIndexValid();
            if (ret == false) 
                throw std::runtime_error(   "Spatial index error: index is not "
                                            "valid after createNewRTree");

            return index;
        } catch (Tools::Exception& e) {
            std::ostringstream os;
            os << "Spatial Index Error: " << e.what();
            throw std::runtime_error(os.str());
        }    
    }

    else if (m_properties->type == RT_MVRTree) {
        MVRTree::MVRTreeVariant variant;

        if (m_properties->variant == RT_Linear) variant = MVRTree::RV_LINEAR;
        if (m_properties->variant == RT_Quadratic) variant = MVRTree::RV_QUADRATIC;
        if (m_properties->variant == RT_Star) variant = MVRTree::RV_RSTAR;

        try{
            index = MVRTree::createNewMVRTree(  *m_buffer, 
                                            0.7, 
                                            m_properties->index_capacity,
                                            m_properties->leaf_capacity,
                                            m_properties->dimension,
                                            variant,
                                            m_idxId); 

            bool ret = index->isIndexValid();
            if (ret == false) 
                throw std::runtime_error(   "Spatial index error: index is not "
                                            "valid after createNewMVRTree");

            return index;
        } catch (Tools::Exception& e) {
            std::ostringstream os;
            os << "Spatial Index Error: " << e.what();
            throw std::runtime_error(os.str());
        }   
    }

    else if (m_properties->type == RT_TPRTree) {
        TPRTree::TPRTreeVariant variant =  TPRTree::TPRV_RSTAR;


        try{
            index = TPRTree::createNewTPRTree(  *m_buffer, 
                                            0.7, 
                                            m_properties->index_capacity,
                                            m_properties->leaf_capacity,
                                            m_properties->dimension,
                                            variant,
                                            m_properties->tpr_horizon,
                                            m_idxId); 

            bool ret = index->isIndexValid();
            if (ret == false) 
                throw std::runtime_error(   "Spatial index error: index is not "
                                            "valid after createNewMVRTree");

            return index;
        } catch (Tools::Exception& e) {
            std::ostringstream os;
            os << "Spatial Index Error: " << e.what();
            throw std::runtime_error(os.str());
        }   
    }    
}


Index::Index(const char* pszFilename, const IndexProperties* poProperties) 
{
    
    Setup();
    
    std::string m_idxFilename = std::string(pszFilename);
    
    bool m_Initialized;
    bool m_idxExists;
    SpatialIndex::id_type m_idxId;
    
    IndexProperties* m_properties = new IndexProperties;
    m_properties->type = poProperties->type;
    m_properties->storage = poProperties->storage;
    m_properties->dimension = poProperties->dimension;
    m_properties->index_capacity = poProperties->index_capacity;
    m_properties->leaf_capacity = poProperties->leaf_capacity;
    m_properties->pagesize = poProperties->pagesize;
    m_properties->tpr_horizon = poProperties->tpr_horizon;
    Initialize();
}


Index::~Index() 
{
    std::cout << "~Index called" << std::endl;
    
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
        buffer = createNewRandomEvictionsBuffer(storage,
                                                10,
                                                false);
    } catch (Tools::Exception& e) {
        std::ostringstream os;
        os << "Spatial Index Error: " << e.what();
        throw std::runtime_error(os.str());
    }
    return buffer;
}

SpatialIndex::ISpatialIndex* Index::LoadIndex() 
{
    using namespace SpatialIndex;
    
    ISpatialIndex* index = 0;
    
    try{
        index = RTree::loadRTree(*m_buffer,m_idxId);
        bool ret = index->isIndexValid();
        if (ret == false) 
            throw std::runtime_error(   "Spatial index error: index is not"
                                        " valid after loadRTree");

        return index;
    } catch (Tools::Exception& e) {
        std::ostringstream os;
        os << "Spatial Index Error: " << e.what();
        throw std::runtime_error(os.str());
    }    
}

SpatialIndex::IStorageManager* Index::CreateStorage(std::string& filename)
{
    using namespace SpatialIndex::StorageManager;
    
    std::cout << "index type:" << m_properties->type << std::endl;
    SpatialIndex::IStorageManager* storage = 0;
    if (m_properties->storage == RT_Disk) {

        if (ExternalIndexExists(filename) && !filename.empty()) {
            std::cout << "loading existing DiskStorage " << filename << std::endl;
            try{
                storage = loadDiskStorageManager(filename);
                m_idxExists = true;
                return storage;
            } catch (Tools::Exception& e) {
                std::ostringstream os;
                os << "Spatial Index Error: " << e.what();
                throw std::runtime_error(os.str());
            } 
        } else if (!filename.empty()){
            try{
                std::cout << "creating new DiskStorage " << filename << std::endl;            
                storage = createNewDiskStorageManager(filename, m_properties->pagesize);
                m_idxExists = false;
                return storage;
            } catch (Tools::Exception& e) {
                std::ostringstream os;
                os << "Spatial Index Error: " << e.what();
                throw std::runtime_error(os.str());
            }         
        }
    } else if (m_properties->storage == RT_Memory) {

        try{
            std::cout << "creating new createNewVLRStorageManager " << filename << std::endl;            
            storage = createNewMemoryStorageManager();
            m_idxExists = false;
            return storage;
        } catch (Tools::Exception& e) {
            std::ostringstream os;
            os << "Spatial Index Error: " << e.what();
            throw std::runtime_error(os.str());
        } 
                    
    }
    return storage;               
}


bool Index::ExternalIndexExists(std::string& filename)
{
    struct stat stats;
    std::ostringstream os;
    os << filename << ".dat";
    
    // if we have already checked, we're done.
    if (m_idxExists == true) return true;

    std::string indexname = os.str();
    
    // ret is -1 for no file existing and 0 for existing
    int ret = stat(indexname.c_str(),&stats);

    bool output = false;
    if (ret == 0) output= true; else output =false;
    return output;
}


void Index::Initialize()
{
    m_storage = CreateStorage(m_idxFilename);
    
    m_buffer = CreateIndexBuffer(*m_storage);

    if (m_idxExists == true) {
        std::cout << "loading existing index from file " << std::endl;
        m_rtree = LoadIndex();
    }
    else
    {
        m_rtree = CreateIndex();
    }
    
    m_Initialized = true;
}

void Index::Setup()

{   

    m_idxExists = false;
    
    m_idxFilename = std::string("");
    m_Initialized = false;
    m_idxId = 1;
    
    m_buffer = 0;
    m_storage = 0;
    m_rtree = 0;
}
