Python client for Allegro.pl API
================================

.. image:: https://travis-ci.com/mattesilver/allegro-pl.svg?branch=master
    :target: https://travis-ci.com/mattesilver/allegro-pl

.. image:: https://img.shields.io/pypi/v/mattes-allegro-pl.svg
    :target: https://pypi.org/project/mattes-allegro-pl/

.. image:: https://codecov.io/gh/mattesilver/allegro-pl/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/mattesilver/allegro-pl


Supports both Rest and SOAP APIs

Usage:

.. code-block::

    import allegro_pl
    cs = ClientCodeStore('CLIENT ID','CLIENT SECRET')
    ts = TokenStore('ACCESS TOKEN','REFRESH TOKEN)

    auth = ClientCredentialsAuth(cs, ts)
    allegro = allegro_pl.Allegro(auth)

    rest_service = allegro.rest_service()

    categories = rest_service.get_categories(cat_id)

    # access to soap service
    soap_service = allegro.soap_service()

    # direct access to rest and soap clients:
    rest_service = allegro.rest_client()
    soap_client = allegro.soap_client()
