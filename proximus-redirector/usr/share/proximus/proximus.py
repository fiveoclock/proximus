#!/usr/bin/python -u

import sys,string
import time
import MySQLdb
import MySQLdb.cursors
import os, signal
import socket
import struct
import syslog
import pprint # for debugging

import re
import base64
import smtplib
from email.MIMEText import MIMEText
from urlparse import urlparse

from apscheduler.scheduler import Scheduler
import threading
import logging  # apscheduler needs this when it has an exception
import hashlib
import commands

import ConfigParser

class Proximus:
   config_filename = "/etc/proximus/proximus.conf"
   passthrough_filename = "/etc/proximus/passthrough"
   cache = {}
   db_pool = [None]*2

   sched = Scheduler()
   job_bind = None

   def __init__(self, options):
      global settings

      # configure syslog
      syslog.openlog('proximus',syslog.LOG_PID,syslog.LOG_LOCAL5)
      self.stdin   = sys.stdin
      self.stdout  = sys.stdout

      logging.basicConfig()

      # set options
      settings = options
      # read config file and connect to the database
      self.read_configfile()
      # combine / overwrite settings with passed options again... - kind of stupid..
      settings = dict(settings, **options)

      if self.db_connect() :
         self.get_settings_from_db()
         # make sure the right time is used
         self.set_timezone()
      else :
         error_msg = "ERROR: please make sure that database settings are correctly set in " + \
            self.config_filename + "; activating passthrough-mode until database is available"
         settings['passthrough'] = True
         self.log(error_msg)
         self._writeline(error_msg)

      # debugging....
      self.debug("Settings: " + pprint.pformat(settings, 3), 3 )


   def read_configfile(self):
      global settings

      cp = ConfigParser.RawConfigParser()
      cp.read( self.config_filename )

      try:
         config = dict(cp.items('main'))
      except :
         error_msg = "ERROR: config file not found: " + self.config_filename
         self.log(error_msg)
         self._writeline(error_msg)
         sys.exit(1)

      if os.path.isfile(self.passthrough_filename) :
         self.log("Warning, file: "+self.passthrough_filename+" exists; Passthrough mode activated")
         config['passthrough'] = True
      else :
         config['passthrough'] = False

      # sanity checks
      # debug
      if config.has_key("debug") :
         config['debug'] = int(config['debug'])
      else :
         config['debug'] = 1

      # port
      if config.has_key("port") :
         config['port'] = int(config['port'])
      else :
         config['port'] = 65432

      # update_interval
      if config.has_key("list_update_interval") :
         config['list_update_interval'] = int(config['list_update_interval'])
      else :
         config['list_update_interval'] = 60

      # update_interval
      if config.has_key("cache_time") :
         config['cache_time'] = int(config['cache_time'])
      else :
         config['cache_time'] = 60

      settings = config
      #pprint.pprint(settings)  ## debug


   # Get settings from db and catch error if no settings are stored
   def get_settings_from_db(self):
      global settings

      # Get the fully-qualified name.
      hostname = socket.gethostname()
      fqdn_hostname = socket.getfqdn(hostname)

      try:
         # Get proxy specific settings
         cursor = self.db_query("SELECT location_id, redirection_url, smtpserver, admin_email, admincc, timezone \
                           FROM proxy_settings \
                           WHERE fqdn_proxy_hostname = %s", ( fqdn_hostname ))
         query = cursor.fetchone()

         # combine with settings with existing ones
         settings = dict(settings, **query)

         # Get global settings
         cursor = self.db_query ("SELECT name, value FROM global_settings")
         query = cursor.fetchall()
         for row in query:
            settings[row['name']] = row['value']

         # set redirection_host
         r = self.parse_url( settings['redirection_url'] )
         settings['redirection_host'] = r['sitename']

      # catch error if no settings are stored;
      # and activate passthrough mode
      except Exception, e :
         s.debug("get_settings_from_db - exception: " + str(e), 1)
         error_msg = "ERROR: please make sure that a config for this node is stored in the database. Table-name: proxy_settings - Full qualified domain name: " + fqdn_hostname + "; "
         self.log("ERROR: activating passthrough-mode until config is present")
         self.log(error_msg)
         self._writeline(error_msg)
         settings['passthrough'] = True


   # set timezone according to settings
   def set_timezone(self):
      if "timezone" in settings :
         if ( settings['timezone'] != '' ) :
            self.db_query("SET time_zone = %s", ( settings['timezone']) )
            cursor = self.db_query ("SELECT CURTIME() AS now")
            time = cursor.fetchone()
            self.debug("Timezone was set to: " + settings['timezone'] + "; current time is now: " + str(time['now']), 0)
            return True
      else:
         cursor = self.db_query ("SELECT CURTIME() AS now")
         time = cursor.fetchone()
         self.debug("Current time is now: " + str(time['now']), 0)
         return False


   def run(self):
      # start list updating thread if configured
      if settings['reload_method'] in ["signal", "command"] :
         self.start_list_update_thread()

      self.log("redirector started")
      self.req_id = 0
      line = self._readline()
      while line:
         if settings['passthrough'] == True :
            self._writeline("")
         else:
            self.req_id += 1
            self.debug("Req  " + str(self.req_id) + ": " + line, 2)
            response = self.check_request(line)
            self._writeline(response)
            self.debug("Resp " + str(self.req_id) + ": " + response, 2)
         line = self._readline()


   def run_auth(self):
      self.log("authenticator started")
      self.req_id = 0
      line = self._readline()
      while True:
         if settings['passthrough'] == True :
            self._writeline("")
         else:
            self.req_id += 1
            self._writeline( self.check_auth(line) )
         line = self._readline()


   def check_config(self):
      settings['db_pass'] = "***"
      pprint.pprint(settings)
      self._writeline("")
      self.log("If you didn't see any error messages above the config should be ok")
 
   ################
   ################
   ## Basic functions
   ########
   ########

   def _readline(self):
      "Returns one unbuffered line from squid."
      return self.stdin.readline()[:-1]

   def _writeline(self,s):
      self.stdout.write(s+'\n')
      self.stdout.flush()

   def log(s, str):
      syslog.syslog(syslog.LOG_DEBUG,str)
      if settings['interactive']:
         s._writeline(str)

   def debug(s, str, level=1):
      if settings['debug'] >= level:
         s.log(str)

   def open_file(s, filename, option):
      try:
         f = open(filename, option)
         return f
      except :
         error_msg = "ERROR: cannot open file: " + filename
         s.log(error_msg)

   def read_file(s, filename):
      f = s.open_file(filename, 'r')
      if f != None :
         data = f.read()
         f.close()
         return data

   def write_file(s, filename, data):
      f = s.open_file(filename, 'w')
      if f != None :
         f.write( data )
         f.close()
         return True
      else:
         return False


   ################
   ################
   ## Database functions
   ########
   ########

   def get_db_index(self):
      if threading.current_thread().name == "MainThread" :
         return 0
      else :
         return 1

   def get_db(self):
      return self.db_pool[ self.get_db_index() ]

   def db_connect(self):
      try:
         conn = MySQLdb.connect (host = settings['db_host'],
            user = settings['db_user'],
            passwd = settings['db_pass'],
            db = settings['db_name'], cursorclass=MySQLdb.cursors.DictCursor)

         # store the connection in the pool
         self.db_pool[ self.get_db_index() ] = conn

         # make sure the right time is used - when reconnecting
         self.set_timezone()
         self.debug("db_connect - current connections: " + str( self.db_pool ), 1)
         return True
      except MySQLdb.Error, e:
         self.debug("db_connect - exception: " + str(e), 1)
         self.db_pool[ self.get_db_index() ] = None
         self.debug("db_connect - current connections: " + str( self.db_pool ), 1)
         return False


   def db_connected(self, conn=None):
      if conn == None : conn = self.get_db()
      if conn == None : return False


   # wrapper to catch mysql disconnections
   def db_query(self, sql, args=None, conn=None ):
      if conn == None : conn = self.get_db()
      try:
         cursor = conn.cursor()
         cursor.execute(sql, args)
         return cursor
      except (AttributeError, MySQLdb.OperationalError), e:
         self.debug("db_query - exception: " + str(e), 1)
         time.sleep(10) # this is important - if mysql server is not ready yet proximus will crash
         if self.db_connect() :
            conn = self.get_db()
            cursor = conn.cursor()
            cursor.execute(sql, args)
            return cursor
         return None


   # updates the database cache
   def db_query_cache_update(self, sql, args=None, conn=None) :
      if conn == None : conn = self.get_db()

      cursor = self.db_query(sql, args, conn)
      if cursor is not None:
         result = cursor.fetchall()
         self.cache[sql + str(args)] = {'time': int(time.time()), 'result': result }
         self.debug("Number of cached queries: " + str(len(self.cache)), 8)
         return result
      else:
         return None


   # mysql wrapper that caches queries - how cool is that?
   def db_query_cache(self, sql, args=None, conn=None) :
      if conn == None : conn = self.get_db()

      if settings['cache_time'] <= 0 :
         # if cache is turned off send do a query
         cursor = self.db_query(sql, args, conn)
         return cursor.fetchall()

      args_key = str(args)
      # if key is in cache 
      if sql + args_key in self.cache :
         # if cache_time is over update the query cache
         if ( int(time.time()) - self.cache[sql + args_key]['time'] ) > settings['cache_time'] :
            self.debug("Data from db - update..", 9)
            return self.db_query_cache_update(sql, args, conn)
         # if cache_time is not yet over return from cache
         else :
            self.debug("Data from cache..", 9)
            return self.cache[sql + args_key]['result']
      # if we don't have it in cache, save it
      else :
         self.debug("Data from db..", 9)
         return self.db_query_cache_update(sql, args, conn)


   # mysql wrapper that caches queries - how cool is that?
   def verify_cache(self) :
      self.debug("Queries in cache: " + str( len(self.cache) ), 8)
      for key,entry in self.cache.items() :
         if ( int(time.time()) - entry['time'] ) > settings['cache_time'] :
            del self.cache[key]


   ################
   ################
   ## updating of files
   ########
   ########

   def start_list_update_thread(self):
      # prepare socket
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.setblocking(False)

      # Start the scheduler
      self.sched.start()
      # Schedule job_function to be called
      self.job_bind = self.sched.add_interval_job(self.job_testbind, seconds=5)


   def job_testbind(self):
      self.verify_cache()
      try:
         self.socket.bind(("127.0.0.1", settings['port']))
         self.socket.listen(1)
         # Schedule update job

         # if database connection is established go on
         if self.db_connect() :
            # deactivate bindtest job
            self.sched.unschedule_job(self.job_bind)
            # schedule new update lists job
            self.job_listupdate = self.sched.add_interval_job(self.job_update, seconds = settings['list_update_interval'] )
            self.log("I'm the master process now!")
         else :
            self.socket.close()
      except socket.error, e:
         None


   def job_update(self):
      #self.log("running.......")
      self.update_lists()
      self.verify_cache()


   def update_lists(s):
      s.reloadNeeded = False

      s.debug("Updating lists now", 2)

      sql = "SELECT sitename, description \
            FROM noauth_rules \
            WHERE type='%s' \
               AND (location_id = %s OR location_id = 1 OR location_id IS NULL) \
               AND (valid_until IS NULL OR valid_until > NOW())" 

      if not s.update_file("noauth_dst_ip", sql % ('IP', settings['location_id']) ) :
         return False
      if not s.update_file("noauth_dst_dn", sql % ('DN', settings['location_id']) ) :
         return False

      if s.reloadNeeded == True:
         s.debug("Lists have changed Squid reload needed", 1)
         s.reload_parent()
      else:
         s.debug("Lists unchanged, no reload needed", 2)
      # tell that updating went fine
      return True


   def update_file(s, filename, query):
      # query the db using the thread db cursor
      # if we use the same cursor for both processes
      # they will interfere with each other
      cursor = s.db_query (query)
      rows = cursor.fetchall()
      #s.log("MySQL disconnected; Master exiting.")
      # tell previous function that something went wrong

      data = ""
      for row in rows:
         data += row['sitename'] + "\n"

      # get hashes
      filename = settings['vardir'] + filename
      prehash = s.get_md5( s.read_file(filename) )
      curhash = s.get_md5( data )
      #print prehash
      #print curhash

      # compare hashes and reload if needed
      if curhash != prehash :
         s.write_file( filename, data )
         s.reloadNeeded = True
      # tell that everything went fine
      return True


   def reload_parent(s):
      cmd = settings['reload_command']
      meth = settings['reload_method']

      if ( metH == "command" ) and ( cmd ) :
         s.log("Attention, going to reload squid now, using: + " + cmd )
         status, output = commands.getstatusoutput( cmd )
         s.log("Attention, output of reload command: " + output )
         return status
      elif meth == "signal" :
         s.log("Attention, going to send SIGHUP to my parent process: + " + str(os.getppid()) )
         os.kill(os.getppid(), signal.SIGHUP)
      else:
         s.log("Attention, not reloading since no valid 'reload_method' is configured in the config: " + meth )


   def get_md5(s, str):
      md5 = hashlib.md5()
      if str != None:
         md5.update( str )
         return md5.digest()


   ################
   ################
   ## User authentication
   ########
   ########

   def check_auth(s, line):
      creds = string.split(line)
      if len(creds) < 2:
         s.debug("Auth failed; input has wrong format; should be 'username password'", 2)
         return s.auth_deny()

      username = creds[0]
      password = creds[1]
      salt = settings['auth_salt']
      user = s.fetch_userinfo(username)
      pwhash = s.get_sha1(password, salt)

      if user and ( user['password'] == pwhash ):
         s.debug("Auth OK; user: %s" % username, 3)
         return s.auth_grant()
      else :
         s.debug("Auth failed; user: %s" % username, 2)
         return s.auth_deny()

   def auth_grant(s):
      return "OK"

   def auth_deny(s):
      return "ERR"

   def get_sha1(s, str, salt=""):
      sha1 = hashlib.sha1()
      if str != None:
         if salt != "":
            sha1.update( salt + str )
            return sha1.hexdigest()
         sha1.update( str )
         return sha1.hexdigest()


   ################
   ################
   ## Request processing
   ########
   ########

   # called when a site is blocked
   def deny(s):
      return "302:%sproximus.php?action=%s&site=%s" % ( settings['redirection_url'], "deny", request['sitename'] )

   # called when access to a site is granted
   def grant(s):
      return ""

   # takes the user home...
   def takeHome(s):
      return "302:%sproximus.php" % ( settings['redirection_url'] )

   # called when a request has to be learned
   def learn(s):
      # check if site has already been learned
      cursor = s.db_query ("SELECT id \
                        FROM logs \
                        WHERE \
                           user_id = %s \
                           AND protocol = %s \
                           AND source != %s \
                           AND \
                              ( sitename = %s OR \
                              %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                        ", (user['id'], request['protocol'], "REDIRECT", request['sitename'], request['sitename']))
      dyn = cursor.fetchone()
      if (dyn == None) :
         s.db_query ("INSERT INTO logs (sitename, ipaddress, user_id, location_id, protocol, source, created) \
                           VALUES (%s, %s, %s, %s, %s, %s, NOW()) \
                  ", (request['sitename_save'], request['src_address'], user['id'], settings['location_id'], request['protocol'], "LEARN"))
      else :
         request['id'] = dyn['id']
         s.db_query ("UPDATE logs SET hitcount=hitcount+1 \
                              WHERE id = %s ", ( request['id'] ) )


   # checks if a redirect has been logged and writes it into the db if not..
   def redirect_log(s):
      global request

      cursor = s.db_query ("INSERT INTO logs (sitename, ipaddress, user_id, protocol, location_id, source, created, hitcount) \
                           VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s) \
                         ON DUPLICATE KEY UPDATE hitcount=hitcount+1 \
                  ", (request['sitename_save'], request['src_address'], user['id'], request['protocol'], settings['location_id'], "REDIRECT", 1 ))
      request['id'] = cursor.lastrowid


   # checks if a redirect has been logged and writes it into the db if not..
   def redirect_log_hit(s, id):
      s.db_query ("UPDATE logs SET hitcount=hitcount+1 WHERE id = %s", (request['id']))


   # send redirect to the browser
   def redirect_send(s):
      if request['protocol'] == "SSL" :
         # default redirection method - if not further specified
         return "302:%sproximus.php?action=confirm&site=%s&id=%s&url=%s" % (settings['redirection_url'], request['sitename_save'], request['id'], base64.b64encode("https://"+request['sitename']))

      else:
         # its http
         return "302:%sproximus.php?action=confirm&site=%s&id=%s&url=%s" % (settings['redirection_url'], request['sitename_save'], request['id'], base64.b64encode(request['url']))


   # called when a request is redirected
   def redirect(s):
      global request

      if request['sitename'].startswith(settings['retrain_key']) :
         key = settings['retrain_key']
         request['sitename'] = re.sub("^"+key, "", request['sitename'])
         request['sitename_save'] = re.sub("^www\.", "", request['sitename'])
         request['url'] = re.sub(key+request['sitename'], request['sitename'], request['url'])
         s.redirect_log()
         return s.redirect_send()


      ######
      ## check if user has the right to access this site, if not check against shared-subsites if enabled 
      ##

      # check if user has already added site to dynamic rules
      cursor = s.db_query ("SELECT sitename, id, source \
                        FROM logs \
                        WHERE \
                              user_id = %s \
                              AND protocol = %s \
                              AND source != %s \
                           AND \
                              ( sitename = %s OR \
                              %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                        ", (user['id'], request['protocol'], "REDIRECT", request['sitename'], request['sitename']))
      dyn = cursor.fetchone()
      if (dyn != None) :   # user is allowed to access this site
         s.debug("Req  "+ str(s.req_id) +": REDIRECT; Log found; " + pprint.pformat(dyn), 2 )
         request['id'] = dyn['id']
         s.redirect_log_hit(request['id'])
         return s.grant()
      elif settings['subsite_sharing'] == "own_parents" :    # check if someone else has already added this site as a children
         cursor = s.db_query ("SELECT log2.sitename AS sitename, log2.id AS id \
                           FROM logs AS log1, logs AS log2 \
                           WHERE \
                                 log1.parent_id = log2.id \
                                 AND log1.protocol = %s \
                                 AND log1.source != %s \
                              AND \
                                 ( log1.sitename = %s OR \
                                 %s RLIKE CONCAT( '.*[[.full-stop.]]', log1.sitename, '$' )) \
                           ", (request['protocol'], "REDIRECT", request['sitename'], request['sitename']))
         rows1 = cursor.fetchall()
         cursor = s.db_query ("SELECT sitename, id \
                           FROM logs \
                           WHERE \
                                 user_id = %s \
                                 AND parent_id IS NULL \
                                 AND source != %s \
                           ", (user['id'], "REDIRECT"))
         rows2 = cursor.fetchall()

         for row1 in rows1:
            for row2 in rows2:
               if row1['sitename'] == row2['sitename'] :
                  s.debug("Debug REDIRECT; Log found with subsite sharing - own_parents; Log-id=" + str(row1['id']), 2)
                  return s.grant()
      elif settings['subsite_sharing'] == "all_parents" :  # check if someone else has already added this site as a children 
         cursor = s.db_query ("SELECT sitename, id \
                           FROM logs \
                           WHERE \
                                 parent_id IS NOT NULL \
                                 AND source != %s \
                              AND \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                           ", ("REDIRECT", request['sitename'], request['sitename']))
         all = cursor.fetchone()
         if (all != None) :
            s.debug("Debug REDIRECT; Log found with subsite sharing - all_parents; Log-id="+str(all['id']), 2)
            return s.grant()

      # if we get here user is not yet allowed to access this site
      s.debug("Debug REDIRECT; No log found; DENY", 2)
      # log request
      s.redirect_log()
      return s.redirect_send()
      

   def send_mail(s, subject, body):
      smtp = smtplib.SMTP(settings['smtpserver'])
      msg = MIMEText(body)
      msg['Subject'] = subject
      msg['From'] = "ProXimus"
      msg['To'] = user['emailaddress']
      if settings['admincc'] == 1 :
         msg['Cc'] = settings['admin_email']
         smtp.sendmail(settings['admin_email'], settings['admin_email'], msg.as_string())
      smtp.sendmail(settings['admin_email'], user['emailaddress'], msg.as_string())
      smtp.close()


   def deny_mail_user(s):
      # if user doesn't have an email address skip the part below
      if user['emailaddress'] == "":
         return s.deny()

      # check if mail has already been sent
      cursor = s.db_query ("SELECT id  \
                           FROM maillog \
                           WHERE \
                              user_id = %s \
                              AND (HOUR(NOW()) - HOUR(sent)) <= %s \
                              AND \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                              AND \
                                 ( protocol = %s OR \
                                 protocol = '*' ) \
                              ", (user['id'], settings['mail_interval'], request['sitename'], request['sitename'], request['protocol']) )
      result = cursor.fetchone()
      if (result == None) : # no mail has been sent recently
         if request['protocol'] == "SSL" :
            scheme = "https"
         else :
            scheme = "http"

         s.send_mail('Site '+request['sitename']+' has been blocked', "Dear User! \n\nYour request to "+scheme+"://"+request['sitename']+" has been blocked. \n\nIf you need access to this page please contact your Administrator.\n\nProXimus")
         
         # log that a mail has been sent
         cursor = s.db_query ("INSERT INTO maillog (sitename, user_id, protocol, sent) \
                              VALUES (%s, %s, %s, NOW()) ", (request['sitename_save'], user['id'], request['protocol']))
         dyn = cursor.fetchone()
      return s.deny()


   def parse_url(s, url, method="GET"):
      # also keep the original url
      r = {}
      r['url'] = url

      if method == "CONNECT" :
         """it's ssl"""
         r['protocol'] = "SSL"
         r['sitename'] = url.split(":", 1)[0]
      else :
         """it' http"""
         r['protocol'] = "HTTP"
         # scheme://host/path;parameters?query#fragment
         (scheme,host,path,parameters,query,fragment) = urlparse(url)
         r['sitename'] = host.split(":", 1)[0]

      # prepare for latter use...
      r['sitename_save'] = re.sub("^www\.", "", r['sitename'])
      return r


   def parse_line(s, line):
      withdraw = string.split(line)
      if len(withdraw) >= 5:
         # all needed parameters are given
         url = withdraw[0]
         src_address = withdraw[1]
         ident = withdraw[2]
         method = withdraw[3]
      else:
         # not enough parameters - deny
         return False

      # parse url and fill request
      request = s.parse_url(url, method)

      # prepare username
      if settings['regex_cut'] != "" :
         request['user'] = re.sub(settings['regex_cut'], "", ident.lower() )

      # remove "/-" from source ip address
      request['src_address'] = re.sub("/.*", "", src_address)
      return request


   def fetch_userinfo(s, ident):
      if (ident == "-") or (ident == "") :
         return None

      # get user
      try:
         user = s.db_query_cache("SELECT id, username, password, location_id, emailaddress, group_id FROM users WHERE username = %s AND active = 'Y'", ident)[0]
         user['emailaddress'] = user['emailaddress'].rstrip('\n')
      except (TypeError, IndexError), e:
         return None

      #pprint.pprint(user)   ## debug
      if user != None :
         s.debug("Req  "+ str(s.req_id) +": User found; " + pprint.pformat(user) , 3)
      else :
         s.debug("Req  "+ str(s.req_id) +": User not found; ident="+ident, 2)

      return user
      # make all vars lowercase to make sure they match
      #ident = escape(ident.lower())


   # tests if a ip address is within a subnet
   def addressInNetwork(s, ip, net):
      try:
         ipaddr = int(''.join([ '%02x' % int(x) for x in ip.split('.') ]), 16)
         netstr, bits = net.split('/')
         netaddr = int(''.join([ '%02x' % int(x) for x in netstr.split('.') ]), 16)
         mask = (0xffffffff << (32 - int(bits))) & 0xffffffff
         return (ipaddr & mask) == (netaddr & mask)
      except ValueError:
         return False;


   # tests if a sitename matches
   def check_sitename(s, sitename, rule):
      if rule.startswith("regex:") :
         # if its a regex rule strip off the prefix
         regex = re.sub("^regex:", "", rule)
      else :
         if ( rule == "*" ) or ( rule == sitename ) :
            return True
         else :
            # convert from our matching syntax to regex
            rule = rule.replace('.', '\.') # escape the dot
            rule = rule.replace('-', '\-') # escape the dash.. could mean range
            rule = rule.replace('*', '.*') # prepend star with a dot
            regex = ".*\." + rule + "$"

      # check if the regex matches
      # print rule + " / " + regex + " :"
      if re.search(regex, sitename) != None :
         return True
      else :
         return False

   # check if it is a blocked network
   def check_blocked_network(s, src_ip):
      rows = s.db_query_cache ("SELECT network \
               FROM blockednetworks \
               WHERE \
                     ( location_id = %s \
                     OR location_id = 1 ) ",
               (settings['location_id'] ))
      for row in rows:
         if src_ip == row['network'] :
            return True
         if s.addressInNetwork( src_ip,  row['network'] ) :
            return True
      return False


   def check_request(s, line):
      global request, user
      if not s.db_connected() : s.grant()

      request = s.parse_line(line)
      if request == False:
         return s.deny()

      user = s.fetch_userinfo(request['user'])

      # allow access to to proximuslog website
      if request['sitename'] == settings['redirection_host'] :
         return s.grant()
      # shortcut
      if request['sitename'] == "proximus" :
         return s.takeHome()


      ######
      ## Global blocked network check
      ##
      if s.check_blocked_network( request['src_address'] ) :
         return s.deny()


      ######
      ## Global no-auth check
      ##
      if user == None :
         # since squid is configured to require user auth
         # and no user identification is sent the site must be in the no-auth table
         s.debug("Req  "+ str(s.req_id) +": ALLOW - Request with no user-id - looks like a NoAuth rule ;-)", 2)
         return s.grant()
      #else :
         # actually this should not be nessecary - the browser should never
         # send user identification if the site is in the no-auth table;
         # in case it does we have that query
         # so commenting this out now
         # cursor = s.db_query ("SELECT sitename, protocol  \
         #                     FROM noauth_rules \
         #                     WHERE \
         #                           ( sitename = %s OR \
         #                           %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
         #                        AND \
         #                           ( protocol = %s OR \
         #                           protocol = '*' )", (request['sitename'], request['sitename'], request['protocol']) )
         #rows = cursor.fetchall()
         #for row in rows:
         #   return grant()


      ######
      ## retrieve rules for user
      ##

      # check if we could retrieve user information
      if user['id'] != None :
         rules = s.db_query_cache ("SELECT id, sitename, policy, location_id, group_id, priority, description \
                  FROM rules \
                  WHERE \
                        ( group_id = %s \
                        OR group_id = 0 ) \
                     AND \
                        ( location_id = %s \
                        OR location_id = 1 ) \
                     AND \
                        ( protocol = %s \
                        OR protocol = '*' ) \
                     AND \
                        ( starttime is NULL AND endtime is NULL \
                        OR starttime <= NOW() AND NOW() <= endtime ) \
                  ORDER BY priority DESC, location_id",
                  (user['group_id'], user['location_id'], request['protocol']))
      for rule in rules:
         if s.check_sitename( request['sitename'], rule['sitename'] ) :
            s.debug("Req  "+ str(s.req_id) +": Rule found; " + pprint.pformat(rule), 2)
            if rule['policy'] == "ALLOW" :
               return s.grant()
            elif rule['policy'].startswith("REDIRECT") :
               request['redirection_method'] = rule['policy']
               return s.redirect()
            elif rule['policy'] == "DENY_MAIL" :
               return s.deny_mail_user()
            elif rule['policy'] == "DENY" :
               return s.deny()
            elif rule['policy'] == "LEARN" :
               s.learn()
               return s.grant()
         else :
            s.debug("Req  "+ str(s.req_id) +": Rule doesn't match; " + pprint.pformat(rule), 4)

      s.debug("Req  "+ str(s.req_id) +": no rule found; using default deny", 2)

      # allow access if no rule did match until here ;-)
      return s.grant()



if __name__ == "__main__":
   import argparse
   parser = argparse.ArgumentParser(description='ProXimus redirector - This program is intended to be integrated into squid, alternatively use the options listed below.')
   parser.add_argument('-u', '--updatelists', action='store_true', help='Updates noauth lists and exits')
   parser.add_argument('-c', '--checkconfig', action='store_true', help='Check config and database connection and exit')
   parser.add_argument('-a', '--auth', action='store_true', help='Run ProXimus in authenticator mode')
   parser.add_argument('-d', '--debug', action='store', help='Set debbuging level', type=int, default=0, metavar='N')
   parser.add_argument('-i', '--interactive', action='store_true', help='Write everything to stdout; only for testing')

   args = parser.parse_args()
   options = vars(args)
   #pprint.pprint(options)

   # delete debug option if it was not set
   if not options['debug'] :
      del options['debug']

   if options['updatelists'] :
      options['debug'] = 2
      options['interactive'] = True
      sr = Proximus(options)
      sr.update_lists()
   elif options['auth'] :
      sr = Proximus(options)
      sr.run_auth()
   elif options['checkconfig'] :
      options['debug'] = 2
      options['interactive'] = True
      sr = Proximus(options)
      sr.check_config()
   else:
      sr = Proximus(options)
      sr.run()


