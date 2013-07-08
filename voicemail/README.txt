voicemail README
==================

Getting Started
---------------

- cd <directory containing this file>

- create the voicemail database
- make sure you create a user and assign password in mysql
- mysql -u <user> -p voicemail < ../db/voicemaildb/dmp
- Change development.ini to have the correct sqlalchemy_url for the db

- $venv/bin/pserve development.ini

