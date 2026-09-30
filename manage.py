#!/usr/bin/env python
"""Permite executar os comandos Django a partir da raiz do repositório."""
import runpy
import sys
from pathlib import Path


if __name__ == '__main__':
    pasta_app = Path(__file__).resolve().parent / 'aumiau'
    sys.path.insert(0, str(pasta_app))
    runpy.run_path(str(pasta_app / 'manage.py'), run_name='__main__')
