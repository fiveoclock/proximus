#!/usr/bin/python -u

import sys,string
import proximus_class
import MySQLdb
import os
import socket
import syslog

config = {}
config_filename = "/etc/proximus/proximus.conf"
passthrough_filename = "/etc/proximus/passthrough"

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
         error_msg = "ERROR: please make sure that database settings are correctly set in "+config_filename
         self._log("ERROR: activating passthrough-mode until config is present")
         config['passthrough'] = True

         self._log(error_msg)
         self._writeline(error_msg)

   def read_config(self):
      global config
      try:
         config_file = open(config_filename, 'r')
      except :
         error_msg = "ERROR: config file not found: "+config_filename
         self._log(error_msg)
         self._writeline(error_msg)
         sys.exit(1)

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

      if os.path.isfile(passthrough_filename) :
         self._log("Warning, file: "+passthrough_filename+" exists; Passthrough mode activated")
         config['passthrough'] = True
      else :
         config['passthrough'] = False

      # set defaults
      if not config.has_key("web_path") :
         config['web_path'] = "/proximus/"

      # do some converting
      if config.has_key("debug") :
         config['debug'] = int(config['debug'])
      else :
         config['debug'] = 0
 
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
         db_cursor.execute ("SELECT location_id, redirection_host, smtpserver, admin_email, admincc, subsite_sharing, mail_interval, retrain_key, regex_cut \
                           FROM proxy_settings, global_settings \
                           WHERE \
                                 fqdn_proxy_hostname = %s", ( fqdn_hostname ))
         query = db_cursor.fetchone()
         settings = {'location_id':query[0], 'redirection_host':query[1], 'smtpserver':query[2], 'admin_email':query[3], 'admincc':query[4], 'subsite_sharing':query[5], 'mail_interval':query[6], 'retrain_key':query[7], 'regex_cut':query[8], 'db_cursor':db_cursor, 'debug':config['debug'], 'web_path':config['web_path'] }
      except :
         error_msg = "ERROR: please make sure that a config for this node is stored in the database. Table-name: proxy_settings - Full qualified domain name: "+fqdn_hostname
         self._log("ERROR: activating passthrough-mode until config is present")
         self._log(error_msg)
         self._writeline(error_msg)
         config['passthrough'] = True

      line = self._readline()
      while line:
         if config['passthrough'] == True :
            self._writeline("")
         else:
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
