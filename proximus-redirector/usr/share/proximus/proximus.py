#!/usr/bin/python -u

import sys,string
import MySQLdb
import MySQLdb.cursors
import os, signal
import socket
import syslog
import pprint # for debugging

import urlparse
import re
import base64
import smtplib
from email.MIMEText import MIMEText

from apscheduler.scheduler import Scheduler
import hashlib
import commands


# define globaly used variables
settings = {}
request = {'sitename':None, 'sitename_save':None, 'protocol':None, 'siteport':None, 'src_address':None, 'url':None, 'redirection_method':None, 'id':None }
user = {'ident':None, 'id':None, 'username':None, 'location_id':None, 'group_id':None, 'emailaddress':None }

config_filename = "/etc/proximus/proximus.conf"
passthrough_filename = "/etc/proximus/passthrough"


class Proximus:
   def __init__(self, options):
      global db_cursor, settings

      # configure syslog
      syslog.openlog('proximus',syslog.LOG_PID,syslog.LOG_LOCAL5)
      self.stdin   = sys.stdin
      self.stdout  = sys.stdout

      # set options
      settings = options
      # read config file and connect to the database
      self.read_configfile()
      # combine / overwrite settings with passed options again... - kind of stupid..
      settings = dict(settings, **options)

      self.db_connect()
      self.get_settings_from_db()

      # debugging....
      #pprint.pprint(settings)  ## debug
      self.debug("Settings: " + pprint.pformat(settings, 3), 3 )

   def read_configfile(self):
      global settings

      config = {}
      config_file = self.open_file(config_filename, 'r')

      if config_file == None:
         error_msg = "ERROR: config file not found: " + config_filename
         self.log(error_msg)
         self._writeline(error_msg)
         sys.exit(1)
      else:
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
         config_file.close()

      if os.path.isfile(passthrough_filename) :
         self.log("Warning, file: "+passthrough_filename+" exists; Passthrough mode activated")
         config['passthrough'] = True
      else :
         config['passthrough'] = False

      # set defaults
      if not config.has_key("web_path") :
         config['web_path'] = "/proximus"

      # sanity checks
      # debug
      if config.has_key("debug") :
         config['debug'] = int(config['debug'])
      else :
         config['debug'] = 0

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

      settings = config
      #pprint.pprint(settings)  ## debug


   def db_connect(self):
      global db_cursor

      try:
         conn = MySQLdb.connect (host = settings['db_host'],
            user = settings['db_user'],
            passwd = settings['db_pass'],
            db = settings['db_name'], cursorclass=MySQLdb.cursors.DictCursor)
         db_cursor = conn.cursor ()
      except MySQLdb.Error, e:
         error_msg = "ERROR: please make sure that database settings are correctly set in " + config_filename
         self.log("ERROR: activating passthrough-mode until config is present")
         settings['passthrough'] = True

         self.log(error_msg)
         self._writeline(error_msg)


   # Get settings from db and catch error if no settings are stored
   def get_settings_from_db(self):
      global settings

      # Get the fully-qualified name.
      hostname = socket.gethostname()
      fqdn_hostname = socket.getfqdn(hostname)

      try:
         # Get proxy specific settings
         db_cursor.execute ("SELECT location_id, redirection_host, smtpserver, admin_email, admincc \
                           FROM proxy_settings \
                           WHERE fqdn_proxy_hostname = %s", ( fqdn_hostname ))
         query = db_cursor.fetchone()

         # combine with settings with existing ones
         settings = dict(settings, **query)

         # Get global settings
         db_cursor.execute ("SELECT name, value FROM global_settings")
         query = db_cursor.fetchall()
         for row in query:
            settings[row['name']] = row['value']
      
      # catch error if no settings are stored;
      # and activate passthrough mode
      except :
         error_msg = "ERROR: please make sure that a config for this node is stored in the database. Table-name: proxy_settings - Full qualified domain name: " + fqdn_hostname
         self.log("ERROR: activating passthrough-mode until config is present")
         self.log(error_msg)
         self._writeline(error_msg)
         settings['passthrough'] = True

   def run(self):
      # start list updating thread if configured
      if settings['reload_method'] in ["signal", "command"] :
         self.start_list_update_thread()

      self.log("started")
      self.req_id = 0
      line = self._readline()
      while line:
         if settings['passthrough'] == True :
            self._writeline("")
         else:
            self.req_id += 1
            self.debug("Req  " + str(self.req_id) + ": " + line, 1)
            response = self.check_request(line)
            self._writeline(response)
            self.debug("Resp " + str(self.req_id) + ": " + response, 1)
         line = self._readline()

   def check_config(self):
      settings['db_user'] = "***"
      settings['db_pass'] = "***"
      pprint.pprint(settings)
      self._writeline("")
      self.log("Config seems to be ok")
 
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


   ################
   ################
   ## updating of files
   ########
   ########

   def start_list_update_thread(self):
      # prepare socket
      self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.s.setblocking(False)

      # Start the scheduler
      self.sched = Scheduler()
      self.sched.start()
      # Schedule job_function to be called
      self.job_bind = self.sched.add_interval_job(self.job_testbind, seconds=5)


   def job_testbind(self):
      try:
         self.s.bind(("127.0.0.1", settings['port']))
         self.s.listen(1)

         # deactivate bindtest job
         self.sched.unschedule_job(self.job_bind)
         # Schedule job_function to be called every two hours
         self.sched.add_interval_job(self.job_update, seconds=5)
         # remove the previous scheduled job
         self.log("I'm now the master process!")
      except socket.error, e:
         None


   def job_update(self):
      #self.log("running.......")
      self.update_lists()


   def update_lists(s):
      global request, user
      s.reloadNeeded = False

      s.debug("Updating lists now", 2)

      sql = "SELECT sitename, description \
            FROM noauth_rules \
            WHERE type='%s' \
               AND (location_id = %s OR location_id = 1 OR location_id IS NULL) \
               AND (valid_until IS NULL OR valid_until > NOW())" 

      s.update_file("noauth_dst_ip", sql % ('IP', settings['location_id']) )
      s.update_file("noauth_dst_dn", sql % ('DN', settings['location_id']) )

      if s.reloadNeeded == True:
         s.debug("Lists have changed Squid reload needed", 1)
         s.reload_parent()
      else:
         s.debug("Lists unchanged, no reload needed", 2)


   def update_file(s, filename, query):
      filename = settings['vardir'] + filename
      prehash = s.md5_for_file(filename)

      f = s.open_file(filename, 'w')
      db_cursor.execute (query)
      rows = db_cursor.fetchall()

      for row in rows:
         f.write(row['sitename'] + "\n")
      f.close()

      if prehash != s.md5_for_file(filename):
         s.reloadNeeded = True


   def reload_parent(s):
      cmd = settings['reload_command']
      meth = settings['reload_method']

      if ( meth == "command" ) and ( cmd ) :
         s.log("Attention, going to reload squid now, using: + " + cmd )
         status, output = commands.getstatusoutput( cmd )
         s.log("Attention, output of reload command: " + output )
         return status
      elif meth == "signal" :
         s.log("Attention, going to send SIGHUP to my parent process: + " + str(os.getppid()) )
         os.kill(os.getppid(), signal.SIGHUP)
      else:
         s.log("Attention, not reloading since no valid 'reload_method' is configured in the config: " + meth )


   def md5_for_file(s, filename, block_size=2**20):
      md5 = hashlib.md5()

      f = s.open_file(filename, 'r')
      if f :
         while True:
            data = f.read(block_size)
            if not data:
               break
            md5.update(data)
         f.close()
         return md5.digest()


   ################
   ################
   ## Request processing
   ########
   ########

   # called when a site is blocked
   def deny(s):
      return "302:http://%s%s/forbidden.html" % ( settings['redirection_host'], settings['web_path'] )

   # called when access to a site is granted
   def grant(s):
      return ""

   # called when a request has to be learned
   def learn(s):
      global request, user

      # check if site has already been learned
      db_cursor.execute ("SELECT id \
                        FROM logs \
                        WHERE \
                           user_id = %s \
                           AND protocol = %s \
                           AND source != %s \
                           AND \
                              ( sitename = %s OR \
                              %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                        ", (user['id'], request['protocol'], "REDIRECT", request['sitename'], request['sitename']))
      dyn = db_cursor.fetchone()
      if (dyn == None) :
         db_cursor.execute ("INSERT INTO logs (sitename, ipaddress, user_id, location_id, protocol, source, created) \
                           VALUES (%s, %s, %s, %s, %s, %s, NOW()) \
                  ", (request['sitename_save'], request['src_address'], user['id'], settings['location_id'], request['protocol'], "LEARN"))
      else :
         request['id'] = dyn['id']
         db_cursor.execute ("UPDATE logs SET hitcount=hitcount+1 \
                              WHERE id = %s ", ( request['id'] ) )


   # checks if a redirect has been logged and writes it into the db if not..
   def redirect_log(s):
      global request, user

      db_cursor.execute ("INSERT INTO logs (sitename, ipaddress, user_id, protocol, location_id, source, created, hitcount) \
                           VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s) \
                         ON DUPLICATE KEY UPDATE hitcount=hitcount+1 \
                  ", (request['sitename_save'], request['src_address'], user['id'], request['protocol'], settings['location_id'], "REDIRECT", 1 ))
      request['id'] = db_cursor.lastrowid


   # checks if a redirect has been logged and writes it into the db if not..
   def redirect_log_hit(s, id):
      global request, user
      db_cursor.execute ("UPDATE logs SET hitcount=hitcount+1 WHERE id = %s", (request['id']))


   # send redirect to the browser
   def redirect_send(s):
      global request, user

      if request['protocol'] == "SSL" :
         # default redirection method - if not further specified
         return "302:http://%s%s/proximus.php?site=%s&id=%s&url=%s" % (settings['redirection_host'], settings['web_path'], request['sitename_save'], request['id'], base64.b64encode("https://"+request['sitename']))

      else:
         # its http
         return "302:http://%s%s/proximus.php?site=%s&id=%s&url=%s" % (settings['redirection_host'], settings['web_path'], request['sitename_save'], request['id'], base64.b64encode(request['url']))


   # called when a request is redirected
   def redirect(s):
      global request, user

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
      db_cursor.execute ("SELECT sitename, id, source \
                        FROM logs \
                        WHERE \
                              user_id = %s \
                              AND protocol = %s \
                              AND source != %s \
                           AND \
                              ( sitename = %s OR \
                              %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                        ", (user['id'], request['protocol'], "REDIRECT", request['sitename'], request['sitename']))
      dyn = db_cursor.fetchone()
      if (dyn != None) :   # user is allowed to access this site
         s.debug("Req  "+ str(s.req_id) +": REDIRECT; Log found; " + pprint.pformat(dyn), 2 )
         request['id'] = dyn['id']
         s.redirect_log_hit(request['id'])
         return s.grant()
      elif settings['subsite_sharing'] == "own_parents" :    # check if someone else has already added this site as a children
         db_cursor.execute ("SELECT log2.sitename AS sitename, log2.id AS id \
                           FROM logs AS log1, logs AS log2 \
                           WHERE \
                                 log1.parent_id = log2.id \
                                 AND log1.protocol = %s \
                                 AND log1.source != %s \
                              AND \
                                 ( log1.sitename = %s OR \
                                 %s RLIKE CONCAT( '.*[[.full-stop.]]', log1.sitename, '$' )) \
                           ", (request['protocol'], "REDIRECT", request['sitename'], request['sitename']))
         rows1 = db_cursor.fetchall()
         db_cursor.execute ("SELECT sitename, id \
                           FROM logs \
                           WHERE \
                                 user_id = %s \
                                 AND parent_id IS NULL \
                                 AND source != %s \
                           ", (user['id'], "REDIRECT"))
         rows2 = db_cursor.fetchall()

         for row1 in rows1:
            for row2 in rows2:
               if row1['sitename'] == row2['sitename'] :
                  s.debug("Debug REDIRECT; Log found with subsite sharing - own_parents; Log-id="+str(rows1['id']), 2)
                  return s.grant()
      elif settings['subsite_sharing'] == "all_parents" :  # check if someone else has already added this site as a children 
         db_cursor.execute ("SELECT sitename, id \
                           FROM logs \
                           WHERE \
                                 parent_id IS NOT NULL \
                                 AND source != %s \
                              AND \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                           ", ("REDIRECT", request['sitename'], request['sitename']))
         all = db_cursor.fetchone()
         if (all != None) :
            s.debug("Debug REDIRECT; Log found with subsite sharing - all_parents; Log-id="+str(all['id']), 2)
            return s.grant()

      # if we get here user is not yet allowed to access this site
      s.debug("Debug REDIRECT; No log found; DENY", 2)
      # log request
      s.redirect_log()
      return s.redirect_send()
      

   def send_mail(s, subject, body):
      global user
      smtp = smtplib.SMTP(settings['smtpserver'])
      msg = MIMEText(body)
      msg['Subject'] = subject
      msg['From'] = "ProXimus"
      msg['To'] = user['email']
      if settings['admincc'] == 1 :
         msg['Cc'] = settings['admin_email']
         smtp.sendmail(settings['admin_email'], settings['admin_email'], msg.as_string())
      smtp.sendmail(settings['admin_email'], user['emailaddress'], msg.as_string())
      smtp.close()


   def deny_mail_user(s):
      global user, request

      # if user doesn't have an email address skip the part below
      if user['emailaddress'] == "":
         return s.deny()

      # check if mail has already been sent
      db_cursor = settings['db_cursor']
      db_cursor.execute ("SELECT id  \
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
      result = db_cursor.fetchone()
      if (result == None) : # no mail has been sent recently
         if request['protocol'] == "SSL" :
            scheme = "https"
         else :
            scheme = "http"

         s.send_mail('Site '+request['sitename']+' has been blocked', "Dear User! \n\nYour request to "+scheme+"://"+request['sitename']+" has been blocked. \n\nIf you need access to this page please contact your Administrator.\n\nProXimus")
         
         # log that a mail has been sent
         db_cursor.execute ("INSERT INTO maillog (sitename, user_id, protocol, sent) \
                              VALUES (%s, %s, %s, NOW()) ", (request['sitename_save'], user['id'], request['protocol']))
         dyn = db_cursor.fetchone()
      return s.deny()


   def parse_line(s, line):
      global request, user
      # clear previous request data
      request = {}
      uparse, ujoin = urlparse.urlparse , urlparse.urljoin

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

      # scheme://host/path;parameters?query#fragment
      (scheme,host,path,parameters,query,fragment) = uparse(url)

      # prepare username
      user['ident'] = ident.lower()
      if settings['regex_cut'] != "" :
         user['ident'] = re.sub(settings['regex_cut'], "", user['ident'])

      # remove "/-" from source ip address
      request['src_address'] = re.sub("/.*", "", src_address)
      request['url'] = url

      if method == "CONNECT" :
         """it's ssl"""
         request['protocol'] = "SSL"
         request['sitename'] = scheme
         request['siteport'] = path
      else:
         """it' http"""
         request['protocol'] = "HTTP"
         request['sitename'] = host.split(":", 1)[0]
         try:
            request['siteport'] = host.split(":", 1)[1]
         except IndexError,e:
            request['siteport'] = "80"
      request['sitename_save'] = re.sub("^www\.", "", request['sitename'])


   def fetch_userinfo(s, ident):
      global user

      if ident != "-" :
         # get user
         try:
            db_cursor.execute ("SELECT id, username, location_id, emailaddress, group_id FROM users WHERE username = %s AND active = 'Y'", ident)
            user = db_cursor.fetchone()
            user['emailaddress'] = user['emailaddress'].rstrip('\n')
         except TypeError:
            user = None
      else :
         user = None

      #pprint.pprint(user)   ## debug
      if user != None :
         s.debug("Req  "+ str(s.req_id) +": User found; " + pprint.pformat(user) , 2)
      else :
         s.debug("Req  "+ str(s.req_id) +": No user found; ident="+ident, 2)
    
      # make all vars lowercase to make sure they match
      #sitename = escape(sitename)
      #ident = escape(ident.lower())
      #src_address = escape(src_address)


   # tests if a ip address is within a subnet
   def addressInNetwork(s, ip, net):
      import socket,struct
      try:
         ipaddr = int(''.join([ '%02x' % int(x) for x in ip.split('.') ]), 16)
         netstr, bits = net.split('/')
         netaddr = int(''.join([ '%02x' % int(x) for x in netstr.split('.') ]), 16)
         mask = (0xffffffff << (32 - int(bits))) & 0xffffffff
         return (ipaddr & mask) == (netaddr & mask)
      except ValueError:
         return False;


   def check_request(s, line):
      global request, user

      if s.parse_line(line) == False:
         return s.deny()
      s.fetch_userinfo(user['ident'])

      # allow access to to proximuslog website
      if request['sitename'] == settings['redirection_host'] :
         return s.grant()


      ######
      ## Global blocked network check
      ##
      db_cursor.execute ("SELECT network \
               FROM blockednetworks \
               WHERE \
                     ( location_id = %s \
                     OR location_id = 1 ) ",
               (settings['location_id'] ))
      rows = db_cursor.fetchall()
      for row in rows:
         if request['src_address'] == row['network'] :
            return s.deny();
         if s.addressInNetwork( request['src_address'] ,  row['network'] ) :
            return s.deny();


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
         #db_cursor.execute ("SELECT sitename, protocol  \
         #                     FROM noauth_rules \
         #                     WHERE \
         #                           ( sitename = %s OR \
         #                           %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
         #                        AND \
         #                           ( protocol = %s OR \
         #                           protocol = '*' )", (request['sitename'], request['sitename'], request['protocol']) )
         #rows = db_cursor.fetchall()
         #for row in rows:
         #   return grant()


      ######
      ## retrieve rules for user
      ##

      # check if we could retrieve user information
      if user['id'] != None :
         db_cursor.execute ("SELECT id, sitename, policy, location_id, group_id, priority, description \
                  FROM rules \
                  WHERE \
                        ( group_id = %s \
                        OR group_id = 0 ) \
                     AND \
                        ( location_id = %s \
                        OR location_id = 1 ) \
                     AND \
                        ( sitename = %s OR \
                        %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                     AND \
                        ( protocol = %s OR \
                        protocol = '*' ) \
                     AND \
                        ( starttime is NULL AND endtime is NULL OR \
                        starttime <= NOW() AND NOW() <= endtime ) \
                  ORDER BY priority DESC, location_id",
                  (user['group_id'], user['location_id'], request['sitename'], request['sitename'], request['protocol']))
      rules = db_cursor.fetchall()
      for rule in rules:
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

      s.debug("Req  "+ str(s.req_id) +": no rule found; using default deny", 2)

      # deny access if the request was not accepted until this point ;-)
      return s.deny()



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

   if options['updatelists'] :
      options['debug'] = 2
      options['interactive'] = True
      sr = Proximus(options)
      sr.update_lists()
   elif options['auth'] :
      print "Sorry, this is not implemented yet"
   elif options['checkconfig'] :
      options['debug'] = 2
      options['interactive'] = True
      sr = Proximus(options)
      sr.check_config()
   else:
      sr = Proximus(options)
      sr.run()


