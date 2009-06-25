"""Reloadable module allows arbitrary url transformations.
        must define reload_after (an integer), and rewrite(url)."""

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
request = {'sitename':None, 'sitename_save':None, 'protocol':None, 'siteport':None, 'src_address':None, 'url':None, 'redirection_method':None }
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
   db_cursor.execute ("SELECT sitename \
                     FROM logs \
                     WHERE \
                           ( user_id = %s ) \
                        AND \
                           ( sitename = %s OR \
                           %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                     ", (user['id'], request['sitename'], request['sitename']))
   dyn = db_cursor.fetchone()
   if (dyn == None) :
      db_cursor.execute ("INSERT INTO logs (sitename, ipaddress, user_id, location_id, protocol, source, created) \
                        VALUES (%s, %s, %s, %s, %s, %s, NOW()) ", (request['sitename_save'], request['src_address'], user['id'], settings['location_id'], request['protocol'], "LEARN"))
      dyn = db_cursor.fetchone()
   return ""


# called when a request is redirected
def redirect():
   global settings, request, user
   db_cursor = settings['db_cursor']

   ######
   ## write log into database
   ##

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
      return ""
   else :   # user is not yet allowed to access this site
      # check if request has already been logged
      db_cursor.execute ("SELECT sitename \
                     FROM logs \
                     WHERE \
                           user_id = %s \
                           AND protocol = %s \
                           AND source = %s \
                        AND \
                           ( sitename = %s OR \
                           %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                     ", (user['id'], request['protocol'], "REDIRECT", request['sitename'], request['sitename']))
      dyn = db_cursor.fetchone()
      if (dyn == None) :     # request has not been logged yet
         db_cursor.execute ("INSERT INTO logs (sitename, user_id, protocol, location_id, source, created) \
                            VALUES (%s, %s, %s, %s, %s, NOW()) \
                        ", (request['sitename_save'], user['id'], request['protocol'], settings['location_id'], "REDIRECT"))
         dyn = db_cursor.fetchone()

   ######
   ## redirect the browser to our site
   ##

   if request['protocol'] == "ssl" :
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
   db_cursor = settings['db_cursor']

    # check if mail has already been sent
   db_cursor.execute ("SELECT id  \
                        FROM maillog \
                        WHERE \
                           user_id = %s \
                           AND (HOUR(NOW()) - HOUR(sent)) <= 1 \
                           AND \
                              ( sitename = %s OR \
                              %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                           AND \
                              ( protocol = %s OR \
                              protocol = '*' ) \
                           ", (user['id'], request['sitename'], request['sitename'], request['protocol']) )
   result = db_cursor.fetchone()
   if (result == None) : # no mail has been sent recently
      if request['protocol'] == "ssl" :
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
      request['protocol'] = "ssl"
      request['sitename'] = scheme
      request['siteport'] = path
   else:
      """it' http"""
      request['protocol'] = "http"
      request['sitename'] = host.split(":", 1)[0]
      try:
         request['siteport'] = host.split(":", 1)[1]
      except IndexError,e:
         request['siteport'] = "80"

   request['sitename_save'] = re.sub("^www\.", "", request['sitename'])


def fetch_userinfo(ident):
   global settings, user

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
      # user not found in database redirect to default site
      user['group_id'] = None
      return deny(sitename,protocol)

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
   ## check if host is blocked globally
   ##
   db_cursor.execute ("SELECT sitename, protocol  \
                        FROM globalrules \
                        WHERE \
                              ( sitename = %s OR \
                              %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                           AND \
                              ( protocol = %s OR \
                              protocol = '*' )", (request['sitename'], request['sitename'], request['protocol']) )
   rows = db_cursor.fetchall()
   for row in rows:
      return deny()

   ######
   ## retrieve rules
   ##

   # check if the user is in a valid group (group_id 0 means no group)
   if (user['group_id'] != None) and (user['group_id'] != 0) :   # user is assigned to a group
      db_cursor.execute ("SELECT sitename, protocol, policy, priority, description \
                           FROM rules \
                           WHERE \
                                 ( group_id = %s \
                                 OR location_id = %s \
                                 OR location_id = 1 ) \
                              AND \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                              AND \
                                 ( protocol = %s OR \
                                 protocol = '*' ) \
                           ORDER BY priority DESC, location_id", (user['group_id'], user['loc_id'], request['sitename'], request['sitename'], request['protocol']))
   else :    # user is not assigned to a group
      db_cursor.execute ("SELECT sitename, protocol, policy, priority, description \
                           FROM rules \
                           WHERE \
                              group_id = 0 \
                              AND \
                                 ( location_id = %s \
                                 OR location_id = 1 ) \
                              AND \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT( '.*[[.full-stop.]]', sitename, '$' )) \
                              AND \
                                 ( protocol = %s OR \
                                 protocol = '*' ) \
                           ORDER BY priority DESC, location_id", (user['loc_id'], request['sitename'], request['sitename'], request['protocol']))
   rows = db_cursor.fetchall()
   for row in rows:
      if row[2] == "ALLOW" :
         break
      elif row[2].startswith("REDIRECT") :
         request['redirection_method'] = row[2]
         return redirect()
      elif row[2] == "DENY_MAIL" :
         return deny_mail_user()
      elif row[2] == "DENY" :
         return deny()
      elif row[2] == "LEARN" :
         return learn()

   # if we got to this point grant access ;-)
   return ""

