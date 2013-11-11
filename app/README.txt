Asterisk and Twisted installation instructions.

This application is build using the latest release of asterisk version 1.8.  There are no special
functions or features used that prevent this from operating with higher versions, but this has not
been tested with asterisk 1.6 or older.

All development should continue to use asterisk 1.8.

Install asterisk from source: http://downloads.asterisk.org/pub/telephony/certified-asterisk/certified-asterisk-1.8.15-current.tar.gz

Install twisted (version 13 or later) using either the OS package manager (i.e. yum, apt-get, etc.) or via easy_install or pip.

Install starpy using easy_install or pip

For asterisk, you will need a test dial plan, I use the following:

--------------
;autofallthrough=no
;
;
clearglobalvars=no
;
;
[globals]

;
; Sample entries for extensions.conf
;
;
[from-sip]

exten => 5555,1,MusicOnHold()
exten => 5555,n,Hangup

exten => _99XX.,1,Wait(1)
exten => _99XX.,n,Answer()
exten => _99XX.,n,AGI(agi://localhost:4537/leaveMessage,12345,abc,xyz)
exten => _99XX.,n,Verbose(1,Back from AGI call)
exten => _99XX.,n,Hangup
---------------


register a sip phone (x-lite http://www.counterpath.com/x-lite.html works well.) with
asterisk and dial 99 and any 2 additional digits to access the leaveMessage call flow.

here is my sip.conf phone entry that allows my soft phone to access the dialplan above:

----------------
[1111] (natted-phone,ulaw-phone)
        type = friend
        context = from-sip
        dtmfmode = auto
        host = dynamic
        directmedia = no
        disallow = all
        allow = ulaw
        secret = 888888
        mailbox = 1111
-----------------

you would just add additional dialplan functionality for the new call flows.  Both of my extensions.conf
as well as sip.conf are in the repository for this in the asterisk section.

in the app, the etc/flexvmail.conf configures all the asterisk related ip and port informaiton for
connecting to asterisk from the twisted application.

you will also need to make sure you manager.conf asterisk file matches the credentials in the app's
configuration file.  See example manager.conf file in this repository.

once everything is installed, you just need to run bin/flexvmail start  to start the twisted app.
Asterisk will need to be running as well.  If it is not, the twisted app will attempt to reconnect
every 60 seconds.


all log statements (I use debug level logging while developing and testing to debug twisted), are in
the log/flexvmail.log file (created by the app.  you may need to manually create the log directory -
at the same level as the applications etc, bin, flexvmail, and run directories)



