# ProXimus

<img src="https://github.com/fiveoclock/proximus/raw/master/proximus-redirector/srv/www/proximus/img/logo.png" />

ProXimus is an enterprise scale solution to manage access control for the Squid
proxy server http://www.squid-cache.org/. It offers a web-based management 
interface to easily configure access rules for users. It is integrated into 
Squid as a redirector program.

[[https://github.com/fiveoclock/fiveoclock.github.com/raw/master/proximus/images/screenie.png|frame]]


## Features
ProXimus offers the following:

**Access Rules....**

* ... can be configured globally (so they are valid for every user)
* ... can be assigned to locations and groups (each user is assigned to a location; additionally it can also be member of a group)
* ... do have priorities (the rule with the highest priority wins)
* ... can have defined times in which they are valid (e.g. allow surfing during lunch break from 12 to 1pm)
* ... can be "Noauth-Rules" (means: sites where no authentication is required)
* ... can be dynamically added / learned as the user requests it **beta** 
* ... can trigger eMails being sent to the User and Admin if access is denied

**Enterprise ready...**

* example scripts are provided to sync users from the Active Directory to the Proximus user database
* Proximus is highly scale-able (at my company it runs on about 40 proxy servers around the world)

**Administration....**

* multiple administrative accounts
* Admins can be Global-Admins (allowed to change everything)
* ... or Location-Admin (only allowed to change rules within on or more locations)


## More information

For more information visit:

* the homepage - http://proximus.5-o-clock.net
* the wiki - https://github.com/fiveoclock/proximus/wiki


## Contributor list

ProXimus was mainly written by 
* Ivan Samarin
* Alexander Ganster

If you want to help develop ProXimmus get in contact with us over Github.


## Licensing

See COPYING for license info

