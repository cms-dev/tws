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

import sys
import os
import os.path
import json
import re

from ioi_to_iso2 import ioi_to_iso2
from Teams import teams
from Langs import langs

from cms.db.SQLAlchemyAll import Session, Contest, Statement
from cms.db.FileCacher import FileCacher

official_team = "HSC"

def run(contest_id):
    session = Session()
    contest = Contest.get_from_id(contest_id, session)

    task_by_team = set()
    task_by_lang = set()

    task_dir = os.path.join(os.path.dirname(__file__), "tasks")

    for t in os.listdir(task_dir):
        if t.endswith('.json'):
            task = t[:-5]
            task_path = os.path.join(task_dir, t)
            with open(task_path) as task_file:
                data = json.load(task_file)
                if "teams" in data:
                    for team, v in data["teams"].iteritems():
                        for lang in v:
                            task_by_team.add((task, lang, team))
                if "langs" in data:
                    for lang, v in data["langs"].iteritems():
                        for team in v:
                            task_by_lang.add((task, lang, team))

    if task_by_team != task_by_lang:
        print "ERROR: inconsistent data in task files"
        print repr(task_by_team - task_by_lang)
        print repr(task_by_lang - task_by_team)
        return

    team_by_task = set()
    team_by_lang = set()

    team_dir = os.path.join(os.path.dirname(__file__), "teams")

    for t in os.listdir(team_dir):
        if t.endswith('.json'):
            team = t[:-5]
            team_path = os.path.join(team_dir, t)
            with open(team_path) as team_file:
                data = json.load(team_file)
                if "tasks" in data:
                    for task, v in data["tasks"].iteritems():
                        for lang in v:
                            team_by_task.add((task, lang, team))
                if "langs" in data:
                    for lang, v in data["langs"].iteritems():
                        for task in v:
                            team_by_lang.add((task, lang, team))

    if team_by_task != team_by_lang:
        print "ERROR: inconsistent data in team files"
        print repr(team_by_task - team_by_lang)
        print repr(team_by_lang - team_by_task)
        return

    if task_by_team != team_by_task:
        print "ERROR: inconsistent data between task and team files"
        print repr(task_by_team - team_by_task)
        print repr(team_by_task - task_by_team)
        return

    data_by_lang = set()
    data_by_team = set()

    data_dir = os.path.join(os.path.dirname(__file__), "data")

    for task in os.listdir(data_dir):
        if os.path.isdir(os.path.join(data_dir, task)):
            for f in os.listdir(os.path.join(data_dir, task, "by_lang")):
                # f == "lang (team).pdf"
                lang, team = re.findall("^([A-Za-z0-9_]+) \(([A-Za-z0-9_]+)\)\.pdf$", f)[0]
                data_by_lang.add((task, lang, team))
            for f in os.listdir(os.path.join(data_dir, task, "by_team")):
                # f == "team (lang).pdf"
                team, lang = re.findall("^([A-Za-z0-9_]+) \(([A-Za-z0-9_]+)\)\.pdf$", f)[0]
                data_by_team.add((task, lang, team))

    if data_by_lang != data_by_team:
        print "ERROR: inconsistent data in data files"
        print repr(data_by_lang - data_by_team)
        print repr(data_by_team - data_by_lang)
        return

    if task_by_team != data_by_lang:
        print "ERROR: inconsistent data between json and data files"
        print repr(task_by_team - data_by_lang)
        print repr(data_by_lang - task_by_team)
        return


    translations = task_by_team

    print "Hooray! Data is consistent!"


    translation_map = dict()

    for t in os.listdir(task_dir):
        if t.endswith('.json'):
            task = t[:-5]
            task_path = os.path.join(task_dir, t)
            with open(task_path) as task_file:
                data = json.load(task_file)
                if "langs" in data:
                    for lang, v in data["langs"].iteritems():
                        if len(v) == 0:
                            pass
                        elif len(v) == 1 and v[0] != official_team:
                            for team in v:
                                translation_map[(task, lang, team)] = "%s" % lang
                        else:
                            for team in v:
                                translation_map[(task, lang, team)] = "%s_%s" % (lang, ioi_to_iso2[team])


    tasks = set(task for task, lang, team in translations)

    task_map = dict((task, contest.get_task(task)) for task in tasks)


    file_cacher = FileCacher()

    for task, lang, team in translations:
        if team == official_team:
            assert lang == "en"
            digest = file_cacher.put_file(
                        path=os.path.join(data_dir, task, "by_lang", "%s (%s).pdf" % (lang, team)),
                        description="Statement for task %s" % task)
        else:
            digest = file_cacher.put_file(
                        path=os.path.join(data_dir, task, "by_lang", "%s (%s).pdf" % (lang, team)),
                        description="Statement for task %s, translated into %s (%s) by %s (%s)" %
                            (task, langs[lang], lang, teams[team], team))

        s = Statement(digest, translation_map[(task, lang, team)], task_map[task])

        session.add(s)
        translation_map[(task, lang, team)] = s

    session.commit()

    # FIXME doesn't seem to work
    for task, lang, team in translations:
        if team == official_team:
            task_map[task].official_statement = translation_map[(task, lang, team)].language

        translation_map[(task, lang, team)] = translation_map[(task, lang, team)].id

    session.commit()

    print "Translations stored!"


    for t in os.listdir(team_dir):
        if t.endswith('.json'):
            team = t[:-5]
            team_path = os.path.join(team_dir, t)
            with open(team_path) as team_file:
                data = json.load(team_file)
                if "selected" in data:
                    selected = list(str(translation_map[tuple(reversed(x))]) for x in data["selected"])
                    selected.extend(str(v) for k, v in translation_map.iteritems() if k[2] in [official_team, team])
                    selected = sorted(set(selected))
                    session.execute("UPDATE users SET statements = '{%s}' WHERE username LIKE '%s%%';" % (','.join(selected), team))

    session.commit()

    print "Selections stored!"

    print "ALL DONE"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Usage: %s contest_id" % sys.argv[0]
    else:
        run(int(sys.argv[1]))
