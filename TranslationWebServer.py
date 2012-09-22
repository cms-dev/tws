#!/usr/bin/python
# -*- coding: utf-8 -*-

# Translation Web Server
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
import os.path
import simplejson as json
import base64
from datetime import datetime
from tornado.web import HTTPError, Application, RequestHandler, StaticFileHandler, authenticated, asynchronous
from tornado.ioloop import IOLoop

from Teams import teams as team_names
from Langs import langs as lang_names
from Teams2Langs import teams_to_langs
from Langs2Teams import langs_to_teams
from Logger import logger


teams = dict()
tasks = dict()


def init():
    # Load teams and tasks from disk

    teams_path = os.path.join(os.path.dirname(__file__), "teams")
    for f_name in os.listdir(teams_path):
        if f_name.endswith(".json"):
            name = f_name[:-5]
            path = os.path.join(teams_path, f_name)
            try:
                teams[name] = json.load(open(path))
            except IOError:
                logger.error("Couldn't read data for team %s" % name)
            except ValueError:
                logger.error("Couldn't load data for team %s" % name)

    tasks_path = os.path.join(os.path.dirname(__file__), "tasks")
    for f_name in os.listdir(tasks_path):
        if f_name.endswith(".json"):
            name = f_name[:-5]
            path = os.path.join(tasks_path, f_name)
            try:
                tasks[name] = json.load(open(path))
            except IOError:
                logger.error("Couldn't read data for task %s" % name)
            except ValueError:
                logger.error("Couldn't load data for task %s" % name)

    # TODO Notify if some teams are missing or shouldn't be there

    # Add needed structures to teams and tasks

    for team in teams.itervalues():
        team.setdefault("tasks", {})
        team.setdefault("langs", {})
        team.setdefault("selected", [])

    for task in tasks.itervalues():
        task.setdefault("teams", {})
        task.setdefault("langs", {})

init()


class BaseHandler(RequestHandler):
    """Base RequestHandler for this application.

    """
    def get_current_user(self):
        """Gets the current user logged in from the cookies

        """
        return self.get_secure_cookie("login")


class MainHandler(BaseHandler):
    """Home page handler.

    """
    def get(self):
        team = self.current_user

        self.render("overview.html",
                    global_team=team,
                    global_teams=teams, global_tasks=tasks,
                    lang_names=lang_names, team_names=team_names,
                    teams_to_langs=teams_to_langs,
                    login_error=bool(self.get_argument("login_error", "")))


class LoginHandler(BaseHandler):
    """Login handler

    """
    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")

        if username not in teams:
            logger.warn("Wrong username (%s / %s)." % (username, password))
            self.redirect("/?login_error=1")
            return

        if teams[username]["password"] != password:
            logger.warn("Wrong password (%s / %s)." % (username, password))
            self.redirect("/?login_error=1")
            return

        self.set_secure_cookie("login", username, expires_days=None)
        self.redirect("/")


class LogoutHandler(BaseHandler):
    """Logout handler

    """
    def get(self):
        self.clear_cookie("login")
        self.redirect("/")


class MessageProxy(object):
    def __init__(self):
        self.clients = list()

        # We keep a buffer of sent messages, to send them to the clients
        # that temporarily lose the connection, to avoid them missing
        # any data.
        self.buffer = list()

        # The "age" of the buffers is the minimum time such that we are
        # sure to have all events that happened after that time.
        self.age = time.time()

    def send(self, event, data, target):
        timestamp = time.time()
        message = 'id: %0.6f\n' \
                  'event: %s\n' \
                  'data: %s\n' \
                  '\n' % (timestamp, event, data)
        for client in self.clients:
            client(message, target)
        self.buffer.append((timestamp, message))

    def add_callback(self, callback):
        self.clients.append(callback)

    def remove_callback(self, callback):
        self.clients.remove(callback)

proxy = MessageProxy()


class EventHandler(BaseHandler):
    @authenticated
    @asynchronous
    def get(self):
        self.set_status(200)
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.flush()

        # This is only needed to make Firefox fire the 'open' event on
        # the EventSource object.
        self.write(':\n')
        self.flush()

        # The EventSource polyfill will only deliver events once the
        # connection has been closed, so we have to finish the request
        # right after the first message has been sent. This custom
        # header allows us to identify the request from the polyfill.
        self.one_shot = False
        if 'X-Requested-With' in self.request.headers and \
                self.request.headers['X-Requested-With'] == 'XMLHttpRequest':
            self.one_shot = True

        # We get the ID of the last event the client received. We
        # assume that if the header is missing the client didn't
        # receive any event. In that case we send the entire history
        # (well, not really, but we try to achieve the same effect).
        if "Last-Event-ID" in self.request.headers:
            last_id = float(self.request.headers.get_list("Last-Event-ID")[-1])
        else:
            last_id = None

        self.outdated = False
        if last_id is not None and last_id < proxy.age:
            self.outdated = True
            # The reload event will tell the client that we can't update
            # its data using buffered event and that it'll need to init
            # it again from scratch (in pratice: reload the page).
            self.write("event: reload\n")
            self.write("data: _\n\n")
            # We're keeping the connection open because we want the
            # client to close it. If we'd close it the client (i.e. the
            # browser) may automatically attempt to reconnect before
            # having processed the event we sent it.
            if self.one_shot:
                self.finish()
            else:
                self.flush()
            return

        if last_id is None:
            timestamp = time.time()
            for task in tasks:
                for lang in tasks[task]["langs"]:
                    for team in tasks[task]["langs"][lang]:
                        self.send("id: %0.6f\n" \
                                  "event: create\n" \
                                  "data: %s %s %s\n" \
                                  "\n" % (timestamp, team, lang, task), '*')
            for s in teams[self.current_user]["selected"]:
                self.send("id: %0.6f\n" \
                          "event: select\n" \
                          "data: %s %s %s\n" \
                          "\n" % (timestamp, s[0], s[1], s[2]), '*')
        else:
            for t, msg in proxy.buffer:
                if t > last_id:
                    self.send(msg, '*')

        proxy.add_callback(self.send)

        # FIXME put the timeout (i.e. 600) in a better location
        self.timeout = IOLoop.instance().add_timeout(
            time.time() + 600, self.finish)


    # If the connection is closed by the client then the "on_connection_
    # _close" callback is called. If we decide to finish the request (by
    # calling the finish() method) then the "on_finish" callback gets
    # called (and "on_connection_close" *won't* be called!).

    def on_connection_close(self):
        if not self.outdated:
            proxy.remove_callback(self.send)
            IOLoop.instance().remove_timeout(self.timeout)

    def on_finish(self):
        if not self.outdated:
            proxy.remove_callback(self.send)
            IOLoop.instance().remove_timeout(self.timeout)

    def send(self, message, target):
        if target == '*' or target == self.current_user:
            self.write(message)
            if self.one_shot:
                self.finish()
            else:
                self.flush()


class TranslationHandler(StaticFileHandler):
    def get_current_user(self):
        return self.get_secure_cookie("login")


    def initialize(self):
        StaticFileHandler.initialize(self, os.path.join(os.path.dirname(__file__), "data"))


    def head(self, team, lang, task):
        path = os.path.join(task, "by_team", "%s (%s).pdf" % (team, lang))

        self.set_header("Content-Disposition", "attachment; filename=\"%s (%s, %s).pdf\"" % (task, lang, team))

        StaticFileHandler.get(self, path, include_body=False)


    def get(self, team, lang, task):
        path = os.path.join(task, "by_team", "%s (%s).pdf" % (team, lang))

        self.set_header("Content-Disposition", "attachment; filename=\"%s (%s, %s).pdf\"" % (task, lang, team))

        StaticFileHandler.get(self, path)


    @authenticated
    def post(self, team, lang, task):
        if team != self.current_user:
            logger.warn("Team %s said to be %s while uploading translation of %s in %s." % (self.current_user, team, task, lang))
            raise HTTPError(403)

        if lang not in lang_names:
            raise HTTPError(404)

        if task not in tasks:
            raise HTTPError(404)

        if lang in teams[team]["tasks"].get(task, []):
            raise HTTPError(405)

        self._save(team, lang, task)

        proxy.send("create", "%s %s %s" % (team, lang, task), '*')


    @authenticated
    def put(self, team, lang, task):
        if team != self.current_user:
            logger.warn("Team %s said to be %s while uploading translation of %s in %s." % (self.current_user, team, task, lang))
            raise HTTPError(403)

        if lang not in teams[team]["tasks"].get(task, []):
            raise HTTPError(404)

        self._save(team, lang, task)

        proxy.send("update", "%s %s %s" % (team, lang, task), '*')


    def _save(self, team, lang, task):
        timestamp = datetime.now()

        logger.info("Team %s uploaded translation of task %s into %s" % (team, task, lang))

        # Try immediately to save the file in the history

        path = os.path.join(os.path.dirname(__file__), "history",
                            "%s %s %s %s.pdf" % (timestamp, team, task, lang))

        try:
            open(path, "wb").write(self.request.body)
        except IOError:
            logger.error("Couldn't save translation of task %s into %s, made by %s, in the history." % (task, lang, team))
            raise HTTPError(500)


        # Update the task and team data

        task_path = os.path.join(os.path.dirname(__file__),
                                 "tasks", "%s.json" % task)

        tasks[task]["teams"][team] = sorted(set(tasks[task]["teams"].get(team, []) + [lang]))
        tasks[task]["langs"][lang] = sorted(set(tasks[task]["langs"].get(lang, []) + [team]))

        try:
            json.dump(tasks[task], open(task_path, "w"), indent=4)
        except IOError:
            logger.error("Couldn't write data for task %s" % task)
            raise HTTPError(500)
        except ValueError:
            logger.error("Couldn't dump data for task %s" % task)
            raise HTTPError(500)

        team_path = os.path.join(os.path.dirname(__file__),
                                 "teams", "%s.json" % team)

        teams[team]["tasks"][task] = sorted(set(teams[team]["tasks"].get(task, []) + [lang]))
        teams[team]["langs"][lang] = sorted(set(teams[team]["langs"].get(lang, []) + [task]))

        try:
            json.dump(teams[team], open(team_path, "w"), indent=4)
        except IOError:
            logger.error("Couldn't write data for team %s" % team)
            raise HTTPError(500)
        except ValueError:
            logger.error("Couldn't dump data for team %s" % team)
            raise HTTPError(500)


        # Make some symlinks to easily access this version of the file

        links = [os.path.join(os.path.dirname(__file__),
                              "data", task, "by_lang", "%s (%s).pdf" % (lang, team)),
                 os.path.join(os.path.dirname(__file__),
                              "data", task, "by_team", "%s (%s).pdf" % (team, lang))]

        for link in links:
            try:
                os.makedirs(os.path.dirname(link))
            except OSError:
                pass  # dir already exists

            try:
                os.remove(link)
            except OSError:
                pass  # file doesn't exist yet

            os.symlink(os.path.relpath(path, os.path.dirname(link)), link)


    @authenticated
    def delete(self, team, lang, task):
        if team != self.current_user:
            logger.warn("Team %s said to be %s while deleting translation of %s in %s." % (self.current_user, team, task, lang))
            raise HTTPError(403)

        if lang not in teams[team]["tasks"].get(task, []):
            raise HTTPError(404)

        logger.info("Team %s deleted translation of task %s into %s" % (team, task, lang))

        # Update the task and team data

        task_path = os.path.join(os.path.dirname(__file__),
                                 "tasks", "%s.json" % task)

        tasks[task]["teams"][team].remove(lang)
        tasks[task]["langs"][lang].remove(team)

        try:
            json.dump(tasks[task], open(task_path, "w"), indent=4)
        except IOError:
            logger.error("Couldn't write data for task %s" % task)
            raise HTTPError(500)
        except ValueError:
            logger.error("Couldn't dump data for task %s" % task)
            raise HTTPError(500)

        team_path = os.path.join(os.path.dirname(__file__),
                                 "teams", "%s.json" % team)

        teams[team]["tasks"][task].remove(lang)
        teams[team]["langs"][lang].remove(task)

        try:
            json.dump(teams[team], open(team_path, "w"), indent=4)
        except IOError:
            logger.error("Couldn't write data for team %s" % team)
            raise HTTPError(500)
        except ValueError:
            logger.error("Couldn't dump data for team %s" % team)
            raise HTTPError(500)


        # Remove the symlinks

        links = [os.path.join(os.path.dirname(__file__),
                              "data", task, "by_lang", "%s (%s).pdf" % (lang, team)),
                 os.path.join(os.path.dirname(__file__),
                              "data", task, "by_team", "%s (%s).pdf" % (team, lang))]

        for link in links:
            os.remove(link)

        proxy.send("delete", "%s %s %s" % (team, lang, task), '*')


class SelectionHandler(BaseHandler):
    @authenticated
    def put(self, team, lang, task):
        logger.info("Team %s selected %s %s %s" % (self.current_user, lang, task, team))

        path = os.path.join(os.path.dirname(__file__),
                            "teams", "%s.json" % self.current_user)

        if [team, lang, task] not in teams[self.current_user]["selected"]:
            teams[self.current_user]["selected"].append([team, lang, task])

        try:
            json.dump(teams[self.current_user], open(path, "w"), indent=4)
        except IOError:
            logger.error("Couldn't write data for team %s" % team)
            raise HTTPError(500)
        except ValueError:
            logger.error("Couldn't dump data for team %s" % team)
            raise HTTPError(500)

        proxy.send("select", "%s %s %s" % (team, lang, task), self.current_user)


    @authenticated
    def delete(self, team, lang, task):
        logger.info("Team %s unselected %s %s %s" % (self.current_user, lang, task, team))

        path = os.path.join(os.path.dirname(__file__),
                            "teams", "%s.json" % self.current_user)

        if [team, lang, task] in teams[self.current_user]["selected"]:
            teams[self.current_user]["selected"].remove([team, lang, task])

        try:
            json.dump(teams[self.current_user], open(path, "w"), indent=4)
        except IOError:
            logger.error("Couldn't write data for team %s" % team)
            raise HTTPError(500)
        except ValueError:
            logger.error("Couldn't dump data for team %s" % team)
            raise HTTPError(500)

        proxy.send("unselect", "%s %s %s" % (team, lang, task), self.current_user)


class ImageHandler(RequestHandler):
    formats = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp'
    }

    def initialize(self, location, fallback):
        self.location = location
        self.fallback = fallback

    def get(self, *args):
        self.location %= tuple(args)

        for ext, filetype in self.formats.iteritems():
            if os.path.isfile(self.location + '.' + ext):
                self.serve(self.location + '.' + ext, filetype)
                return

        self.serve(self.fallback, 'image/png')  # FIXME hardcoded type

    def serve(self, path, filetype):
        self.set_header("Content-Type", filetype)

        modified = datetime.utcfromtimestamp(int(os.path.getmtime(path)))
        self.set_header('Last-Modified', modified)

        # TODO check for If-Modified-Since and If-None-Match

        with open(path, 'rb') as data:
            self.write(data.read())


def main():
    application = Application([
        (r"/", MainHandler),
        (r"/login", LoginHandler),
        (r"/logout", LogoutHandler),
        (r"/events", EventHandler),
        (r"/translations/([A-Za-z0-9_]+)/([A-Za-z0-9_]+)/([A-Za-z0-9_]+)", TranslationHandler),
        (r"/selections/([A-Za-z0-9_]+)/([A-Za-z0-9_]+)/([A-Za-z0-9_]+)", SelectionHandler),
        (r"/flags/([A-Za-z0-9_]+)", ImageHandler, {
            'location': os.path.join(os.path.dirname(__file__), 'flags', '%s'),
            'fallback': os.path.join(os.path.dirname(__file__), 'static', 'flag.png')
        }),
        ], **{
        "login_url": "/",
        "template_path": os.path.join(os.path.dirname(__file__), "templates"),
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
        "cookie_secret": base64.b64encode("000000000000000000000"),
        })
    application.listen(8891)

    try:
        IOLoop.instance().start()
    except KeyboardInterrupt:
        # Exit cleanly.
        return

if __name__ == "__main__":
    main()
