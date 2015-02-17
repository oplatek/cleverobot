#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals
from SPARQLWrapper import SPARQLWrapper, JSON
import argparse

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
    WHERE { ?bookUri  rdf:type ontology:Country . }
    ''',
    '''
    SELECT ?prop ?title WHERE {
        ?country ?prop [].
        ?country a <http://dbpedia.org/ontology/Country>.
        ?prop rdf:type rdf:Property.
        ?prop rdfs:label ?title
    } ORDER BY DESC(COUNT(DISTINCT ?country))
    ''',
    '''
    SELECT DISTINCT ?country ?title ?comment
    WHERE {
        ?country a <http://dbpedia.org/ontology/Country>.
        ?country rdfs:label ?title.
        ?country rdfs:comment ?comment.
        FILTER(lang(?title) = "en")
        FILTER(lang(?comment) = "en")
    }
    ORDER BY DESC (?country)
    LIMIT 10
    ''',
    '''
    SELECT ?country
    WHERE { ?country a <http://dbpedia.org/ontology/Country>. }
    ''',
    '''
    SELECT DISTINCT ?class ?label WHERE {
         ?class rdfs:subClassOf owl:Thing.
         ?class rdfs:label ?label.
         FILTER(lang(?label) = "en")
    }
    ''',
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

if __name__ == '__main__':
    parser = argparse.ArgumentParser('Run example queries ')
    parser.add_argument('-u', '--url', default="http://dbpedia.org/sparql")
    parser.add_argument('-n', '--number', type=int, default=None, action='store', help='Select specific query')
    args = parser.parse_args()
    sparql = SPARQLWrapper(args.url)
    if args.number is not None:
        queries=[queries[args.number]]

    for q in queries:
        print('%s\n' % q)

        sparql.setQuery(q)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()

        for result in results["results"]["bindings"]:
            print(result)
