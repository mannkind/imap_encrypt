# From http://docs.python.org/2/library/email.message.html

from StringIO import StringIO
from email.generator import Generator

class Util:
    @staticmethod
    def flattenMessage(mail):
        fp = StringIO()
        g = Generator(fp,mangle_from_=False, maxheaderlen=60)
        g.flatten(mail)
        return fp.getvalue()
