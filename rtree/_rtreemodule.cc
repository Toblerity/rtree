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

    self->index = RtreeIndex_new(basename, nPageLength, load);
    
//    if (RtreeIndex_isValid(self->index) != 1) {
//        PyErr_Format(PyExc_IOError,
//            "Index layout is invalid"
//            );
//        return -1;
//	}
    return 0;
}

/* Methods */

static PyObject *
Rtree_add(Rtree *self, PyObject *args)
{
    double min[2], max[2];
    long long id;
    int size;
    PyObject *binput=NULL;
    PyObject *bounds;

    if (!PyArg_ParseTuple(args, "LO", &id, &binput))
        return NULL;

    bounds = PySequence_Fast(binput, "Bounds must be a sequence");
    size = (int) PySequence_Fast_GET_SIZE(bounds);
    
    if (size == 2)
    {
        min[0] = max[0] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 0));
        min[1] = max[1] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 1));
        Py_DECREF(bounds);
    }
    else if (size == 4)
    {
        min[0] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 0));
        min[1] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 1));
        max[0] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 2));
        max[1] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 3));
        Py_DECREF(bounds);
    }
    else
    {
        Py_DECREF(bounds);
        PyErr_Format(PyExc_TypeError,
            "Bounds argument must be sequence of length 2 or 4, not %d",
            size);
        return NULL;
    }
 
    /* Check validity of bounds */
    if (min[0] > max[0] || min[1] > max[1])
    {
        PyErr_SetString(PyExc_ValueError,
            "Bounding box is invalid: maxx < miny or maxy < miny"
            );
        return NULL;
    }

    if (RtreeIndex_insertData(self->index, id, min, max) ) {
        Py_INCREF(Py_None);
        return Py_None;        
    } else {
        return NULL;
    }
    

}

static PyObject *
Rtree_deleteData(Rtree *self, PyObject *args)
{
    double min[2], max[2];
    long long id;
    int size;
    PyObject *binput=NULL;
    PyObject *bounds;

    if (!PyArg_ParseTuple(args, "LO", &id, &binput))
        return NULL;

    bounds = PySequence_Fast(binput, "Bounds must be a sequence");
    size = (int) PySequence_Fast_GET_SIZE(bounds);
    
    if (size == 2)
    {
        min[0] = max[0] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 0));
        min[1] = max[1] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 1));
        Py_DECREF(bounds);
    }
    else if (size == 4)
    {
        min[0] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 0));
        min[1] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 1));
        max[0] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 2));
        max[1] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 3));
        Py_DECREF(bounds);
    }
    else
    {
        Py_DECREF(bounds);
        PyErr_Format(PyExc_TypeError,
            "Bounds argument must be sequence of length 2 or 4, not %d",
            size);
        return NULL;
    }

    /* Check validity of bounds */
    if (min[0] > max[0] || min[1] > max[1])
    {
        PyErr_SetString(PyExc_ValueError,
            "Bounding box is invalid: maxx < miny or maxy < miny"
            );
        return NULL;
    }
    
    if (RtreeIndex_deleteData(self->index, id, min, max) ) {
        Py_INCREF(Py_None);
        return Py_None;        
    } else {
        return NULL;
    }    

}

static PyObject *
Rtree_intersection(Rtree *self, PyObject *args)
{
    double min[2], max[2];

    if (!PyArg_ParseTuple(args, "(dddd)", &min[0], &min[1], &max[0], &max[1]))
        return NULL;

    /* Check validity of bounds */
    if (min[0] > max[0] || min[1] > max[1])
    {
        PyErr_SetString(PyExc_ValueError,
            "Bounding box is invalid: maxx < miny or maxy < miny"
            );
        return NULL;
    }

    return RtreeIndex_intersects(self->index, min, max);
}

static PyObject *
Rtree_nearsetNeighbors(Rtree *self, PyObject *args)
{

    double min[2], max[2];
    uint32_t num_results;
    int size;
    
    PyObject *binput=NULL;
    PyObject *bounds;

    if (!PyArg_ParseTuple(args, "Ol", &binput, &num_results))
        return NULL;
        
    bounds = PySequence_Fast(binput, "Bounds must be a sequence");
    size = (int) PySequence_Fast_GET_SIZE(bounds);
    
    if (size == 2)
    {
        min[0] = max[0] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 0));
        min[1] = max[1] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 1));
        Py_DECREF(bounds);
    }
    else if (size == 4)
    {
        min[0] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 0));
        min[1] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 1));
        max[0] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 2));
        max[1] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(bounds, 3));
        Py_DECREF(bounds);
    }
    else
    {
        Py_DECREF(bounds);
        PyErr_Format(PyExc_TypeError,
            "Bounds argument must be sequence of length 2 or 4, not %d",
            size);
        return NULL;
    }

    /* Check validity of bounds */
    if (min[0] > max[0] || min[1] > max[1])
    {
        PyErr_SetString(PyExc_ValueError,
            "Bounding box is invalid: maxx < miny or maxy < miny"
            );
        return NULL;
    }

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

