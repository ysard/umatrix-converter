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
"""This module handles the SQLite database with SQLAlchemy."""

import os
from sqlalchemy import *
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy.ext.declarative import declarative_base

# /!\ initialization for SQL Alchemy Object Mapping
# /!\ This line MUST BE before Profile class that inherits from it
# /!\ This line MUST BE CALLED before any loading of SQL Engine
Base = declarative_base()

class SQLA_Wrapper():
    """Context manager for DB wrapper

    Auto flush & commit changes on exit.

    """

    def __init__(self, **kwargs):
        """Ability to reuse or not the database"""
        self._kwargs = kwargs

    def __enter__(self):
        """Get a pointer to SQL Alchemy session

        :return: SQLAlchemy session.
        :rtype: <SQL session object>
        """
        self._session = loading_sql(**self._kwargs)()
        return self._session

    def __exit__(self, exc_type, exc_value, traceback):
        """Check to see if it is ending with an exception.

        In this case, exception is raised within the with statement.
        => We do a session rollback.
        Otherwise we flush changes before commit them.

        """

        if (exc_type is not None) and (exc_type is not SystemExit):
#            LOGGER.error("Rollback the database")
            self._session.rollback()
            return

        self._session.flush()
        self._session.commit()


def loading_sql(**kwargs):
    """Create an engine & create all the tables we need

    :param: Optional boolean allowing to reuse the database instead of deleting it.
    :type: <boolean>
    :return: session object
    :rtype: <Session()>

    """

    #Base = declarative_base() => see above, near imports
    # Create an engine and create all the tables we need

    # Erase DB file if already exists
    db_file = kwargs['db_file']
    if not os.path.isfile(db_file):
        raise FileNotFoundError

    engine = create_engine('sqlite:///' + db_file, echo=False)
    Base.metadata.create_all(engine)

    #returns an object for building the particular session you want

    #   bind=engine: this binds the session to the engine,
    #the session will automatically create the connections it needs.
    #   autoflush=True: if you commit your changes to the database
    #before they have been flushed, this option tells SQLAlchemy to flush them
    #before the commit is gone.
    #   autocommit=False: this tells SQLAlchemy to wrap all changes between
    #commits in a transaction. If autocommit=True is specified,
    #SQLAlchemy automatically commits any changes after each flush;
    #this is undesired in most cases.
    #   expire_on_commit=True: this means that all instances attached
    #to the session will be fully expired after each commit so that
    #all attribute/object access subsequent to a completed transaction
    #will load from the most recent database state.

    # PAY ATTENTION HERE:
    # http://stackoverflow.com/questions/21078696/why-is-my-scoped-session-raising-an-attributeerror-session-object-has-no-attr
    return scoped_session(sessionmaker(bind=engine, autoflush=True))
