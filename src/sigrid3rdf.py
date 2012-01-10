#!/usr/bin/env python

from rdflib import *
from surf import *

ns.register(egg="http://purl.org/nsidc/jcomm/egg#")
ns.register(wmo="http://purl.org/wmo/seaice#")
ns.register(sigrid="http://purl.org/nsidc/jcomm/sigrid#")
ns.register(gml="http://www.opengis.net/def/dataType/OGC-GML/3.0/")
ns.register(geo="http://www.opengis.net/ont/OGC-GeoSPARQL/1.0/")
ns.register(ssiii="http://purl.org/nsidc/ssiii/seaice#")

gmltype = ns.GML["GMLLiteral"]

from osgeo import osr
from osgeo import ogr

import string
import sys

def bindPrefixes(graph):
    graph.bind('egg', URIRef("http://purl.org/nsidc/jcomm/egg#"))
    graph.bind('wmo', URIRef("http://purl.org/wmo/seaice#"))
    graph.bind('sigrid', URIRef("http://purl.org/nsidc/jcomm/sigrid#"))
    graph.bind('gml', URIRef("http://www.opengis.net/def/dataType/OGC-GML/3.0/"))
    graph.bind('geo', URIRef("http://www.opengis.net/ont/OGC-GeoSPARQL/1.0/"))
    graph.bind('ssiii', URIRef("http://purl.org/nsidc/ssiii/seaice#"))

def Usage():
    print('Usage: vec_tr.py infile outfile [layer]')
    print('')
    sys.exit(1)

def convert(infile, layer_name=None):
    ds = ogr.Open( infile, update = 0 )
    store = store = Store(reader="rdflib", writer="rdflib",
                          rdflib_store='IOMemory')
    if layer_name == None:
        for i in range(ds.GetLayerCount()):
            layerToRDF(ds.GetLayer(i),store)
    else:
        layerToRDF(ds.GetLayerByName(layer_name),store)
    ds.Destroy()

    model = store.reader.graph
    bindPrefixes(model)
    return model

def layerToRDF(layer, store = None):
    layerName = layer.GetName()
    if store == None:
        store = Store(reader="rdflib", writer="rdflib",
                      rdflib_store='IOMemory')
    session = Session(store)
    Zone = session.get_class(ns.EGG['Zone'])
    ZoneComponent = session.get_class(ns.SSIII['ZoneComponent'])
    Geometry = session.get_class(ns.GEO['Geometry'])
        
    feature = layer.GetNextFeature()
    while feature is not None:
        geom = feature.GetGeometryRef().ExportToGML()
        zoneURI = '#'+layerName+"/zone/"+str(feature.GetFID())
        geometry = Geometry(zoneURI+"/geometry")
        geometry.geo_asGML = Literal(geom,datatype=gmltype)
        geometry.save()
        zone = Zone(zoneURI)
        zone.geo_hasGeometry = geometry
        zone.sigrid3_hasSigrid3ConcentrationCode = feature.GetFieldAsString("CT")
        zone.egg_hasComponent = []
        for comp in ['A','B','C']:
            if feature.IsFieldSet('C'+comp):
                component = ZoneComponent(zoneURI+"/component/"+comp)
                zone.egg_hasComponent.append(component)
                component.sigrid_hasSigrid3ConcentrationCode = feature.GetFieldAsString('C'+comp)
                if feature.IsFieldSet('S'+comp):
                    component.sigrid_hasSigrid3DevelopmentStageCode = feature.GetFieldAsString('S'+comp)
                if feature.IsFieldSet('F'+comp):
                    component.sigrid_hasSigrid3IceFormCode = feature.GetFieldAsString('F'+comp)
        if feature.IsFieldSet('CN') and feature.GetFieldAsString('CN')[0] != '-':
            component = ZoneComponent(zoneURI+"/component/trace")
            zone.egg_hasComponent.append(component)
            component.sigrid_hasSigrid3ConcentrationCode = "01"
            component.sigrid_hasSigrid3DevelopmentStageCode = feature.GetFieldAsString('CN')
            component.save()
        if feature.IsFieldSet('CD') and feature.GetFieldAsString('CD')[0] != '-':
            component = ZoneComponent(zoneURI+"/component/other")
            zone.egg_hasComponent.append(component)
            component.sigrid_hasSigrid3DevelopmentStageCode = feature.GetFieldAsString('CD')
            component.save()
        if feature.IsFieldSet('CF') and feature.GetFieldAsString('CF')[0] != '-':
            pcomponent = ZoneComponent(zoneURI+"/component/predominant")
            pcomponent.rdf_type = ns.EGG['PredominantForm']
            zone.egg_hasComponent.append(pcomponent)
            pcomponent.sigrid_hasSigrid3DevelopmentStageCode = feature.GetFieldAsString('CD')[:2]
            pcomponent.save()
            scomponent = ZoneComponent(zoneURI+"/component/secondary")
            scomponent.rdf_type = ns.EGG['SecondaryForm']
            zone.egg_hasComponent.append(scomponent)
            scomponent.sigrid_hasSigrid3DevelopmentStageCode = feature.GetFieldAsString('CD')[2:]
            scomponent.save()
        zone.save()
        
        feature.Destroy()
        feature = layer.GetNextFeature()

if __name__ == '__main__':
    infile = None
    outfile = None
    layer_name = None

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]

        if infile is None:
            infile = arg
        elif outfile is None:
            outfile = arg
        elif layer_name is None:
            layer_name = arg
        else:
            Usage()
        i = i + 1

    if outfile is None:
        Usage()
    else:
        model = convert(infile, layer_name)
        model.serialize(outfile,format="turtle")

