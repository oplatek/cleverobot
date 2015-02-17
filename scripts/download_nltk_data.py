#!/usr/bin/env python
# encoding: utf-8
import os
import logging


logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
logger.addHandler(ch)
logger.setLevel(logging.INFO)


def download_nltkdata(path):
    import nltk
    try:
        os.mkdir(path)
    except OSError:
        pass
    nltk.download("maxent_treebank_pos_tagger", path)
    logger.info('Downloading of nltk data for POS tagger finished')


if __name__ == '__main__':
    download_nltkdata(os.environ['NLTK_DATA'])
