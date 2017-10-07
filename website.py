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
"""
This modules handles flask app
"""

# Standard imports
from flask import Flask, render_template, request, flash, \
    session, send_from_directory
from werkzeug import secure_filename
from sqlalchemy.exc import DatabaseError
import os
import uuid

# Custom imports
import commons as cm
from uMatrix_converter import *

LOGGER = cm.logger()

#static_url_path :
#can be used to specify a different path for the static files on the web.
#Defaults to the name of the static_folder folder.
#static_folder :
#the folder with static files that should be served at static_url_path.
#Defaults to the 'static' folder in the root path of the application.

app = Flask(__name__,
            static_url_path=cm.STATIC_PREFIX,
            static_folder=cm.DIR_W_STATIC,
            template_folder=cm.DIR_W_TEMPLATES)

# Cookies encoding (still not secure)
app.secret_key = '80ca847ebbc7b195ef5781b114379d79'

# Upload size restriction
# In case of client_max_body_size 100k; restriction not set in NGinx config
app.config['MAX_CONTENT_LENGTH'] = cm.MAX_CONTENT_LENGTH


def extension_check(field, filestorage):
    """Check extension 'txt'/'sqlite' of the given file.filename.

    :param: File object.
    :type: <FileStorage>
    :return: True if txt or sqlite for Firefox data, False otherwise.
    :rtype: <bool>
    """

    extensions = {
        'ns_fic': '.txt',
        'rp_fic': '.txt',
        'fp_fic': '.sqlite',
    }

    # Don't test empty field
    if not filestorage:
        return False

    LOGGER.info("Extension check:: " + filestorage.filename)
    filename, file_extension = os.path.splitext(filestorage.filename)

    if file_extension != extensions[field]:
        flash("The file &lt;" + secure_filename(filestorage.filename) + \
              "&gt; has a bad extension !", 'danger')
        return False

    return True


def form_valid(files):
    """Check the validity of the form.

    Check if fields are present; if yes test filestorage exists.
    Return False if ALL filestorage objects are empty or if at least 1 field is
    missing.

    :param: Iterable of files in form.
    :type: <werkzeug.datastructures.ImmutableMultiDict>
    :return: True or False according to the form validity.
    :rtype: <bool>
    """

    ids = ('ns_fic', 'rp_fic', 'fp_fic')

    if len(ids) != len(files):
        return False

    file_found = False
    for id in ids:
        # Get file in form (return None if expected id is not in fields)
        filestorage = files.get(id, None)
        if filestorage is None:
            # 1 field absent (None) = danger
            return False
        elif filestorage:
            # Detect if all files are empty
            file_found = True
    return file_found


def parse_config(field, filepath, uMatrix_path, advanced):
    """Generates a uMatrix file with the given file.

    The detection is made with the name of the form field.

    :param arg1: Form field (ns_fic, rp_fic, fp_fic).
    :param arg2: Filepath of an addon config export saved on the server.
    :param arg3: Final filepath for uMatrix rules for the current session.
    :param arg4: Trigger advanced rules for request policy.
    :type arg1: <str>
    :type arg2: <str>
    :type arg3: <str>
    :type arg4: <bool>
    """

    parsers = {
        'ns_fic': NoScriptParser,
        'rp_fic': RequestPolicyParser,
        'fp_fic': FirefoxPermissionsParser,
    }

    converters = {
        'ns_fic': noscript_converter,
        'rp_fic': request_policy_converter,
        'fp_fic': cookie_monster_converter,
    }

    LOGGER.info("parse_config:: " + field + ": " + filepath)

    # Create Parser
    parser = parsers[field]()

    try:
        parser.read_file(filepath)
    except DatabaseError:
        flash("Sqlite file <strong>is not</strong> a database!", 'danger')
        raise ValueError
    except:
        flash("File <strong>is not</strong> a text/plain file!", 'danger')
        raise ValueError

    # Convert parser content
    converters[field](parser, uMatrix_path, advanced=advanced)


@app.route(cm.NGINX_PREFIX, methods=['GET', 'POST'])
def index():
    """Main page"""

    if request.method == 'POST':

        # Check/set ID in session
        if 'ID' not in session:
            # random uuid
            session['ID'] = str(uuid.uuid4())

        # Form validation (fields)
        valid = form_valid(request.files)
        if valid:

            # Build final uMatrix filepath with the help of the user session id
            uMatrix_secure_path = \
                cm.DIR_W_UPLOADS + '/' + session['ID'] + '_uMatrix-rules.txt'

            # Remove previous uMatrix output file
            if os.path.isfile(uMatrix_secure_path):
                os.unlink(uMatrix_secure_path)

            # Convert each file
            for field, file in request.files.items():

                # Verify extension
                if not extension_check(field, file):
                    LOGGER.debug("Extension check:: " + file.filename + \
                                 " refused")
                    continue

                # Save user file on server
                secure_name = secure_filename(file.filename)
                secure_path = '{}/{}_{}'.format(
                    cm.DIR_W_UPLOADS,
                    session['ID'],
                    secure_name
                )
                file.save(secure_path)

                # Make uMatrix rules
                advanced = \
                    True if request.form.get('advanced', False) == 'true' else False

                # Generate a uMatrix config file for the current user file
                try:
                    parse_config(field, secure_path,
                                 uMatrix_secure_path, advanced
                    )
                except ValueError:
                    # If a uMatrix config was made before, we delete it
                    if os.path.isfile(uMatrix_secure_path):
                        os.unlink(uMatrix_secure_path)
                    break
                finally:
                    # Remove uploaded user file from server
                    os.unlink(secure_path)

            # If at the end, the uMatrix file is empty,
            # the given file was erroneous
            if not os.path.isfile(uMatrix_secure_path) or \
                os.stat(uMatrix_secure_path).st_size == 0:
                flash('Erroneous files sent !', 'danger')
            else:
                # flash('Configuration file generated!', 'success')
                return send_from_directory(
                    cm.DIR_W_UPLOADS,
                    session['ID'] + '_uMatrix-rules.txt',
                    as_attachment=True
                )
        else:
            flash("Please send at least <strong>1</strong> file !", 'danger')

    # With data caching: realtime
    return render_template('index.html',
                           PIWIK_URL=cm.PIWIK_URL,
                           PIWIK_SITE_ID=cm.PIWIK_SITE_ID)


def main():

    app.run(debug=True)


if __name__ == "__main__":

    main()
