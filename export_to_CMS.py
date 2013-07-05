#!/usr/bin/python2
# -*- coding: utf-8 -*-

# Translation Web Server
# Copyright © 2012-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from convert.ioi_to_iso2 import ioi_to_iso2
from Teams import teams
from Langs import langs

from cms.db.SQLAlchemyAll import Session, Contest, Statement
from cms.db.FileCacher import FileCacher

official_team = "HSC"
ioi_to_iso2[official_team] = "official"

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
        print "ERROR: data in 'tasks' is not self-consistent"
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
        print "ERROR: data in 'teams' is not self-consistent"
        print repr(team_by_task - team_by_lang)
        print repr(team_by_lang - team_by_task)
        return

    if task_by_team != team_by_task:
        print "ERROR: data in 'tasks' and 'teams' is different"
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
        print "ERROR: PDF files in 'data' are not complete"
        print repr(data_by_lang - data_by_team)
        print repr(data_by_team - data_by_lang)
        return

    if task_by_team != data_by_lang:
        print "ERROR: PDF files in 'data' do not match JSON data"
        print repr(task_by_team - data_by_lang)
        print repr(data_by_lang - task_by_team)
        return

    print "Hooray! Data is consistent!"


    # Pick one at random: they're all equal.
    translations = task_by_team

    # Determine language codes used in CMS.
    codes = dict()

    # Read JSON files in 'tasks' again as it provides data already
    # grouped as we need it, and not simply as a list of tuples.
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
                                codes[(task, lang, team)] = "%s" % lang
                        else:
                            for team in v:
                                codes[(task, lang, team)] = "%s_%s" % (lang, ioi_to_iso2[team])

    # Store the files as Statement objects.
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

        s = Statement(codes[(task, lang, team)], digest, task=contest.get_task(task))

        session.add(s)

    session.commit()


    primary = dict()

    # Retrieve the statements selected by each team.
    for t in os.listdir(team_dir):
        if t.endswith('.json'):
            team = t[:-5]
            team_path = os.path.join(team_dir, t)
            with open(team_path) as team_file:
                data = json.load(team_file)

                for team2, lang, task in data.get("selected", []):
                    # A team could have selected a statement that later got removed.
                    if (task, lang, team2) in codes:
                        primary.setdefault(team, {}).setdefault(task, []).append(codes[(task, lang, team2)])

    # Add the ones they uploaded themselves.
    for task, lang, team in translations:
        # Don't worry about duplicates, CWS filters them out.
        primary.setdefault(team, {}).setdefault(task, []).append(codes[(task, lang, team)])

    # Set the primary statements for tasks (i.e. the ones of the official team)
    for task, primary2 in primary.get(official_team, {}).iteritems():
        contest.get_task(task).primary_statements = json.dumps(primary2)

    # Set the primary statements for teams
    for team, primary2 in primary.iteritems():
        session.execute("UPDATE users SET primary_statements = '%s' WHERE username LIKE '%s%%';" % (json.dumps(primary2), team))

    session.commit()

    print "Statements stored in the DB!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Usage: %s contest_id" % sys.argv[0]
    else:
        run(int(sys.argv[1]))
