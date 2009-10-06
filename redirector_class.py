import urlparse
import MySQLdb
import re
import sys,string
import base64
import smtplib
from email.MIMEText import MIMEText

uparse, ujoin = urlparse.urlparse , urlparse.urljoin

# define globaly used variables
settings = []
request = {'sitename':None, 'sitename_save':None, 'protocol':None, 'siteport':None, 'src_address':None, 'url':None, 'redirection_method':None, 'id':None }
user = {'ident':None, 'id':None, 'name':None, 'loc_id':None, 'group_id':None, 'email':None }

def log(s):
    f = open("/var/log/squid/redirector_class.log","a")
    f.write(s+'\n')
    f.close()

# called when a site is blocked
def deny():
   return "302:http://%s/forbidden.html" % ( settings['redirection_host'] )

# called when access to a site is granted
def grant():
   return ""

# called when a request has to be learned
def learn():
   global settings, request, user
   db_cursor = settings['db_cursor']
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
      db_cursor.execute ("UPDATE logs SET hitcount=hitcount+1 \
                           WHERE id = %s \
                           ", ( request['id'] ) )
   return grant()

# checks if a redirect has been logged and writes it into the db if not..
def redirect_log():
   global settings, request, user
   db_cursor = settings['db_cursor']

   # check if request has already been logged
   db_cursor.execute ("SELECT id, hitcount \
                  FROM logs \
                  WHERE \
                        user_id = %s \
                        AND protocol = %s \
                     AND \
                        ( sitename = %s OR \
                        %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                  ", (user['id'], request['protocol'], request['sitename'], request['sitename']))
   dyn = db_cursor.fetchone()
   if (dyn != None) : # request has alredy been logged
      # set id
      request['id'] = dyn[0]
      db_cursor.execute ("UPDATE logs SET hitcount=hitcount+1 \
                           WHERE id = %s \
                           ", ( request['id'] ) )
   else :     # request has not been logged yet
      db_cursor.execute ("INSERT INTO logs (sitename, ipaddress, user_id, protocol, location_id, source, created, hitcount) \
                         VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s) \
                  ", (request['sitename_save'], request['src_address'], user['id'], request['protocol'], settings['location_id'], "REDIRECT", 1))
      request['id'] = db_cursor.lastrowid

# send redirect to the browser
def redirect_send_old():
   global settings, request, user
   db_cursor = settings['db_cursor']

   if request['protocol'] == "SSL" :
      if request['redirection_method'] == "REDIRECT_HTTP" :
         # redirect by sending a HTTP 302 status code - not all browsers accept this
         return "302:http://%s/proximuslog/logs/confirm/site:%s/proto:%s/ip:%s/uid:%s/locid:%s/url:%s" % (settings['redirection_host'], request['sitename_save'], request['protocol'], request['src_address'], user['id'], settings['location_id'], base64.b64encode("https://"+request['sitename']))
      
      elif request['redirection_method'] == "REDIRECT_SSL" :
         # the webserver there can read the requested host + requested uri and then redirect to proximuslog (SSL Certificate will not fit)
         return "%s:443" % (settings['redirection_host'])
 
      elif request['redirection_method'] == "REDIRECT_SSL_GEN" :
         # generate a SSL certificate on the fly and present it to the requesting browser 
         # not implemented yet
         return "%s:443" % (settings['redirection_host'])
      
      else :
         # default redirection method - if not further specified
         return "302:http://%s/proximuslog/logs/confirm/site:%s/proto:%s/ip:%s/uid:%s/locid:%s/url:%s" % (settings['redirection_host'], request['sitename_save'], request['protocol'], request['src_address'], user['id'], settings['location_id'], base64.b64encode("https://"+request['sitename']))

   else:
      # its http
      return "302:http://%s/proximuslog/logs/confirm/site:%s/proto:%s/ip:%s/uid:%s/locid:%s/url:%s" % (settings['redirection_host'], request['sitename_save'], request['protocol'], request['src_address'], user['id'], settings['location_id'], base64.b64encode(request['url']))

# send redirect to the browser
def redirect_send():
   global settings, request, user
   db_cursor = settings['db_cursor']

   if request['protocol'] == "SSL" :
      if request['redirection_method'] == "REDIRECT_HTTP" :
         # redirect by sending a HTTP 302 status code - not all browsers accept this
         return "302:http://%s/proximuslog/logs/confirm/site:%s/id:%s/url:%s" % (settings['redirection_host'], request['sitename_save'], request['id'], base64.b64encode("https://"+request['sitename']))
      
      elif request['redirection_method'] == "REDIRECT_SSL" :
         # the webserver there can read the requested host + requested uri and then redirect to proximuslog (SSL Certificate will not fit)
         return "%s:443" % (settings['redirection_host'])
 
      elif request['redirection_method'] == "REDIRECT_SSL_GEN" :
         # generate a SSL certificate on the fly and present it to the requesting browser 
         # not implemented yet
         return "%s:443" % (settings['redirection_host'])
      
      else :
         # default redirection method - if not further specified
         return "302:http://%s/proximuslog/logs/confirm/site:%s/id:%s/url:%s" % (settings['redirection_host'], request['sitename_save'], request['id'], base64.b64encode("https://"+request['sitename']))

   else:
      # its http
      return "302:http://%s/proximuslog/logs/confirm/site:%s/id:%s/url:%s" % (settings['redirection_host'], request['sitename_save'], request['id'], base64.b64encode(request['url']))


# called when a request is redirected
def redirect():
   global settings, request, user
   db_cursor = settings['db_cursor']

   if request['sitename'].startswith(settings['retrain_key']) :
      key = settings['retrain_key']
      request['sitename'] = re.sub("^"+key, "", request['sitename'])
      request['sitename_save'] = re.sub("^www\.", "", request['sitename'])
      request['url'] = re.sub(key+request['sitename'], request['sitename'], request['url'])
      redirect_log()
      return redirect_send()


   ######
   ## check if user has the right to access this site, if not check against shared-subsites if enabled 
   ##

   # log the request
   redirect_log()

   # check if user has already added site to dynamic rules
   db_cursor.execute ("SELECT sitename \
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
      return grant()
   elif settings['subsite_sharing'] == "own_parents" :    # check if someone else has already added this site as a children
      db_cursor.execute ("SELECT log2.sitename, log2.id \
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
            if row1[0] == row2[0] :
               return grant()
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
         return grant()

   # if we get here user is not yet allowed to access this site
   return redirect_send()
   

def send_mail(subject, body):
   global settings, user
   smtp = smtplib.SMTP(settings['smtpserver'])
   msg = MIMEText(body)
   msg['Subject'] = subject
   msg['From'] = "ProXimus"
   msg['To'] = user['email']
   if settings['admincc'] == 1 :
      msg['Cc'] = settings['admin_email']
      smtp.sendmail(settings['admin_email'], settings['admin_email'], msg.as_string())
   smtp.sendmail(settings['admin_email'], user['email'], msg.as_string())
   smtp.close()


def deny_mail_user():
   global settings, user, request

   # if user doesn't have an email address skip the part below
   if user['email'] == "":
      return deny()

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

      send_mail('Site '+request['sitename']+' has been blocked', "Dear User! \n\nYour request to "+scheme+"://"+request['sitename']+" has been blocked. \n\nIf you need access to this page please contact your Administrator.\n\nProXimus")
      
      # log that a mail has been sent
      db_cursor.execute ("INSERT INTO maillog (sitename, user_id, protocol, sent) \
                           VALUES (%s, %s, %s, NOW()) ", (request['sitename_save'], user['id'], request['protocol']))
      dyn = db_cursor.fetchone()
  
   return deny()


def parse_line(line):
   global request, user
   uparse, ujoin = urlparse.urlparse , urlparse.urljoin
   url,src_address,ident,method,dash=string.split(line)
   # scheme://host/path;parameters?query#fragment
   (scheme,host,path,parameters,query,fragment) = uparse(url)

   user['ident'] = ident.lower()
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


def fetch_userinfo(ident):
   global settings, user

   if ident != "-" :
      # get user
      try:
         db_cursor = settings['db_cursor']
         db_cursor.execute ("SELECT id, username, location_id, emailaddress, group_id FROM users WHERE username = %s", ident)
         row = db_cursor.fetchone()
         user['id'] = row[0]
         user['name'] = row[1]
         user['loc_id'] = row[2]
         user['email'] = row[3].rstrip('\n')
         user['group_id'] = row[4]
      except TypeError:
         user['id'] = None
   else :
      user['id'] = None

   # make all vars lowercase to make sure they match
   #sitename = escape(sitename)
   #ident = escape(ident.lower())
   #src_address = escape(src_address)


def check_request(passed_settings, line):
   global settings, request, user
   settings = passed_settings

   db_cursor = settings['db_cursor']

   parse_line(line)
   fetch_userinfo(user['ident'])

   # allow access to to proximuslog website
   if request['sitename'] == settings['redirection_host'] :
      return grant()

   ######
   ## Global no-auth check
   ##
   if user['id'] == None :
      # since squid is configured to require user auth
      # and no user identification is sent the site must be in the no-auth table
      return grant()
   else :
      # actually 'else' should never happen - the browser should never
      # send user identification if the site is in the no-auth table;
      # in case it does we have that query
      db_cursor.execute ("SELECT sitename, protocol  \
                           FROM global_noauth \
                           WHERE \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                              AND \
                                 ( protocol = %s OR \
                                 protocol = '*' )", (request['sitename'], request['sitename'], request['protocol']) )
      rows = db_cursor.fetchall()
      for row in rows:
         return grant()


   ######
   ## retrieve rules for user
   ##

   # check if we could retrieve user information
   if user['id'] != None :
      db_cursor.execute ("SELECT sitename, protocol, policy, priority, description \
               FROM rules \
               WHERE \
                  group_id = %s \
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
               (user['group_id'], user['loc_id'], request['sitename'], request['sitename'], request['protocol']))
   rows = db_cursor.fetchall()
   for row in rows:
      if row[2] == "ALLOW" :
         return grant()
      elif row[2].startswith("REDIRECT") :
         request['redirection_method'] = row[2]
         return redirect()
      elif row[2] == "DENY_MAIL" :
         return deny_mail_user()
      elif row[2] == "DENY" :
         return deny()
      elif row[2] == "LEARN" :
         return learn()

   # deny access if the request was not accepted until this point ;-)
   return deny()

