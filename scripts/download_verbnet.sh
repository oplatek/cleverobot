#!/bin/sh

file=verbnet-3.2.tar.gz
link=http://verbs.colorado.edu/verb-index/vn/${file}

if [ ! -f $file ] ; then
  wget $link -O $file
fi

tar xf $file
