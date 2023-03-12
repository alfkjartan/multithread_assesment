""" Runs doctests
"""
import doctest
from utils.network import SMServerConnection

if __name__ == '__main__':
    doctest.run_docstring_examples(SMServerConnection.chop_json, globals())

    
