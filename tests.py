""" Runs doctests
"""
import doctest
from utils.network import SMServerConnection
from service.model.message import Message
from service.repository.repository import CSVRepository, SQLRepository, Repository

if __name__ == '__main__':
    doctest.run_docstring_examples(SMServerConnection.chop_json, globals())
    doctest.run_docstring_examples(Message, globals())
    doctest.run_docstring_examples(CSVRepository, globals())
    doctest.run_docstring_examples(SQLRepository, globals())

    
