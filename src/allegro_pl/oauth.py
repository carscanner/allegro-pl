import abc
import logging
import typing
import datetime

import oauthlib.oauth2
import requests_oauthlib

_ACCESS_TOKEN = 'access_token'
_REFRESH_TOKEN = 'refresh_token'
_KEY_TIMESTAMP = 'timestamp'

URL_TOKEN = 'https://allegro.pl/auth/oauth/token'
URL_AUTHORIZE = 'https://allegro.pl/auth/oauth/authorize'

logger = logging.getLogger(__name__)


class TokenStore:
    def __init__(self, access_token: str = None, refresh_token: str = None, timestamp: datetime.datetime = None):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._timestamp = timestamp

    def save(self) -> None:
        logger.info('Not saving tokens')

    @property
    def access_token(self) -> str:
        return self._access_token

    @access_token.setter
    def access_token(self, access_token: str) -> None:
        if self._access_token != access_token:
            self._timestamp = datetime.datetime.utcnow()
        self._access_token = access_token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    @refresh_token.setter
    def refresh_token(self, refresh_token: str) -> None:
        if self._refresh_token != refresh_token:
            self._timestamp = datetime.datetime.utcnow()
        self._refresh_token = refresh_token

    @classmethod
    def from_dict(cls: typing.Type['TokenStore'], data: dict) -> 'TokenStore':
        if data is None:
            raise ValueError('None')
        ts = cls()
        ts.update_from_dict(data)
        return ts

    def update_from_dict(self, data: dict) -> None:
        self._access_token = data.get(_ACCESS_TOKEN)
        self._refresh_token = data.get(_REFRESH_TOKEN)
        self._timestamp = data.get(_KEY_TIMESTAMP)

    def to_dict(self) -> dict:
        d = {}
        if self._access_token:
            d[_ACCESS_TOKEN] = self.access_token
        if self._refresh_token:
            d[_REFRESH_TOKEN] = self.refresh_token
        if self._timestamp:
            d[_KEY_TIMESTAMP] = self._timestamp
        return d


class ClientCodeStore:
    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def client_secret(self) -> str:
        return self._client_secret


class AllegroAuth(abc.ABC):
    """Handle acquiring and refreshing access_token"""

    def __init__(self, code_store: ClientCodeStore, token_store: TokenStore):
        assert code_store is not None
        self._cs = code_store

        assert token_store is not None
        self._token_store = token_store

    def _on_token_updated(self, token) -> None:
        logger.debug('Token updated')
        self._token_store.update_from_dict(token)
        self._token_store.save()
        if self.notify_token_updated:
            self.notify_token_updated()

    def retry_refresh_token(self, retry_state) -> None:
        if retry_state.attempt_number == 1:
            if self.token_store.access_token is None:
                self.fetch_token()
        else:
            self.refresh_token()

    def notify_token_updated(self) -> None:
        """Update this attribute to be notified of new token"""
        pass

    @property
    def token_store(self) -> TokenStore:
        return self._token_store

    @property
    def client_id(self):
        return self._cs.client_id

    @abc.abstractmethod
    def fetch_token(self) -> None:
        pass

    @abc.abstractmethod
    def refresh_token(self) -> None:
        pass


class ClientCredentialsAuth(AllegroAuth):
    """Authenticate with Client credentials flow.

    The token will expire after 12hrs and the flow doesn't accept re-login."""

    def __init__(self, cs: ClientCodeStore, ts: TokenStore = None):
        if ts is None:
            ts = TokenStore()

        super().__init__(cs, ts)

        client = oauthlib.oauth2.BackendApplicationClient(self._cs.client_id,
                                                          access_token=self.token_store.access_token)

        self.oauth = requests_oauthlib.OAuth2Session(client=client, token_updater=self._on_token_updated)

    def fetch_token(self):
        logger.debug('Fetch token')
        token = self.oauth.fetch_token(URL_TOKEN, client_id=self._cs.client_id, client_secret=self._cs.client_secret)
        self._on_token_updated(token)

    def refresh_token(self):
        logger.debug('refresh_token called...')
        self.fetch_token()


class TokenError(Exception):
    pass


class AuthorizationCodeAuth(AllegroAuth):
    def __init__(self, cs: ClientCodeStore, ts: TokenStore, redirect_uri: str):
        super().__init__(cs, ts)
        client = oauthlib.oauth2.WebApplicationClient(self._cs.client_id, access_token=self._token_store.access_token)

        self._oauth = requests_oauthlib.OAuth2Session(self._cs.client_id, client, URL_TOKEN, redirect_uri=redirect_uri,
                                                      token_updater=self._token_store.access_token)

    def refresh_token(self):
        logger.info('Refresh token')
        from requests.auth import HTTPBasicAuth
        try:
            # OAuth2 takes data in the body, but allegro expects it in the query
            url = mkurl(URL_TOKEN,
                        {'grant_type': _REFRESH_TOKEN,
                         'refresh_token': self.token_store.refresh_token,
                         'redirect_uri': self._oauth.redirect_uri
                         })
            token = self._oauth.refresh_token(url, auth=HTTPBasicAuth(self._cs.client_id,
                                                                      self._cs.client_secret))
            self._on_token_updated(token)
        except oauthlib.oauth2.rfc6749.errors.OAuth2Error as x:
            if x.description.startswith('Invalid refresh token: '):
                error_description = 'Invalid refresh token'
            else:
                error_description = x.description

            logger.warning('Refresh token failed: %s "%s" %s', type(x), x.error, error_description)

            if x.description != 'Full authentication is required to access this resource' \
                    and not x.description.startswith('Invalid refresh token: ') \
                    and x.error != 'invalid_token':
                raise TokenError('Refresh token Failed', x.error) from x

            try:
                self.fetch_token()
            except TokenError as e:
                # Hide potentially sensitive data
                raise e from None
            except Exception as tx:
                # Hide potentially sensitive data
                logger.warning("Error fetching token %s", type(tx))
                raise TokenError('Error fetching token') from None


def mkurl(address, query):
    from urllib.parse import urlencode
    result = [address]
    if query is not None and len(query):
        result.append(urlencode(query, True))
    return '?'.join(result)
