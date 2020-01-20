from unittest import TestCase
from unittest.mock import Mock

import requests
import tenacity
import zeep.exceptions
from allegro_pl.soap import AllegroSoapService, _get_service, _token_needs_refresh


class TestSoap(TestCase):
    def test_service_init(self):
        client = Mock()
        client_id = 'id'
        cc = 1
        svc = AllegroSoapService(client, client_id, cc)

        self.assertEqual(client, svc._client)
        self.assertEqual(client_id, svc._client_id)
        self.assertEqual(cc, svc._cc)
        self.assertIsNone(svc._session_handle)
        self.assertIsNone(svc._access_token)

    def test_get_items_info(self):
        client = Mock()
        mock_list = object()
        mock_list_type = Mock(return_value=mock_list)
        client.get_type = Mock(return_value=mock_list_type)

        svc = AllegroSoapService(client, 'id', 1)
        svc._session_handle = 'session'

        svc.get_items_info([1, 2, 3], True)

        client.get_type.assert_called_once_with('ns0:ArrayOfLong')
        mock_list_type.assert_called_once_with([1, 2, 3])
        client.service.doGetItemsInfo.assert_called_once_with(svc._session_handle, mock_list, 1, 0, 0, 0, 0, 0, 0, 0, 0)

    def test_get_states_info(self):
        client = Mock()
        client_id = 'id'
        cc = 1
        svc = AllegroSoapService(client, client_id, cc)
        svc._session_handle = 'session'

        svc.get_states_info()

        client.service.doGetStatesInfo.assert_called_once_with(cc, client_id)

    def test_session_handle(self):
        client = Mock()
        client_id = 'id'
        cc = 1
        svc = AllegroSoapService(client, client_id, cc)
        svc._session_handle = 'session'

        self.assertEqual(svc._session_handle, svc.session_handle)

    def test_token_needs_refresh_success(self):
        retry_state = tenacity.RetryCallState(None, None, None, None)
        retry_state.outcome = Mock()

        self.assertFalse(_token_needs_refresh(retry_state))

    def test_token_needs_refresh_fault_other(self):
        retry_state = tenacity.RetryCallState(None, None, None, None)
        retry_state.outcome = Mock()
        retry_state.outcome.exception = Mock(return_value=zeep.exceptions.Fault('message'))

        self.assertFalse(_token_needs_refresh(retry_state))

    def test_token_needs_refresh_fault_no_session(self):
        retry_state = tenacity.RetryCallState(None, None, None, None)
        retry_state.outcome = Mock()
        retry_state.outcome.exception = Mock(return_value=zeep.exceptions.Fault('message', code='ERR_NO_SESSION'))

        self.assertTrue(_token_needs_refresh(retry_state))

    def test_token_needs_refresh_fault_invalid_token(self):
        retry_state = tenacity.RetryCallState(None, None, None, None)
        retry_state.outcome = Mock()
        retry_state.outcome.exception = Mock(
            return_value=zeep.exceptions.Fault('message', code='ERR_INVALID_ACCESS_TOKEN'))

        self.assertTrue(_token_needs_refresh(retry_state))

    def test_token_needs_refresh_validation_error_session_handle(self):
        retry_state = tenacity.RetryCallState(None, None, None, None)
        retry_state.outcome = Mock()
        retry_state.outcome.exception = Mock(
            return_value=zeep.exceptions.ValidationError(message='Missing element sessionHandle'))

        self.assertTrue(_token_needs_refresh(retry_state))

    def test_token_needs_refresh_validation_error_other(self):
        retry_state = tenacity.RetryCallState(None, None, None, None)
        retry_state.outcome = Mock()
        retry_state.outcome.exception = Mock(
            return_value=zeep.exceptions.ValidationError())

        self.assertFalse(_token_needs_refresh(retry_state))

    def test_token_needs_refresh_conn_aborted(self):
        retry_state = tenacity.RetryCallState(None, None, None, None)
        retry_state.outcome = Mock()
        retry_state.outcome.exception = Mock(
            return_value=requests.exceptions.ConnectionError(Exception('Connection aborted.')))

        self.assertTrue(_token_needs_refresh(retry_state))

    def test_wrapper(self):
        def erring(*_):
            raise zeep.exceptions.Fault('message', code='ERR_NO_SESSION')

        # with patch.object(AllegroSoapService, 'get_items_info', side_effect=erring) as mocked_method:
        client = Mock()
        client.service.doGetItemsInfo.side_effect = erring

        retry_mock = Mock()

        service = _get_service(client, "C_ID", 1, retry_mock)

        with self.assertRaises(zeep.exceptions.Fault):
            service.get_items_info([1])

        self.assertEqual(2, len(retry_mock.mock_calls))
