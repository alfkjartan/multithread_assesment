import sys
import abc
from service.model.message import Message


class Repository(abc.ABC):

    @abc.abstractmethod
    def append(self, message: Message):
        pass

    def screen_repository(where=sys.stdout):
        return ScreenRepository(where)

    def csv_repository(filename : str):
        return CSVRepository(filename)

class ScreenRepository(Repository):

    def __init__(self, where=sys.stdout):
        self.file = where


    def append(self, message : Message):
        print("\t".join(map(str, message.__dict__.values())), file=self.file)


class CSVRepository(Repository):

    def __init__(self, filename : str):
        self.filename = filename

        self.header_written = False
        
    def append(self, message : Message):
        if not self.header_written:
            with open(self.filename, 'w') as f:
                f.write(", ".join(map(str, message.__dict__.keys())))
                f.write("\n")
            self.header_written = True
        with open(self.filename, 'a') as f:
            f.write(", ".join(map(str, message.__dict__.values())))
            f.write("\n")
