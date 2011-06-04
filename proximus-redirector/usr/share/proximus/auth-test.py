#!/usr/bin/python -u

import sys,string
import os
import socket
import syslog

config = {}
config_filename = "/etc/proximus/proximus.conf"
passthrough_filename = "/etc/proximus/passthrough"

class Proximus:
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
      config['debug'] = 1;
      # Get the fully-qualified name.
      self._log("started")

      line = self._readline()
      while line:
         if config['debug'] > 0 :
            self._log("Req  "+": " + line)
         self._writeline("OK")
         line = self._readline()

if __name__ == "__main__":
   sr = Proximus()
   sr.run()
