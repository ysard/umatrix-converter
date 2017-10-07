# -*- coding: utf-8 -*-
# MIT License
#
# Copyright (c) 2017 Ysard
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Standard imports
import re
from collections import defaultdict
import abc

# Custom imports
import database as db


class ConfigParser(abc.ABC):
    """Basic class that can handle dump files from various addons"""

    def __init__(self):
        self._content = defaultdict(set)

    def sections(self):
        return self._content.keys()

    def section(self, name):
        return self._content.get(name, dict())

    @property
    def content(self):
        return self._content

    @abc.abstractclassmethod
    def read_file(self, filepath):
        """Open an export file"""
        return


class RequestPolicyParser(ConfigParser):
    """Parser of RequestPolicy export"""

    def read_file(self, filepath):
        """Open RequestPolicy export

        .. note:: 2 sections: 'UKN', 'origins-to-destinations', 'destinations'
            & 'origins'
        """

        section_pattern = re.compile('\[(.*)\]')

        with open(filepath, 'r') as fd:

            section = 'UKN'

            for line in fd:
                line = line.rstrip('\n')

                m = section_pattern.match(line)

                # Detect sections
                if m is not None:
                    section = m.group(1)
                    continue

                # Detect origin => destination pattern
                if '|' in line:
                    self._content[section].add(tuple(line.split('|')))
                else:

                    self._content[section].add(line)


class NoScriptParser(ConfigParser):
    """Parser of NoScript export"""

    def read_file(self, filepath):
        """Open NoScript export

        .. note:: 2 sections: 'UKN' & 'UNTRUSTED'
        """

        section_pattern = re.compile('\[(.*)\]')
        # Remove http://, https://, about:blank urls
        protocol_pattern = re.compile('(https?://)?([^:]*$)')

        with open(filepath, 'r') as fd:

            section = 'UKN'

            for line in fd:
                line = line.rstrip('\n')

                m = section_pattern.match(line)

                # Detect sections
                if m is not None:
                    section = m.group(1)
                    continue

                # Insert hosts
                m = protocol_pattern.match(line)
                if m is not None:
                    # print(m.groups())
                    self._content[section].add(m.group(2))


class FirefoxPermissionsParser(ConfigParser):
    """Parser of Cookie Monster/Firefox export

    .. note:: Since Cookie Monster is a wrapper of Firefox features, we need
        to get data from permissions.sqlite.

        In 'moz_perms' table we need to retrieve:
            - type: cookie
            - permission:
                1: Autoriser, 2: Bloquer, 8: Autoriser pour la session
    """

    def read_file(self, filepath):
        """Open permisssions.sqlite & set content variable.

        .. note:: 2 sections: 'allow' & 'block'
        """

        # Initialize database
        with db.SQLA_Wrapper(db_file=filepath) as session:

            # Query
            res = session.execute(
                'SELECT origin, permission '
                'FROM moz_perms '
                'WHERE type == \'cookie\''
            )

            # Remove http://, https://, about:blank urls
            protocol_pattern = re.compile('(https?://)?([^:]*$)')

            for origin, permission in res:

                m = protocol_pattern.match(origin)
                if m is None:
                    # Unknown host
                    continue

                # Allow
                if permission == 1:
                    self._content['allow'].add(m.group(2))

                # Block/Allow for the session
                elif permission == 8 or permission == 2:
                    self._content['block'].add(m.group(2))


def request_policy_converter(request_policy_parser, output_filepath,
                             advanced=False):
    """Convert and write content of RequestPolicy to uMatrix rules file.

    types of requests for uMatrix:
        xhr, frame, cookie, media, image, css, script
    actions for uMatrix:
        allow, block

    .. note:: If advanced is False, all rules allow all types of requests.
        ex:
            'origins-to-destinations': origin destination * allow
            'destinations': * destination * allow
            'origins': origin * * allow

        If advanced is True, rules are more restricted.
        ex:
            'origins-to-destinations': origin destination [xhr, script] allow
            'destinations': * destination xhr allow
            'origins': None

    """

    with open(output_filepath, 'a') as fd:

        # Origin => Destination
        section = request_policy_parser.section('origins-to-destinations')

        for ori, dest in section:

            if advanced:
                fd.write("{} {} xhr allow\n".format(ori, dest))
                fd.write("{} {} script allow\n".format(ori, dest))
            else:
                fd.write("{} {} * allow\n".format(ori, dest))


        # Destinations
        section = request_policy_parser.section('destinations')

        for dest in section:
            if advanced:
                fd.write("* {} xhr allow\n".format(dest))
#                fd.write("* {} script allow\n".format(dest))
            else:
                fd.write("* {} * allow\n".format(dest))


        # Origins
        section = request_policy_parser.section('origins')

        for ori in section:
            if advanced:
                pass
#                fd.write("{} * xhr allow\n".format(ori))
#                fd.write("{} * script allow\n".format(ori))
            else:
                fd.write("{} * * allow\n".format(ori))


def noscript_converter(noscript_parser, output_filepath, **kwargs):
    """Convert and write content of NoScript to uMatrix rules file.

    types of requests for uMatrix:
        script
    actions for uMatrix:
        allow, block

    .. note:: Basic rules of NoScript are 'allow' rules, others are explicitly
        'block' rules.
    """

    with open(output_filepath, 'a') as fd:

        # UKN (allow)
        section = noscript_parser.section('UKN')

        for host in section:
            fd.write("{} {} script allow\n".format(host, host))

        # UNTRUSTED (block)
        section = noscript_parser.section('UNTRUSTED')

        for host in section:
            fd.write("* {} script block\n".format(host))


def cookie_monster_converter(firefox_permissions_parser, output_filepath,
                             **kwargs):
    """Convert and write content of Firefox permissions to uMatrix rules file.

    types of requests for uMatrix:
        cookie
    actions for uMatrix:
        allow, block

    .. note:: 'Authorized for the session' rules are converted to 'block' rules.
    """

    with open(output_filepath, 'a') as fd:

        # allow
        for section, content in firefox_permissions_parser.content.items():

            for host in content:
                fd.write("{} * cookie {}\n".format(host, section))



if __name__ == "__main__":

    import os
    os.remove('data/uMatrix-rules.txt')

    config = FirefoxPermissionsParser()
    config.read_file('data/permissions.sqlite')
    cookie_monster_converter(config, 'data/uMatrix-rules.txt')

    config = RequestPolicyParser()
    config.read_file('data/requestpolicy-settings.txt')
    request_policy_converter(config, 'data/uMatrix-rules.txt', advanced=True)

    config = NoScriptParser()
    config.read_file('data/noscript_whitelist_export.txt')
    noscript_converter(config, 'data/uMatrix-rules.txt')

    #print(config.sections())
    #print(config.content())





