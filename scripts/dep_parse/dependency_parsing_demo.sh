#!/bin/sh
set -e

file=maltparser-1.8.tar.gz
link=http://maltparser.org/dist/$file

if [ ! -f $file ] ; then
  wget $link -O $file
fi

tar xf $file

model=engmalt.linear-1.7.mco
model_link=http://maltparser.org/mco/english_parser/$model
if [ ! -f $model ] ; then
  wget $model_link -O $model
fi

java -Xmx1024m -jar maltparser-1.8/maltparser-1.8.jar -w '.' -c engmalt.linear-1.7 -i infile_test.conll -o outfile.conll -m parse
