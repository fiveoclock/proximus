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

# called when a request is redirected
def redirect():
   global settings, request, user

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
   # code here
   global settings, user
   smtp = smtplib.SMTP(settings['smtpserver'])
   msg['Subject'] = subject
   msg['From'] = "ProXimus"
   msg['To'] = user['email']
   msg = MIMEText(body)
   smtp.sendmail(settings['admin_email'], user_email, msg.as_string())
   smtp.close()


def deny_mail_user():
   global user, request
   send_mail('Site '+sitename+' has been blocked', "Dear User! \n\nYour request to https://"+sitename+" has been blocked. \n\nIf you need access to this page please contact your Administrator.\n\nProXimus")
   deny()


def parse_line(line):
   global request, user
   url,src_address,ident,method,dash=string.split(line)
   # scheme://host/path;parameters?query#fragment
   (scheme,host,path,parameters,query,fragment) = uparse(url)

   user['ident'] = ident
   # remove "/-" from source ip address
   request['src_address'] = re.sub("/.*", "", src_address)

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
   
   #request = {'sitename':None, 'protocol':None, 'siteport':None, 'src_address':None, 'url':None, 'redirection_method':None }
   #user = {'ident':None, 'id':None, 'name':None, 'loc_id':None, 'group_id':None, 'email':None }
 
   db_cursor = settings['db_cursor']

   parse_line(line)
   fetch_userinfo(user['ident'])

   # allow access to to proximuslog website
   if request['sitename'] == settings['redirection_host'] :
      grant()
 
   #
   # check if host is blocked globally
   #
   db_cursor.execute ("SELECT sitename, protocol  \
                        FROM globalrules \
                        WHERE \
                              ( sitename = %s OR \
                              %s RLIKE CONCAT('.*[.full-stop.]', sitename ) ) \
                           AND \
                              ( protocol = %s OR \
                              protocol = '*' )", (request['sitename'], request['sitename'], request['protocol']) )
   #print "SELECT sitename, siteport, description FROM rules WHERE globalflag = 1 AND sitename = %s OR sitename LIKE %s" % (sitename, '%'+sitename) 
   rows = db_cursor.fetchall()
   for row in rows:
      return deny()
     

   # check if the user is in a valid group (group_id 0 means no group)
   if (user['group_id'] != None) and (user['group_id'] != 0) :
      db_cursor.execute ("SELECT sitename, protocol, policy, priority, description \
                           FROM rules \
                           WHERE \
                                 ( group_id = %s \
                                 OR location_id = %s \
                                 OR location_id = 1 ) \
                              AND \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT('.*[.full-stop.]', sitename ) ) \
                              AND \
                                 ( protocol = %s OR \
                                 protocol = '*' ) \
                           ORDER BY priority DESC, location_id", (user['group_id'], user['loc_id'], request['sitename'], request['sitename'], request['protocol']))
   else :
      #print "group is set"
      db_cursor.execute ("SELECT sitename, protocol, policy, priority, description \
                           FROM rules \
                           WHERE \
                                 ( location_id = %s \
                                 OR location_id = 1 ) \
                              AND \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT('.*[.full-stop.]', sitename ) ) \
                              AND \
                                 ( protocol = %s OR \
                                 protocol = '*' ) \
                           ORDER BY priority DESC, location_id", (user['loc_id'], request['sitename'], request['sitename'], request['protocol']))
   rows = db_cursor.fetchall()
   for row in rows:
      if row[2] == "ALLOW" :
         break
      elif row[2].startswith("REDIRECT") :
         redirection_method = row[2]
         # check if user has already added site to dynamic rules
         db_cursor.execute ("SELECT sitename \
                           FROM logs \
                           WHERE \
                                 user_id = %s \
                                 AND protocol = %s \
                              AND \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT('.*[.full-stop.]', sitename ) ) \
                           ", (user['id'], request['protocol'], request['sitename'], request['sitename']))
         dyn = db_cursor.fetchone()
         if (dyn == None) :
            return redirect()
         else :
            break
         return redirect()
      elif row[2] == "DENY" :
         return deny()
      elif row[2] == "LEARN" :
         # check if site has already been learned
         db_cursor.execute ("SELECT sitename \
                           FROM logs \
                           WHERE \
                                 ( user_id = %s ) \
                              AND \
                                 ( sitename = %s OR \
                                 %s RLIKE CONCAT('.*[.full-stop.]', sitename ) ) \
                           ", (user_id, sitename, sitename))
         dyn = db_cursor.fetchone()
         if (dyn == None) :
            sitename_sav = re.sub("^www\.", "", sitename)
            db_cursor.execute ("INSERT INTO logs (sitename, ipaddress, user_id, location_id, protocol, source) \
                              VALUES (%s, %s, %s, %s, %s, %s) ", (sitename_sav, src_address, user_id, user_loc_id, protocol, "LEARN"))
            dyn = db_cursor.fetchone()

   
    #for row in rows:
    #  #print row[0]
    #  if (row[0] == sitename) or re.search('.*\.'+row[0], sitename):
    #     #print row[1]
    #     if (protocol == row[1]) or (row[1] == '*') :
    #        #print row[2]
    #        if row[2] == "DENY" :
    #           return redirect(sitename,protocol,url)+metainfo
    #        elif row[2] == "ALLOW" :
    #           break
 

   #newurl = urlparse.urlunparse((scheme,host,path,parameters,query,fragment))
   #return " ".join((newurl,src_address,ident,method,dash))
   return " "


