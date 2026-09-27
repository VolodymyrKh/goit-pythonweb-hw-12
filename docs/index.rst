Contacts API documentation
==========================

REST API for storing and managing contacts, built with FastAPI, SQLAlchemy,
PostgreSQL and Redis.

Main features:

* registration and login with an access/refresh JWT token pair;
* email confirmation and password reset by email;
* ``user`` and ``admin`` roles (only administrators can change their avatar);
* the current user is cached in Redis;
* every user works only with their own contacts;
* search by name and email, upcoming birthdays for the next 7 days.

Interactive API reference (Swagger) is available at ``/docs`` of a running server.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
   services
   repository
   database
   config


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
