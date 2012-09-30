Translation Web Server
======================


Introduction
------------

TWS, short for Translation Web Server, is a simple web server (and web
application) that has been created to help with the task translation
process at the 24th International Olympiad in Informatics (Italy 2012).

Its aim is to provide an interface for team leaders to upload their
translation of a task statement, to download the translations made by
other teams and to select the translations that will be highlighted to
the contestants of their team. On the Scientific Committee side this
system allows to easily collect all translations and to automatically
insert them into the contest management system, even at a later time.


Dependencies
------------

To run this software you need a Python interpreter, the Tornado web
server and a few other libraries. On Ubuntu they're provided by the
following packages:

- python >= 2.7 (and < 3.0);

- python-tornado >= 2.0;

- python-simplejson >= 2.1;


Configuration
-------------

Add JSON files in the `tasks` directory describing the tasks you want
to translate. See the `ioi2012_day1` and `ioi2012_day2` branches for
some examples.

To add, modify or remove a team please take a look at `Teams.py`,
`Teams2Langs.py`, `Langs2Teams.py` and the files in the `teams` and
`flags` directories.


Installation
------------

There's no installation script for TWS. It's reccomended to run it from
the directory it resides in, by running:

    ./TranslationWebServer.py


Exporting to CMS
----------------

Once you're done with collecting translations you can export them to
CMS by using the `export_to_CMS.py` script.
