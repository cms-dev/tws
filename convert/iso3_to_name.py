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

import os.path
from xml.sax import parse
from xml.sax.handler import ContentHandler

class _make_dict (ContentHandler):
    def __init__ (self, path, key, value, result):
        self.path = path
        self.key = key
        self.value = value
        self.index = 0
        self.result = result

    def startElement (self, name, attrs):
        if self.index < len(self.path) and name == self.path[self.index]:
            self.index += 1
        if self.index == len(self.path):
            if self.key in attrs and self.value in attrs:
                self.result[attrs[self.key]] = attrs[self.value]

    def endElement (self, name):
        if self.index > 0 and name == self.path[self.index-1]:
            self.index -= 1

iso3_to_name = dict()

parse(os.path.join('/', 'usr', 'share', 'xml', 'iso-codes', 'iso_3166.xml'),
      _make_dict(["iso_3166_entries", "iso_3166_entry"],
                "alpha_3_code", "name", iso3_to_name))
