#!/usr/bin/env python

from rdflib import *
from surf import *
from lxml import html, etree
import urllib
import tarfile
import tempfile
import datetime

ns.register(egg="http://purl.org/nsidc/jcomm/egg#")
ns.register(wmo="http://purl.org/wmo/seaice#")
ns.register(sigrid="http://purl.org/nsidc/jcomm/sigrid#")
ns.register(gml="http://www.opengis.net/def/dataType/OGC-GML/3.0/")
ns.register(geo="http://www.opengis.net/ont/OGC-GeoSPARQL/1.0/")
ns.register(ssiii="http://purl.org/nsidc/ssiii/seaice#")
ns.register(sio="http://semanticscience.org/resource/")
ns.register(dcat="http://www.w3c.org/ns/dcat#")
ns.register(prov="http://www.w3.org/ns/prov#")
ns.register(esip="http://www.itsc.uah.edu/esip_data#")

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
    graph.bind('sio',URIRef("http://semanticscience.org/resource/"))
    graph.bind('dcat',URIRef("http://www.w3c.org/ns/dcat#"))
    graph.bind('prov',URIRef("http://www.w3.org/ns/prov#"))
    graph.bind('dc',URIRef("http://purl.org/dc/terms/"))
    graph.bind('esip',URIRef("http://www.itsc.uah.edu/esip_data#"))

def Usage():
    print('Usage: vec_tr.py infile outfile [layer]')
    print('')
    sys.exit(1)

def convert(infile, layer_name=None):
    shpFile, xmlFile = downloadAndExtract(infile)
    ds = ogr.Open( shpFile, update = 0 )
    graph = Graph()
    layers = []
    if layer_name == None:
        for i in range(ds.GetLayerCount()):
            layers.append(layerToRDF(ds.GetLayer(i),graph))
    else:
        layers.append(layerToRDF(ds.GetLayerByName(layer_name),graph))
    ds.Destroy()

    bindPrefixes(graph)
    getMetadata(xmlFile, graph, infile, layers)
    return graph

def get_class(graph, classURI):
    def fn(node):
        if type(node) == str:
            node = URIRef(node)
        result = graph.resource(node)
        result.add(ns.RDF['type'],classURI)
        return result
    return fn

def layerToRDF(layer, graph = None):
    layerName = layer.GetName()
    print layerName
    if graph == None:
        graph = Graph()
    Zone = get_class(graph, ns.EGG['Zone'])
    ZoneComponent = get_class(graph, ns.SSIII['ZoneComponent'])
    Geometry = get_class(graph, ns.GEO['Geometry'])
    SeaIceChart = get_class(graph, ns.EGG['SeaIceChart'])

    layerRDF = SeaIceChart('http://purl.org/ssiii/layers/'+layerName)
    layerRDF.add(ns.DCTERMS['title'],Literal(layerName))
    feature = layer.GetNextFeature()

    outSpatialRef = osr.SpatialReference()
    outSpatialRef.SetWellKnownGeogCS( "WGS84" )
    inSpatialRef = layer.GetSpatialRef()

    while feature is not None:
        #geo = feature.GetGeometryRef()
        #geo.Transform(
        geom = feature.GetGeometryRef()
        coordTransform = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)
        geom.Transform(coordTransform)
        gml = geom.ExportToGML()
        
        zoneURI = 'http://purl.org/ssiii/layers/'+layerName+"/zone/"+str(feature.GetFID())
        geometry = Geometry(zoneURI+"/geometry")
        geometry.set(ns.GEO['asGML'], Literal(gml,datatype=gmltype))
        zone = Zone(zoneURI)
        zone.set(ns.SIO['is-member-of'],layerRDF.identifier)
        zone.set(ns.GEO['hasGeometry'], geometry.identifier)
        zone.set(ns.SIGRID['hasSigrid3ConcentrationCode'],
                 Literal(feature.GetFieldAsString("CT")))
        #zone.egg_hasComponent = []
        for comp in ['A','B','C']:
            if feature.IsFieldSet('C'+comp):
                component = ZoneComponent(zoneURI+"/component/"+comp)
                zone.add(ns.EGG['hasComponent'], component.identifier)
                component.set(ns.SIGRID['hasSigrid3ConcentrationCode'],
                              Literal(feature.GetFieldAsString('C'+comp)))
                if feature.IsFieldSet('S'+comp):
                    component.set(ns.SIGRID['hasSigrid3DevelopmentStageCode'],
                                  Literal(feature.GetFieldAsString('S'+comp)))
                if feature.IsFieldSet('F'+comp):
                    component.set(ns.SIGRID['hasSigrid3IceFormCode'],
                                  Literal(feature.GetFieldAsString('F'+comp)))
        if feature.IsFieldSet('CN') and feature.GetFieldAsString('CN')[0] != '' and feature.GetFieldAsString('CN')[0] != '-':
            component = ZoneComponent(zoneURI+"/component/trace")
            zone.add(ns.EGG['hasComponent'],component.identifier)
            component.add(ns.SIGRID['hasSigrid3ConcentrationCode'], Literal("01"))
            component.add(ns.SIGRID['hasSigrid3DevelopmentStageCode'],
                          Literal(feature.GetFieldAsString('CN')))
        if feature.IsFieldSet('CD') and feature.GetFieldAsString('CD')[0] != '' and feature.GetFieldAsString('CD')[0] != '-':
            component = ZoneComponent(zoneURI+"/component/other")
            zone.add(ns.EGG['hasComponent'],component.identifier)
            component.add(ns.SIGRID['hasSigrid3DevelopmentStageCode'],
                          Literal(feature.GetFieldAsString('CD')))
        if feature.IsFieldSet('CF') and feature.GetFieldAsString('CF')[0] != '' and feature.GetFieldAsString('CF')[0] != '-':
            pcomponent = ZoneComponent(zoneURI+"/component/predominant")
            pcomponent.add(ns.RDF['type'],ns.EGG['PredominantForm'])
            zone.add(ns.EGG['hasComponent'],pcomponent.identifier)
            pcomponent.add(ns.SIGRID['hasSigrid3DevelopmentStageCode'],
                           Literal(feature.GetFieldAsString('CF')[:2]))
            scomponent = ZoneComponent(zoneURI+"/component/secondary")
            scomponent.add(ns.RDF['type'],ns.EGG['SecondaryForm'])
            zone.add(ns.EGG['hasComponent'],scomponent.identifier)
            scomponent.add(ns.SIGRID['hasSigrid3DevelopmentStageCode'],
                           Literal(feature.GetFieldAsString('CF')[2:]))
        
        feature.Destroy()
        feature = layer.GetNextFeature()
    return layerRDF

def downloadAndExtract(url):
    d = tempfile.mkdtemp()
    tarFile = d+"/file.tar"
    urllib.urlretrieve(url,tarFile)
    tarball = tarfile.open(tarFile)
    tarball.extractall(d)
    fileNames = tarball.getnames()
    xmlName = [d+"/"+f for f in fileNames if f.endswith(".xml")][0]
    shpName = [d+"/"+f for f in fileNames if f.endswith(".shp")][0]
    return shpName, xmlName

def getMetadata(xmlFile, graph, url, layers):
    dataset = graph.resource(URIRef('http://dx.doi.org/10.7265/N51V5BW9'))
    dataset.set(ns.RDF['type'],ns.DCAT['Dataset'])
    dataset.set(ns.RDF['type'],ns.ESIP['DataSet'])
    dataGranule = graph.resource(URIRef(url))
    dataGranule.set(ns.RDF['type'],ns.ESIP['DataGranule'])
    dataGranule.set(ns.SIO['is-member-of'],dataset.identifier)
    dataGranule.set(ns.ESIP['hasDataSet'],dataset.identifier)
    doc = etree.parse(xmlFile)
    abstract = doc.find('idinfo/descript/abstract').text
    dataGranule.set(ns.DCTERMS['abstract'],Literal(abstract))
    pubDate = doc.find('idinfo/citation/citeinfo/pubdate').text
    pubDate = datetime.datetime.strptime(pubDate,'%Y%m%d').date()
    effectiveDate = doc.find('idinfo/timeperd/timeinfo/sngdate/caldate').text
    effectiveDate = datetime.datetime.strptime(effectiveDate,'%Y%m%d').date()
    dataGranule.set(ns.PROV['generatedAtTime'],Literal(effectiveDate))
    dataGranule.set(ns.PROV['invalidatedAtTime'],Literal(effectiveDate))
    attribution = doc.find('idinfo/citation/citeinfo/origin').text
    attributionURI = 'http://purl.org/ssiii/source/'+attribution.replace(" ","_").replace("(","").replace(")","")
    SeaIceCenter = get_class(graph, ns.EGG['SeaIceCenter'])
    DataCenter = get_class(graph, ns.SIGRID['DataCenter'])
    Organization = get_class(graph, ns.PROV['Organization'])
    source = SeaIceCenter(attributionURI)
    source.set(ns.RDFS['label'],Literal(attribution))
    publisher = DataCenter("http://nsidc.org")
    source.set(ns.RDFS['label'],Literal("National Snow and Ice Data Center (NSIDC)"))
    dataGranule.set(ns.PROV['wasAttributedTo'],source.identifier)
    dataGranule.set(ns.PROV['wasAttributedTo'],publisher.identifier)
    region = URIRef('http://purl.org/nsidc/cis/Sea-Ice-Chart-Regions#'
                    +url.split('/')[7].replace("_",""))
    dataGranule.set(ns.SIO['is-model-of'],region)
    for layer in layers:
        layer.add(ns.PROV['wasDerivedFrom'],dataGranule.identifier)
        layer.add(ns.SIO['is-modeled-by'],dataGranule.identifier)
        layer.add(ns.PROV['alternateOf'],dataGranule.identifier)
        dataGranule.add(ns.DCTERMS['title'],layer.value(ns.DCTERMS['title']))
        layer.set(ns.PROV['wasAttributedTo'],source.identifier)
        layer.set(ns.PROV['wasAttributedTo'],publisher.identifier)
        layer.set(ns.SIO['is-model-of'],region)
        layer.set(ns.PROV['generatedAtTime'],Literal(effectiveDate))
        layer.set(ns.PROV['invalidatedAtTime'],Literal(effectiveDate))


    #for accessionElement in doc.findall('//experiment/accession'):
    #    accession = accessionElement.text.strip()
    #    obj = HarvestObject(guid=accession, job=harvest_job, content=accession)
    #    print "ArrayExpress accession: "+accession
    #    obj.save()


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

