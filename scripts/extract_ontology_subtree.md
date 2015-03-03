Notes on extracting ontology subtree
====================================

- DBpedia endpoint - http://dbpedia.org/sparql
```
    select ?location where {
      ?location a d0:Location
    }
    order by ?location  #-- need an order for offset to work
    limit 1000          #-- how many to get each time
    offset 3000         #-- where to start in the list
```
- ontology class - http://mappings.dbpedia.org/server/ontology/classes/


Interesting queries (see also ``sparql_example.py``:
* Traversing hierarchy http://stackoverflow.com/questions/5364851/getting-dbpedia-infobox-categories
* construct query and retrieving hierarchy for grounded item (Nokia) in http://stackoverflow.com/questions/10855450/extracting-hierarchy-for-dbpedia-entity-using-sparql
* Object vs property http://stackoverflow.com/questions/18175006/sparql-query-to-retrieve-all-dbpedia-literary-grenre
