#!/usr/bin/python -u
""" redirector.py -- a script for squid redirection.
    (a long-running process that uses unbuffered io; hence the -u flag in python)"""

import sys,string
import redirector_class
import MySQLdb
import os
import socket

class SquidRedirector:
   def db_connect(self):
      self._log("started")
      conn = MySQLdb.connect (host = "mysql-lga.mm-karton.com",
         user = "proximusadmin",
         passwd = "proximus",
         db = "db_proximusgate")
      global db_cursor
      db_cursor = conn.cursor ()

   def __init__(self):
      self.stdin   = sys.stdin
      self.stdout  = sys.stdout

   def _log(self,s):
      f = open("/var/log/squid/redirector.log","a")
      f.write(s+'\n')
      f.close()
 
   def _readline(self):
      "Returns one unbuffered line from squid."
      return self.stdin.readline()[:-1]

   def _writeline(self,s):
      self.stdout.write(s+'\n')
      self.stdout.flush()

   def run(self):
      self._log("started")
      #print os.uname()
      #print os.system('hostname')
      # Get the fully-qualified name.
      hostname = socket.gethostname()
      fqdn_hostname = socket.getfqdn(hostname)
      #print "Fully-qualified name:", socket.getfqdn(hostname)
      self.db_connect()

      # Get relevant proxy settings
      db_cursor.execute ("SELECT location_id, redirection_host \
                           FROM proxy_settings \
                           WHERE \
                                 fqdn_proxy_hostname = %s \
         ", ( fqdn_hostname ))

      settings = db_cursor.fetchone()
      location_id = settings[0]
      redirection_host = settings[1]

      line = self._readline()
      while line:
         response = redirector_class.check_request(db_cursor, redirection_host, location_id, line)
         self._log("request: " + line)
         self._log("response: " + response + "\n")
         self._writeline(response)
         line = self._readline()

if __name__ == "__main__":
   sr = SquidRedirector()
   sr.run()
