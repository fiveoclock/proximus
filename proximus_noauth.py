#!/usr/bin/python -u

import sys,string
import MySQLdb

config = {}
config_filename = "/etc/proximus/proximus.conf"

class SquidRedirector:
   def db_connect(self):
      global db_cursor, config

      try:
         conn = MySQLdb.connect (host = config['db_host'],
            user = config['db_user'],
            passwd = config['db_pass'],
            db = config['db_name'])
         db_cursor = conn.cursor ()
      except MySQLdb.Error, e:
         error_msg = "ERROR: please make sure that database settings are correct; current settings: \n \
            User: "+"todo"+"\n \
            Database: "+"todo"+"\n"

         self._log(error_msg)
         self._writeline(error_msg)
         sys.exit(1)

   def read_config(self):
      global config
      config_file = open(config_filename, 'r')
      for line in config_file:
         # Get rid of \n
         line = line.rstrip()
         # Empty?
         if not line:
            continue
         # Comment?
         if line.startswith("#"):
            continue
         (name, value) = line.split("=")
         name = name.strip()
         config[name] = value
      #print config
 
   def __init__(self):
      self.stdout  = sys.stdout

   def openfile(self):
      global f
      f = open("/etc/squid/noauth.txt","w")

   def closefile(self):
      global f
      f.close()

   def writefile(self,s):
      global f
      f.write(s+'\n')

   def _writeline(self,s):
      self.stdout.write(s+'\n')
      self.stdout.flush()

   def run(self):
      self.openfile()
      self.read_config()
      # Get the fully-qualified name.
      self.db_connect()

      # Get relevant proxy settings and catch error if no settings exist in db
      try:
         db_cursor.execute ("SELECT sitename FROM noauth_rules")
         rows = db_cursor.fetchall()
         for row in rows:
            self.writefile("."+row[0])
      except TypeError:
         error_msg = "ERROR: please make sure that a config for this node is stored in the database. \n \
            Table-name: proxy_settings \n \
            Full qualified domain name: "+fqdn_hostname+"\n"

         self._writeline(error_msg)
         sys.exit(1)
      self.closefile()

if __name__ == "__main__":
   sr = SquidRedirector()
   sr.run()
