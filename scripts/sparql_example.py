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
    ,
    '''
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    PREFIX ontology: <http://dbpedia.org/ontology/> 
    select distinct ?bookUri  
    where { ?bookUri  rdf:type ontology:Country . } 
    ''' ,
    '''
    SELECT ?prop ?title WHERE {
         ?country ?prop [].
         ?country a <http://dbpedia.org/ontology/Country>.
         ?prop rdf:type rdf:Property.
         ?prop rdfs:label ?title
    } ORDER BY DESC(COUNT(DISTINCT ?country))
    ''' ,
    '''
    SELECT DISTINCT ?class ?label WHERE {
         ?class rdfs:subClassOf owl:Thing.
         ?class rdfs:label ?label. 
         FILTER(lang(?label) = "en")
    }
    ''' ,
    '''
    CONSTRUCT WHERE {
      dbpedia:Nokia a ?c1 ; a ?c2 .
      ?c1 rdfs:subClassOf ?c2 .
    }
    ''',
    '''
    SELECT * WHERE {
          dbpedia:Nokia a ?c1 ; a ?c2 .
            ?c1 rdfs:subClassOf ?c2 .
    }
    ''',
    '''
    SELECT * WHERE {
          dbpedia:California a ?c1 ; a ?c2 .
            ?c1 rdfs:subClassOf ?c2 .
    }
    '''
    ]

queries = [queries[-1]]
for q in queries:
    print('%s\n' % q)

    sparql.setQuery(q)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    for result in results["results"]["bindings"]:
        print(result)
