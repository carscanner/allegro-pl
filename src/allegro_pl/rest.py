import json
import logging
import typing

import allegro_api
import allegro_api.models
import allegro_api.rest
import oauthlib
import oauthlib.oauth2
import tenacity

from .utils import is_connection_aborted

log = logging.getLogger(__name__)


class AllegroRestService:
    def __init__(self, client: allegro_api.ApiClient, default_parameters=None):
        self._client = client
        self._cat_service = allegro_api.api.CategoriesAndParametersApi(client)
        self._offer_service = allegro_api.api.PublicOfferInformationApi(client)

        self._def_params = default_parameters

    def _extra_params(self, kwargs):
        return kwargs if kwargs else self._def_params if self._def_params else {}

    def get_categories(self, parent_id: str = None, **kwargs) -> allegro_api.models.CategoriesDto:
        params = self._extra_params(kwargs)
        if parent_id is not None:
            params['parent_id'] = parent_id
        return self._cat_service.get_categories_using_get(**params)

    def get_listing(self, **kwargs) -> allegro_api.models.ListingResponse:
        return self._offer_service.get_listing(**kwargs)

    get_listing.limit_min = 1
    get_listing.limit_max = 100

    def get_category_parameters(self, category_id: str, **kwargs) -> allegro_api.models.CategoryParameterList:
        return self._cat_service.get_flat_parameters_using_get2(category_id, **self._extra_params(kwargs))

    def _set_access_token(self, value: str) -> None:
        self._client.configuration.access_token = value

    access_token = property(fset=_set_access_token)


def get_client_and_service(api_uri: str, refresh_access_token_fn, default_params: dict = None) -> \
        typing.Tuple[allegro_api.ApiClient, AllegroRestService]:
    config = allegro_api.configuration.Configuration()
    config.host = api_uri
    client = allegro_api.ApiClient(config)

    service = AllegroRestService(client, default_params)

    def before_call(retry_state: tenacity.RetryCallState):
        refresh_access_token_fn(retry_state)

    decorator = _get_retrying(before_call)

    _wrap_methods(service, decorator)

    return client, service


def _get_retrying(before_fn):
    return tenacity.Retrying(
        retry=_token_needs_refresh,
        before=before_fn,
        stop=tenacity.stop_after_attempt(2),
        reraise=True,
    ).wraps


def _wrap_methods(obj: AllegroRestService, decorator) -> None:
    for name in dir(obj):
        if name.startswith('_') or name == 'access_token':
            continue

        attr = getattr(obj, name)
        if callable(attr):
            log.debug('decorate %s.%s', obj, name)
            wrapped = decorator(attr)
            wrapped.__dict__.update(attr.__dict__)
            wrapped.__doc__ = attr.__doc__
            wrapped.__name__ = attr.__name__
            setattr(obj, name, wrapped)


def _token_needs_refresh(retry_state: tenacity.RetryCallState) -> bool:
    x = retry_state.outcome.exception(0)
    if x is None:
        return False
    if isinstance(x, oauthlib.oauth2.rfc6749.errors.InvalidGrantError):
        return True
    if isinstance(x, allegro_api.rest.ApiException) and x.status == 401:
        body = json.loads(x.body)
        # don't log more data from body, may contain secrets
        log.warning(body['error'])
        return body['error'] == 'invalid_token'
    elif is_connection_aborted(x):
        return True
    else:
        return False
