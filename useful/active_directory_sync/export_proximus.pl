#!/usr/bin/perl
## Proximus Gate Script

# This script will insert all Users which are in the Internet group into a Mysql-Database
# written by vieaga - Alexander Ganster

# v1.2 vieaga 12.04.10 - reduce number of update statements - only update userinformation that has really changed
# v1.1 vieaga - added more debugging + only deactivate users instead of deleting them
# v1.0 vieaga - Modification of Unkis Mailing Script

use DBI;

my $mysql_user = "!!! please set";
my $mysql_pass = "!!! please set";
my $mysql_db   = "!!! please set";
my $mysql_host = "!!! please set";
my $exportAD       = "C:\\tools\\Proxy\\dom_User.dat";

my @locations;
my %locations_hashtable = ();

my $user_insert_count = 0;
my $user_delete_count = 0;
my $user_update_count = 0;
my $user_insert_list;
my $user_delete_list;
my $user_update_list;
my @updated_users;


# Connect to MySQL database
$dbh = DBI->connect("DBI:mysql:". $mysql_db .":". $mysql_host, $mysql_user, $mysql_pass) or dieMsg("No connection to databaser!");
printMsg("Connected to MySQL database.");

# Readin AD export into memory
open(ADDUMP, $exportAD) or dieMsg("Can't read Active Directory export");
@addump = <ADDUMP>;
close(ADDUMP);


# Remove NEW flag from all existing database entries
$dbh->do("UPDATE users SET updated='N'") or dieMsg("Can't do NEWFLAG query");

# Check AD export for new locations and read location IDs into memory
foreach $line (@addump) {  
   my ($loc, $rest) = split(/;/,$line);
   # Check if we've seen location before

   if(!grep (/^$loc$/i, @locations)) {
      # if we haven't seen the location before add it to our array of known locations
      push(@locations, $loc);
      #printMsg("Checking Location: ". $loc);
      
      # Check if it already exists in the database
      if(!checkLoc($loc)) {
         # if not insert it
         insertLoc($loc);
         printMsg("  > Inserted: ". $loc);
      }
   }
}


# Check AD Export for Users
foreach $line (@addump) {
   my ($loc, $username, $realname, $email) = split(/;/,$line);
   # make username lower case
   $username = lc ($username);

   # Check if already exists
   if(!checkUser($username)) {
      # insert user
      insertUser($username, $realname, $email, $locations_hashtable{ $loc } );

      $user_insert_count++;
      $user_insert_list = $user_insert_list . $username . " ";
      #printMsg("User inserted: ". $username);
   }
   else {
      # update user
      updateUser($username, $realname, $email, $locations_hashtable{ $loc } );

      $user_update_count++;
      $user_update_list = $user_update_list . $username . " ";
      #printMsg("User updated: ". $username);
   }
}

# set updated flag for all processed users
#printMsg("update flag is being set for the following users: @updated_users");
#printMsg("UPDATE users SET updated='Y' WHERE username IN (\"". join('","', @updated_users) ."\")");
$dbh->do("UPDATE users SET updated='Y' WHERE username IN (\"". join('","', @updated_users) ."\")") or dieMsg("Can't set flag for updated users");

# Check for user entries which have not been updated during this run...
$userlist = $dbh->prepare("SELECT id, username FROM users WHERE updated<>'Y' AND active='Y'") or dieMsg("Can't prepare LIST query");
$userlist->execute or dieMsg("Can't execute LIST query");

# ... and delete them
while($result = $userlist->fetchrow_hashref) {
   deactivateUser($result->{'username'});
   $user_delete_count++;
   $user_delete_list = $user_delete_list . $result->{'username'} . " ";
   printMsg("User deactivated: ". $result->{'username'});
}
$userlist->finish;

# Print summary
printMsg("Users inserted: ". $user_insert_count ." ".$user_insert_list);
printMsg("Users updated: ". $user_update_count);
printMsg("Users deactivated: ". $user_delete_count ." ".$user_delete_list);
printMsg("Active users in db: ". ($user_insert_count+$user_update_count) );


# close connection
$dbh->disconnect();
printMsg("Disconnect from MySQL database.");





#######################################################
# Here be subroutines
#######################################################

# Checks if the location already exists in the database
sub checkLoc {
   my $loc = shift;

   $chk = $dbh->prepare("SELECT id FROM locations WHERE code LIKE '". $loc ."'") or dieMsg("Can't prepare CHECK query");
   $chk->execute or dieMsg("Can't execute CHECK query");

   if(@result = $chk->fetchrow_array()) {
      $chk->finish;
      $locations_hashtable{ $loc } = $result[0];
      #printMsg("   id: " . $locations_hashtable{ $loc } );
      return 1;
   }      
   else {
      $chk->finish;
      return 0;
   }
}

# Inserts new location into database
sub insertLoc {
   my $loc = shift;

   $insert = $dbh->prepare("INSERT INTO locations (code) VALUES ('". $loc ."')") or dieMsg("Can't prepare INSERT query");
   $insert->execute or dieMsg("Can't execute INSERT query");
}



# Checks if user already exists in database
sub checkUser {
   my $username = shift;

   $chk = $dbh->prepare("SELECT id FROM users WHERE username = '". $username ."'") or dieMsg("Can't prepare CHECK query");
   $chk->execute or dieMsg("Can't execute CHECK query");

   if(@result = $chk->fetchrow_array()) {
      $chk->finish;
      return 1;
   }      
   else {
      $chk->finish;
      return 0;
   }
}

# Inserts user into database
sub insertUser {
   my $username = shift;
   my $realname = shift;
   my $email = shift;
   my $loc = shift;

   $insert = $dbh->prepare("INSERT INTO users (username, realname, emailaddress, location_id, active, updated) VALUES ('$username', \"$realname\", '$email', '$loc', 'Y', 'Y')") or dieMsg("Can't prepare INSERT query");
   $insert->execute or dieMsg("Can't execute INSERT query");
}

# Updates user in database
sub updateUser {
   my $username = shift;
   my $realname = shift;
   my $email = shift;
   my $loc = shift;


   $chk = $dbh->prepare("SELECT id FROM users WHERE 
      username     = \"$username\" AND
      realname     = \"$realname\" AND
      emailaddress = \"$email\" AND
      location_id  = \"$loc\" AND
      active       = \"Y\"
      ") or dieMsg("Can't prepare CHECK query");
   $chk->execute or dieMsg("Can't execute CHECK query");

   if(@result = $chk->fetchrow_array()) {
      $chk->finish;
      # all userdata is up to date - do nothing
      push(@updated_users, $username);
      #print "all ok for user $username\n";
   }
   else {
      $chk->finish;
      # some userdata has changed - update user
      $update = $dbh->prepare("UPDATE users SET realname=\"$realname\", emailaddress='$email', location_id='$loc', updated='Y', active='Y', update_time=NOW() WHERE username='$username'") or dieMsg("Can't prepare INSERT query");
      $update->execute or dieMsg("Can't execute INSERT query");
      print "user $username has changed\n";
   }

}

# Deactivate user from database
sub deactivateUser {
   my $username = shift;

   $delete = $dbh->prepare("UPDATE users SET active='N', updated='Y', update_time=NOW() WHERE username='$username'") or dieMsg("Can't prepare INSERT query");
   $delete->execute or dieMsg("Can't execute deactivate query");
}

# Delete user from database
sub deleteUser {
   my $username = shift;

   $delete = $dbh->prepare("DELETE FROM users WHERE username='$username'") or dieMsg("Can't prepare INSERT query");
   $delete->execute or dieMsg("Can't execute delte query");
}




sub printMsg {
   $msg = shift;

   $date = localtime();
   print $date .": ". $msg ."\n";  
}

sub dieMsg {
   $msg = shift;

   $date = localtime();
   print $date .": ". $msg ."\n";  
   die;
}
