/*
# =============================================================================
# Rtree spatial index. Copyright (C) 2006 Ancient World Mapping Center
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
    char* filename = NULL;
    unsigned long nPageLength = 0;
    FILE *file = NULL;

    if (!PyArg_ParseTuple(args, "|si", &filename, (unsigned long)&nPageLength))
        return -1;
   
    // Check that there is a file beyond the name
    if (filename)
    {
        file = fopen(filename, "wb");
        if (!file)
        {
            PyErr_Format(PyExc_IOError,
                "Unable to open file '%s' for index storage", filename);
            return -1;
        }
        fclose(file);
    }

    self->index = RtreeIndex_new(filename, nPageLength);
    
    return 0;
}

/* Methods */

static PyObject *
Rtree_add(Rtree *self, PyObject *args)
{
    double min[2], max[2];
    long id;
    int size;
    PyObject *bounds=NULL;

    if (!PyArg_ParseTuple(args, "lO", &id, &bounds))
        return NULL;

    /* Check length of the bounds argument */
    if (!PySequence_Check(bounds))
    {
        PyErr_SetString(PyExc_TypeError, "Bounds must be a sequence");
        return NULL;
    }

    size = (int) PySequence_Size(bounds);
    if (size == 2)
    {
        min[0] = max[0] = PyFloat_AsDouble(PySequence_ITEM(bounds, 0));
        min[1] = max[1] = PyFloat_AsDouble(PySequence_ITEM(bounds, 1));
    }
    else if (size == 4)
    {
        min[0] = PyFloat_AsDouble(PySequence_ITEM(bounds, 0));
        min[1] = PyFloat_AsDouble(PySequence_ITEM(bounds, 1));
        max[0] = PyFloat_AsDouble(PySequence_ITEM(bounds, 2));
        max[1] = PyFloat_AsDouble(PySequence_ITEM(bounds, 3));
    }
    else
    {
        PyErr_Format(PyExc_TypeError,
            "Bounds argument must be sequence of length 2 or 4, not %d",
            size);
        return NULL;
    }
  
    RtreeIndex_insertData(self->index, id, min, max);
    
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
Rtree_intersection(Rtree *self, PyObject *args)
{
    double min[2], max[2];

    if (!PyArg_ParseTuple(args, "(dddd)", &min[0], &min[1], &max[0], &max[1]))
        return NULL;
    
    return RtreeIndex_intersects(self->index, min, max);
}

/* Define Methods */

static PyMethodDef module_methods[] = {
    {"add", (PyCFunction)Rtree_add, METH_VARARGS, "Add an item to an index, specifying an integer id and a bounding box"},
    {"intersection", (PyCFunction)Rtree_intersection, METH_VARARGS, "Return an iterator over integer ids of items that are likely to intersect with the specified bounding box."},
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

