from .allegro import Allegro
from .oauth import AllegroAuth, AuthorizationCodeAuth, ClientCodeStore, ClientCredentialsAuth, TokenError, TokenStore, \
    URL_AUTHORIZE, URL_TOKEN
from .rest import AllegroRestService
from .soap import AllegroSoapService

__name__ = 'mattes-allegro-pl'
__version__ = '0.7.1'
