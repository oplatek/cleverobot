#!/usr/bin/env python
# encoding: utf-8

from SPARQLWrapper import SPARQLWrapper, JSON
 
sparql = SPARQLWrapper("http://dbpedia.org/sparql")
queries = [
    '''
    SELECT * WHERE {
        ?player a <http://dbpedia.org/ontology/SoccerPlayer> .
        ?player <http://dbpedia.org/ontology/birthDate> ?birthDate .
        ?player <http://dbpedia.org/ontology/Person/height> ?height .
        ?player <http://dbpedia.org/ontology/position> ?position .
    }
    ''',
    '''
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label
    WHERE { <http://dbpedia.org/resource/Asturias> rdfs:label ?label }
    '''
    ]

for q in queries:
    print('%s\n' % q)

    sparql.setQuery(q)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    for result in results["results"]["bindings"]:
        print(result)
