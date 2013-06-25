"""
IMAP Encrypt

Utilizing IMAP IDLE monitor a given mailbox and encrypt all unencrypted email.
Special thanks to the authors of imaplib2.py and gpg.py (modified)
"""
import imaplib2, os, sys, email, gpg, yaml
from util import Util
from threading import *

# This is the threading object that does all the waiting on the event
class Idler:
    def __init__(self, conn, config):
        self.thread = Thread(target = self.idle)
        self.M = conn
        self.config = config
        self.knownMail = []
        self.event = Event()
 
    def start(self):
        self.thread.start()
 
    def stop(self):
        # This is a neat trick to make thread end. Took me a 
        # while to figure that one out!
        self.event.set()
 
    def join(self):
        self.thread.join()
 
    def idle(self):
        # Starting an unending loop here
        while True:
            # This is part of the trick to make the loop stop when the stop() command is given
            if self.event.isSet():
                return

            self.needsync = False

            # A callback method that gets called when a new email arrives. 
            def callback(args):
                if not self.event.isSet():
                    self.needsync = True
                    self.event.set()

            # Do the actual idle call.
            self.M.idle(callback=callback)

            # This waits until the event is set. 
            self.event.wait()

            # Escape the loop without stopping.
            if self.needsync:
                self.event.clear()
                self.dosync()
 
    # The method that gets called when a new email arrives. 
    def dosync(self):
        typ, data = self.M.uid('search', None, self.config['monitor'])
	for uid in data[0].split():
	    if not uid in self.knownMail:
	        self.encrypt(uid)
		self.knownMail.append(uid)

    # Encrypt the email
    def encrypt(self, uid):
        typ, data = self.M.uid('fetch', uid,'(RFC822)')
    
        if data == None:
            return

        mail = email.message_from_string(data[0][1])
        if mail.get_content_type() == 'multipart/encrypted':
            return

        # Parse the original date
        headerFields = email.parser.HeaderParser().parsestr(data[0][1])
        if headerFields == None: 
            date = ''
        else:
            pz = email.utils.parsedate_tz(headerFields['Date'])
            stamp = email.utils.mktime_tz(pz)
            date = imaplib2.Time2Internaldate(stamp)

        # Encrypt the message
        encrypted_mail = gpg.GPGEncryption().encryptPGP(mail, self.config['pubkey'])
    
        # Delete the plaintext message
        if 'trash' in self.config and self.config['trash'] != '':
            self.M.uid('copy', uid, self.config['trash'])
    
        self.M.uid('store', uid, '+FLAGS', '\\Deleted')
        self.M.expunge()
        
        # Append the encrypted message
        move_to = self.config['mailbox'] if 'move_to' not in self.config else self.config['move_to']
        read = '' if self.config['monitor'] == 'UNSEEN' else '\\seen'
        self.M.append(move_to, read, date, Util.flattenMessage(encrypted_mail))

 
try:
    config = yaml.load(open(sys.argv[1], 'r'))
    
    # Login
    M = imaplib2.IMAP4_SSL(config['server'])
    M.login(config['username'], config['password'])
    M.select(config['mailbox'])
    
    # Start the Idler thread
    idler = Idler(M, config)
    idler.start()
    
    q = ''
    while not q == 'q':
      q = raw_input('Type \'q\' followed by [ENTER] to quit: ')

finally:

    # Clean up.
    idler.stop()
    idler.join()
    M.close()
    
    # This is important!
    M.logout()
