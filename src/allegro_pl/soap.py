import logging
import typing

import tenacity
import zeep
import zeep.exceptions
import zeep.xsd

from .utils import is_connection_aborted

log = logging.getLogger(__name__)


class AllegroSoapService:
    def __init__(self, client, client_id: str, country_code: int):
        self._client = client
        self._client_id = client_id
        self._cc = country_code
        self._session_handle: typing.Optional[str] = None
        self._access_token: typing.Optional[str] = None

    def get_items_info(self, items: typing.List[int], description=False, image_url=False, attrs=False,
                       postage_opts=False, company_info=False, product_info=False, after_sales_conds=False, ean=False,
                       additional_services_grp=False) -> zeep.xsd.CompoundValue:
        items_arg = self._client.get_type('ns0:ArrayOfLong')(items)

        return self._client.service.doGetItemsInfo(self._session_handle, items_arg, int(description), int(image_url),
                                                   int(attrs), int(postage_opts), int(company_info), int(product_info),
                                                   int(after_sales_conds), int(ean), int(additional_services_grp))

    get_items_info.items_limit = 10

    def get_states_info(self):
        return self._client.service.doGetStatesInfo(self._cc, self._client_id)

    def login_with_access_token(self):
        log.info('Login to webapi')

        login_result = self._client.service.doLoginWithAccessToken(self._access_token, self._cc, self._client_id)
        self._session_handle = login_result.sessionHandlePart

    def _set_access_token(self, value: str) -> None:
        if self._access_token != value:
            self.session_handle = None
        self._access_token = value

    access_token = property(fset=_set_access_token)

    @property
    def session_handle(self) -> str:
        return self._session_handle

    @session_handle.setter
    def session_handle(self, session_handle: str):
        self._session_handle = session_handle


def get_client_and_service(api_uri: str, client_id: str, country_code: int, refresh_access_token_fn) -> typing.Tuple[
    zeep.client.Client, AllegroSoapService]:
    client = zeep.client.Client(api_uri)
    service = _get_service(client, client_id, country_code, refresh_access_token_fn)
    return client, service


def _get_service(client: zeep.client.Client, client_id: str, country_code: int,
                 refresh_access_token_fn) -> AllegroSoapService:
    service = AllegroSoapService(client, client_id, country_code)

    def before_call(retry_state: tenacity.RetryCallState):
        # re-login even if session_handle is present, if it's second attempt, the session handle is invalid
        if service.session_handle is None or retry_state.attempt_number != 1:
            service.login_with_access_token()

    def before_login(retry_state: tenacity.RetryCallState):
        refresh_access_token_fn(retry_state)

    method_decorator = _get_retrying(before_call)
    login_decorator = _get_retrying(before_login)

    _wrap_methods(service, method_decorator, login_decorator)

    return service


def _get_retrying(before_fn):
    return tenacity.Retrying(
        retry=_token_needs_refresh,
        before=before_fn,
        stop=tenacity.stop_after_attempt(2),
        reraise=True,
    ).wraps


def _wrap_methods(obj: AllegroSoapService, decorator, login_decorator) -> None:
    for name in dir(obj):
        if name.startswith('_') or name == 'access_token':
            continue

        attr = getattr(obj, name)

        if not callable(attr):
            continue

        log.debug('decorate %s.%s', obj, name)

        if name.startswith('login'):
            wrapped = login_decorator(attr)
        else:
            wrapped = decorator(attr)

        wrapped.__dict__.update(attr.__dict__)
        wrapped.__doc__ = attr.__doc__
        wrapped.__name__ = attr.__name__
        setattr(obj, name, wrapped)


def _token_needs_refresh(retry_state: tenacity.RetryCallState) -> bool:
    x = retry_state.outcome.exception()
    if x is None:
        return False
    elif isinstance(x, zeep.exceptions.Fault):
        log.warning("%s - %s", x.code, x.message)
        return x.code == 'ERR_INVALID_ACCESS_TOKEN' or x.code == 'ERR_NO_SESSION'
    elif isinstance(x, zeep.exceptions.ValidationError):
        log.warning("%s %s", x.message, x.path)
        return x.message == 'Missing element sessionHandle'
    elif is_connection_aborted(x):
        return True
    else:
        return False
