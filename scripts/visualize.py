#!/usr/bin/env python

import sys

from liblas import file
from osgeo import ogr

from rtree import index


def quick_create_layer_def(lyr, field_list):
    # Each field is a tuple of (name, type, width, precision)
    # Any of type, width and precision can be skipped.  Default type is string.

    for field in field_list:
        name = field[0]
        if len(field) > 1:
            type = field[1]
        else:
            type = ogr.OFTString

        field_defn = ogr.FieldDefn(name, type)

        if len(field) > 2:
            field_defn.SetWidth(int(field[2]))

        if len(field) > 3:
            field_defn.SetPrecision(int(field[3]))

        lyr.CreateField(field_defn)

        field_defn.Destroy()


shape_drv = ogr.GetDriverByName("ESRI Shapefile")

shapefile_name = sys.argv[1].split(".")[0]
shape_ds = shape_drv.CreateDataSource(shapefile_name)
leaf_block_lyr = shape_ds.CreateLayer("leaf", geom_type=ogr.wkbPolygon)
point_block_lyr = shape_ds.CreateLayer("point", geom_type=ogr.wkbPolygon)
point_lyr = shape_ds.CreateLayer("points", geom_type=ogr.wkbPoint)

quick_create_layer_def(
    leaf_block_lyr, [("BLK_ID", ogr.OFTInteger), ("COUNT", ogr.OFTInteger)]
)

quick_create_layer_def(
    point_block_lyr, [("BLK_ID", ogr.OFTInteger), ("COUNT", ogr.OFTInteger)]
)

quick_create_layer_def(point_lyr, [("ID", ogr.OFTInteger), ("BLK_ID", ogr.OFTInteger)])

p = index.Property()
p.filename = sys.argv[1]
p.overwrite = False

p.storage = index.RT_Disk
idx = index.Index(sys.argv[1])

leaves = idx.leaves()
# leaves[0] == (0L, [2L, 92L, 51L, 55L, 26L], [-132.41727847799999,
# -96.717721818399994, -132.41727847799999, -96.717721818399994])

f = file.File(sys.argv[1])


def area(minx, miny, maxx, maxy):
    width = abs(maxx - minx)
    height = abs(maxy - miny)

    return width * height


def get_bounds(leaf_ids, lasfile, block_id):
    # read the first point and set the bounds to that

    p = lasfile.read(leaf_ids[0])
    minx, maxx = p.x, p.x
    miny, maxy = p.y, p.y

    print(len(leaf_ids))
    print(leaf_ids[0:10])

    for p_id in leaf_ids:
        p = lasfile.read(p_id)
        minx = min(minx, p.x)
        maxx = max(maxx, p.x)
        miny = min(miny, p.y)
        maxy = max(maxy, p.y)
        feature = ogr.Feature(feature_def=point_lyr.GetLayerDefn())
        g = ogr.CreateGeometryFromWkt(f"POINT ({p.x:.8f} {p.y:.8f})")
        feature.SetGeometry(g)
        feature.SetField("ID", p_id)
        feature.SetField("BLK_ID", block_id)
        result = point_lyr.CreateFeature(feature)
        del result

    return (minx, miny, maxx, maxy)


def make_poly(minx, miny, maxx, maxy):
    wkt = (
        f"POLYGON (({minx:.8f} {miny:.8f}, {maxx:.8f} {miny:.8f}, {maxx:.8f} "
        f"{maxy:.8f}, {minx:.8f} {maxy:.8f}, {minx:.8f} {miny:.8f}))"
    )
    shp = ogr.CreateGeometryFromWkt(wkt)
    return shp


def make_feature(lyr, geom, id, count):
    feature = ogr.Feature(feature_def=lyr.GetLayerDefn())
    feature.SetGeometry(geom)
    feature.SetField("BLK_ID", id)
    feature.SetField("COUNT", count)
    result = lyr.CreateFeature(feature)
    del result


t = 0
for leaf in leaves:
    id = leaf[0]
    ids = leaf[1]
    count = len(ids)
    # import pdb;pdb.set_trace()

    if len(leaf[2]) == 4:
        minx, miny, maxx, maxy = leaf[2]
    else:
        minx, miny, maxx, maxy, minz, maxz = leaf[2]

    if id == 186:
        print(leaf[2])

    print(leaf[2])
    leaf = make_poly(minx, miny, maxx, maxy)
    print("leaf: " + str([minx, miny, maxx, maxy]))

    pminx, pminy, pmaxx, pmaxy = get_bounds(ids, f, id)
    point = make_poly(pminx, pminy, pmaxx, pmaxy)

    print("point: " + str([pminx, pminy, pmaxx, pmaxy]))
    print("point bounds: " + str([point.GetArea(), area(pminx, pminy, pmaxx, pmaxy)]))
    print("leaf bounds: " + str([leaf.GetArea(), area(minx, miny, maxx, maxy)]))
    print("leaf - point: " + str([abs(point.GetArea() - leaf.GetArea())]))
    print([minx, miny, maxx, maxy])
    #  if shp2.GetArea() != shp.GetArea():
    #      import pdb;pdb.set_trace()
    # sys.exit(1)

    make_feature(leaf_block_lyr, leaf, id, count)
    make_feature(point_block_lyr, point, id, count)

    t += 1
    # if t ==2:
    #     break

leaf_block_lyr.SyncToDisk()
point_lyr.SyncToDisk()

shape_ds.Destroy()
