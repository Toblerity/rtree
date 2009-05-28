/*
# =============================================================================
# Rtree spatial index. Copyright (C) 2007 Sean C. Gillies
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
# Contact email: sgillies@frii.com
# =============================================================================
*/

#include <Python.h>
#include "wrapper.h"


#ifdef _MSC_VER
#include "SpatialIndex.h"
#else
#include <spatialindex/SpatialIndex.h>
#endif

using namespace SpatialIndex;

typedef struct {
    PyObject_HEAD
    RtreeIndex index;
} Rtree;

/* Alloc/dealloc */

static void
Rtree_dealloc(Rtree *self)
{
    RtreeIndex_del(self->index);
    self->ob_type->tp_free((PyObject*) self);
}

static int
Rtree_init(Rtree *self, PyObject *args, PyObject *kwds)
{
    char* basename = NULL;
    char filename[256];
    unsigned long nPageLength = 0;
    int overwrite = 0;
    int load = -1;
    PyObject *os_module;
    PyObject *path_module;
    PyObject *abspath, *dirname;
    PyObject *func;

    static char *kwlist[] = {"basename", "pagesize", "overwrite", NULL};

    if (!PyArg_ParseTupleAndKeywords(
            args, kwds, "|sii", kwlist,
            &basename, (unsigned long)&nPageLength, &overwrite
            )
        )
        return -1;

    // Import os and os.path
    os_module = PyImport_ImportModule("os");
    path_module = PyImport_ImportModule("os.path");

    if (basename)
    {
        snprintf(filename, 256, "%s.dat", basename);
 
        // Bail out if we don't have write access
        func = PyObject_GetAttrString(path_module, "abspath");
        abspath = PyObject_CallFunction(func, "s", filename);
        func = PyObject_GetAttrString(path_module, "dirname");
        dirname = PyObject_CallFunctionObjArgs(func, abspath, NULL);

        func = PyObject_GetAttrString(os_module, "access");
        if (!PyObject_IsTrue(PyObject_CallFunctionObjArgs(func, dirname, PyObject_GetAttrString(os_module, "W_OK"), NULL)))
        {
            PyErr_Format(PyExc_IOError,
                "Unable to open file '%s' for index storage",
                basename
                );
            return -1;
        }

        // Check for existence with os.path.exists
        func = PyObject_GetAttrString(path_module, "exists");
        if (PyObject_IsTrue(PyObject_CallFunction(func, "s", filename)))
        {
            if (overwrite == 0)
                load = 1;
            else
                load = 0;
        }
        else
            load = 0;
    }

	try {
        self->index = RtreeIndex_new(basename, nPageLength, load);
        return 0;
	}

    catch (Tools::Exception& e) {
        PyErr_SetString(PyExc_TypeError, e.what().c_str());
        return -1;
    }

	catch (...)
	{
        PyErr_SetString(PyExc_RuntimeError, "Unknown Exception");
        return -1;
	}
}

/* Methods */

static int
processbounds(PyObject *binput, double min[2], double max[2], int minsize)
{
    int size, i;
    int ret = 0;

    PyObject *bounds = NULL;
    PyObject *omin[2];
    PyObject *omax[2];

    omin[0] = NULL; omin[1] = NULL;
    omax[0] = NULL; omax[1] = NULL;

    bounds =  PySequence_Fast(binput, "Bounds must be a sequence");
    if(bounds == NULL)
        return -1;

    size = (int) PySequence_Fast_GET_SIZE(bounds);

    if (size < minsize)
    {
        PyErr_Format(PyExc_TypeError,
            "Bounds argument must be sequence of length %d, not %d",
            minsize, size);

        ret = -1;
        goto error;
    }

    if (size == 2)
    {
        omin[0] = PySequence_Fast_GET_ITEM(bounds, 0);
        omax[0] = PySequence_Fast_GET_ITEM(bounds, 1);
        min[0] = max[0] =  PyFloat_AsDouble(omin[0]);
        min[1] = max[1] =  PyFloat_AsDouble(omax[0]);
    }
    else if (size == 4)
    {
        for(i = 0; i < 2; i++)
        {
            omin[i] = PySequence_Fast_GET_ITEM(bounds, i);
            omax[i] = PySequence_Fast_GET_ITEM(bounds, i+2);
            min[i] =  PyFloat_AsDouble(omin[i]);
            max[i] =  PyFloat_AsDouble(omax[i]);
        }
    }
    else
    {
        PyErr_Format(PyExc_TypeError,
            "Bounds argument must be sequence of length 2 or 4, not %d",
             size);
        ret = -1;
        goto error;
    }

    if(PyErr_Occurred())
    {
        ret = -1;
        goto error;
    }

    /* Check validity of bounds */
    if (min[0] > max[0] || min[1] > max[1])
    {
        PyErr_SetString(PyExc_ValueError,
             "Bounding box is invalid: maxx < miny or maxy < miny");
        ret = -1;
        goto error;
    }

error:
    Py_XDECREF(bounds);
    return ret;
}

static PyObject *
Rtree_add(Rtree *self, PyObject *args)
{
    double min[2], max[2];
    uint64_t id;
    PyObject *binput=NULL;

    if (!PyArg_ParseTuple(args, "LO", &id, &binput))
        return NULL;

    if (processbounds(binput, min, max, 2) < 0)
        return NULL;

    if (RtreeIndex_insertData(self->index, id, min, max) ) {
        Py_INCREF(Py_None);
        return Py_None;
    }

    return NULL;
}

static PyObject *
Rtree_deleteData(Rtree *self, PyObject *args)
{
    double min[2], max[2];
    uint64_t id;
    PyObject *binput=NULL;

    if (!PyArg_ParseTuple(args, "LO", &id, &binput))
        return NULL;

    if (processbounds(binput, min, max, 2) < 0)
        return NULL;

    if (RtreeIndex_deleteData(self->index, id, min, max) ) {
        Py_INCREF(Py_None);
        return Py_None;
    }

    return NULL;
}

static PyObject *
Rtree_intersection(Rtree *self, PyObject *args)
{
    double min[2], max[2];
    PyObject *binput = NULL;

    if (!PyArg_ParseTuple(args, "O", &binput))
        return NULL;

    if (processbounds(binput, min, max, 4) < 0)
        return NULL;

    return RtreeIndex_intersects(self->index, min, max);
}

static PyObject *
Rtree_nearsetNeighbors(Rtree *self, PyObject *args)
{
    double min[2], max[2];
    uint32_t num_results;
    PyObject *binput=NULL;

    if (!PyArg_ParseTuple(args, "Ol", &binput, &num_results))
        return NULL;

    if (processbounds(binput, min, max, 2) < 0)
        return NULL;

    return RtreeIndex_nearestNeighbors(self->index, num_results, min, max);
}

/* Define Methods */

static PyMethodDef module_methods[] = {
    {"add", (PyCFunction)Rtree_add, METH_VARARGS, "Add an item to an index, specifying an integer id and a bounding box"},
    {"intersection", (PyCFunction)Rtree_intersection, METH_VARARGS, "Return an iterator over integer ids of items that are likely to intersect with the specified bounding box."},
    {"nearest", (PyCFunction)Rtree_nearsetNeighbors, METH_VARARGS, "Return an iterator over integer ids of items that are near the specified bounding box."},
    {"delete", (PyCFunction)Rtree_deleteData, METH_VARARGS, "Deletes a member from the index with a given id and bounding box."},
    {NULL}
};

/* Define Type */

static PyTypeObject RtreeType = {
    PyObject_HEAD_INIT(NULL)
    0,                              /*ob_size*/
    "Rtree",                        /*tp_name*/
    sizeof(Rtree),                  /*tp_basicsize*/
    0,                              /*tp_itemsize*/
    (destructor)Rtree_dealloc,      /*tp_dealloc*/
    0,                              /*tp_print*/
    0,                              /*tp_getattr*/
    0,                              /*tp_setattr*/
    0,                              /*tp_compare*/
    0,                              /*tp_repr*/
    0,                              /*tp_as_number*/
    0,                              /*tp_as_sequence*/
    0,                              /*tp_as_mapping*/
    0,                              /*tp_hash */
    0,                              /*tp_call*/
    0,                              /*tp_str*/
    0,                              /*tp_getattro*/
    0,                              /*tp_setattro*/
    0,                              /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    "R-tree spatial index",       /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    module_methods,             /* tp_methods */
    0,                         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)Rtree_init,       /* tp_init */
    0,                         /* tp_alloc */
    PyType_GenericNew,         /* tp_new */
};

/* Initialization */

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
init_rtree(void) 
{
    PyObject* m;
    if (PyType_Ready(&RtreeType) < 0)
        return;
    m = Py_InitModule3("_rtree", module_methods,
                       "R-tree spatial index.");
    if (m == NULL)
      return;

    Py_INCREF(&RtreeType);
    PyModule_AddObject(m, "Rtree", (PyObject *)&RtreeType);

}

