#!/usr/bin/python -u

import sys,string
import proximus_class
import MySQLdb
import os
import socket
import syslog

config = {}
config_filename = "/etc/proximus/proximus.conf"

class Proximus:
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
      config_file.close()
 
   def __init__(self):
      syslog.openlog('proximus',syslog.LOG_PID,syslog.LOG_LOCAL5)
      self.stdin   = sys.stdin
      self.stdout  = sys.stdout

   def _log(self,s):
      syslog.syslog(syslog.LOG_DEBUG,s)
 
   def _readline(self):
      "Returns one unbuffered line from squid."
      return self.stdin.readline()[:-1]

   def _writeline(self,s):
      self.stdout.write(s+'\n')
      self.stdout.flush()

   def run(self):
      self.read_config()
      # Get the fully-qualified name.
      hostname = socket.gethostname()
      fqdn_hostname = socket.getfqdn(hostname)
      self.db_connect()
      self._log("started")
      req_id = 0

      # Get relevant proxy settings and catch error if no settings exist in db
      try:
         db_cursor.execute ("SELECT location_id, redirection_host, smtpserver, admin_email, admincc, subsite_sharing, mail_interval, retrain_key \
                           FROM proxy_settings, global_settings \
                           WHERE \
                                 fqdn_proxy_hostname = %s", ( fqdn_hostname ))
         query = db_cursor.fetchone()
         settings = {'location_id':query[0], 'redirection_host':query[1], 'smtpserver':query[2], 'admin_email':query[3], 'admincc':query[4], 'subsite_sharing':query[5], 'mail_interval':query[6], 'retrain_key':query[7], 'db_cursor':db_cursor }
      except TypeError:
         error_msg = "ERROR: please make sure that a config for this node is stored in the database. \n \
            Table-name: proxy_settings \n \
            Full qualified domain name: "+fqdn_hostname+"\n"

         self._log(error_msg)
         self._writeline(error_msg)
         sys.exit(1)

      line = self._readline()
      while line:
         req_str = str(req_id)
         req_id = req_id+1
         self._log("Req  "+req_str+": " + line)
         response = proximus_class.check_request(settings, line)
         self._log("Resp "+req_str+": " + response)
         self._writeline(response)
         line = self._readline()

if __name__ == "__main__":
   sr = Proximus()
   sr.run()
