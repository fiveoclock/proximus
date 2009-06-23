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

proxy = ""
location = ""
redirection_method = ""
user_email = ""
email_admin = ""

def log(s):
    f = open("/var/log/squid/redirector_class.log","a")
    f.write(s+'\n')
    f.close()

# called when a site is blocked
def deny(sitename,protocol):
   if protocol == "ssl" :
      ddddd = ""
   else:
      ddddd = ""
      
   #return urlparse.urlunparse((scheme,host,path,parameters,query,fragment))
   #return "302:http://10.1.128.231"
   #return "302:http://10.1.128.231/forbidden.html"
   return "302:http://%s/forbidden.html" % ( proxy )

# called when a request is redirected
def redirect(sitename,protocol,url,user_id,src_address,loc_id):
   sitename_sav = re.sub("^www\.", "", sitename)

   if protocol == "ssl" :
      if redirection_method == "REDIRECT_HTTP" :
         return "302:http://%s/proximuslog/logs/confirm/site:%s/proto:%s/ip:%s/uid:%s/locid:%s/url:%s" % (proxy, sitename_sav, protocol, src_address, user_id, loc_id, base64.b64encode("https://"+sitename))
      
      elif redirection_method == "REDIRECT_SSL" :
         # the webserver there can read the requested host + requested uri and redirect to proximuslog 
         return "srv-vie-wtrash.vie.mm-karton.com:443"
 
      elif redirection_method == "REDIRECT_SSL_MAIL" :
         smtp = smtplib.SMTP("localhost")
         email_admin = "root@mm-karton.com"


         msg = MIMEText("Dear User! \n\nYour request to https://"+sitename+" has been blocked. \n\nIf you need access to this page please contact your Administrator.\n\nProXimus")

         # You can use add_header or set headers directly ...
         msg['Subject'] = 'Site '+sitename+' has been blocked'
         # Following headers are useful to show the email correctly
         # in your recipient's email box, and to avoid being marked
         # as spam. They are NOT essential to the snemail call later
         msg['From'] = "ProXimus"
#         msg['Reply-to'] = 
         msg['To'] = user_email

         #smtp.sendmail(email_admin, user_email, msg.as_string())
         smtp.sendmail("root@mm-karton.com", user_email, msg.as_string())
         smtp.close()

         return "302:http://%s/proximuslog/logs/confirm/site:%s/proto:%s/ip:%s/uid:%s/locid:%s/url:%s" % (proxy, sitename_sav, protocol, src_address, user_id, loc_id, base64.b64encode("https://"+sitename))
      
      elif redirection_method == "REDIRECT_SSL_GEN" :
         # generate a SSL certificate on the fly and present it to the requesting browser
         # not implemented yet
         return "srv-vie-wtrash.vie.mm-karton.com:443"
      
      else :
         #default
         return "302:http://%s/proximuslog/logs/confirm/site:%s/proto:%s/ip:%s/uid:%s/locid:%s/url:%s" % (proxy, sitename_sav, protocol, src_address, user_id, loc_id, base64.b64encode("https://"+sitename))

   else:
      #sitename_sav = re.sub("^www.", "", sitename)
      return "302:http://%s/proximuslog/logs/confirm/site:%s/proto:%s/ip:%s/uid:%s/locid:%s/url:%s" % (proxy, sitename_sav, protocol, src_address, user_id, loc_id, base64.b64encode(url))



#return "302:http://%s/proximuslog/logs/confirm/site:%s/proto:%s/ip:%s/uid:%s/locid:%s/url:%s" % (proxy, sitename_sav, protocol, src_address, user_id, loc_id, base64.urlsafe_b64encode(url))


def check_request(db_cursor, redirection_host, location_id, line):
   url,src_address,ident,method,dash=string.split(line)
   # scheme://host/path;parameters?query#fragment
   (scheme,host,path,parameters,query,fragment) = uparse(url)
   metainfo = " ".join(("",src_address,ident,method,dash))

   global proxy, location, redirection_method, user_email
   
   proxy = redirection_host
   location = location_id

   # remove "/-" from source ip address
   src_address = re.sub("/.*", "", src_address)

   if method == "CONNECT" :
      """it's ssl"""
      protocol = "ssl"
      sitename = scheme
      siteport = path
   else:
      """it' http"""
      protocol = "http"
      sitename = host.split(":", 1)[0]
      try: 
         siteport = host.split(":", 1)[1]
      except IndexError,e:
         siteport = "80"


   # make all vars lowercase to make sure they match
   #sitename = escape(sitename)
   #ident = escape(ident.lower())
   ident = ident.lower()
   #src_address = escape(src_address)

   # allow access to to proximuslog website
   if sitename == proxy : 
      return ""
   

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
                              protocol = '*' )", (sitename, sitename, protocol) )
   #print "SELECT sitename, siteport, description FROM rules WHERE globalflag = 1 AND sitename = %s OR sitename LIKE %s" % (sitename, '%'+sitename) 
   rows = db_cursor.fetchall()
   for row in rows:
      return deny(sitename,protocol)
     
   
   #
   # check if host is blocked by location or group
   #
   # first get users loccations.id and groups.id - makes the second query a lot easier to understand
   try:
      db_cursor.execute ("SELECT id, group_id, location_id, emailaddress FROM users WHERE username = %s", ident)
      row = db_cursor.fetchone()
      user_id = row[0]
      user_loc_id = row[2]
      user_group_id = row[1]
      user_email = row[3].rstrip('\n')
   except TypeError:
      # user not found in database redirect to default site
      user_group_id = None
      return deny(sitename,protocol)
      
   # check if the user is in a valid group (group_id 0 means no group)
   if (user_group_id != None) and (user_group_id != 0) :
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
                           ORDER BY priority DESC, location_id", (user_group_id, user_loc_id, sitename, sitename, protocol))
   else :
      #print "if none"
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
                           ORDER BY priority DESC, location_id", (user_loc_id, sitename, sitename, protocol))
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
                           ", (user_id, protocol, sitename, sitename))
         dyn = db_cursor.fetchone()
         if (dyn == None) :
            return redirect(sitename,protocol,url,user_id,src_address,user_loc_id)
         else :
            break
         return redirect(sitename,protocol,url,user_id,src_address,user_loc_id)
      elif row[2] == "DENY" :
         return deny(sitename,protocol)
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


