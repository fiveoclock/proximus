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
      global db_cursor

      try:
         conn = MySQLdb.connect (host = "mysql-lga.mm-karton.com",
            user = "proximusadmin",
            passwd = "proximus",
            db = "db_proximusgate")
         db_cursor = conn.cursor ()
      except MySQLdb.Error, e:
         error_msg = "ERROR: please make sure that database settings are correct; current settings: \n \
            User: "+"todo"+"\n \
            Database: "+"todo"+"\n"

         self._log(error_msg)
         self._writeline(error_msg)
         sys.exit(1)


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
      self.db_connect()

      # Get relevant proxy settings and catch error if no settings exist in db
      try:
         db_cursor.execute ("SELECT location_id, redirection_host, smtpserver, admin_email, admincc, subsite_sharing, mail_interval \
                           FROM proxy_settings, global_settings \
                           WHERE \
                                 fqdn_proxy_hostname = %s", ( fqdn_hostname ))
         query = db_cursor.fetchone()
         settings = {'location_id':query[0], 'redirection_host':query[1], 'smtpserver':query[2], 'admin_email':query[3], 'admincc':query[4], 'subsite_sharing':query[5], 'mail_interval':query[6], 'db_cursor':db_cursor }
      except TypeError:
         error_msg = "ERROR: please make sure that a config for this node is stored in the database. \n \
            Table-name: proxy_settings \n \
            Full qualified domain name: "+fqdn_hostname+"\n"

         self._log(error_msg)
         self._writeline(error_msg)
         sys.exit(1)

      line = self._readline()
      while line:
         response = redirector_class.check_request(settings, line)
         self._log("request: " + line)
         self._log("response: " + response + "\n")
         self._writeline(response)
         line = self._readline()

if __name__ == "__main__":
   sr = SquidRedirector()
   sr.run()
