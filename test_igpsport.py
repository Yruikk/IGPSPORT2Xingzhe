import unittest
from unittest.mock import Mock, patch
import requests
from igpsport import IGPSportClient, ACTIVITY, TIMEOUT
from ActivitySync import syncData


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.signer_patch = patch("igpsport.WasmSigner")
        self.signer = self.signer_patch.start().return_value
        self.addCleanup(self.signer_patch.stop)
        self.signer.generate_signature.return_value = "signature"
        self.client = IGPSportClient()
        self.client.session = Mock()

    def test_login_signs_exact_body_and_path(self):
        def reply(data):
            response = Mock()
            response.json.return_value = {"code": 0, "data": data}
            return response
        self.client.session.request.side_effect = [reply({"secret_key": "key"}), reply({"access_token": "token"})]
        self.client.login("test-user", "test-password")
        self.assertEqual(self.client.token, "token")
        call = self.client.session.request.call_args
        signed = self.signer.generate_signature.call_args.args
        self.assertEqual(call.kwargs["data"].decode(), signed[4])
        self.assertEqual(signed[:2], ("POST", "/service/auth/account/login"))
        self.assertEqual(call.kwargs["timeout"], TIMEOUT)

    def test_login_failure_is_not_an_empty_success(self):
        self.client.ready = True
        self.client.session.request.return_value.json.return_value = {"code": 1002}
        with self.assertRaises(RuntimeError):
            self.client.login("test-user", "test-password")

    def test_list_uses_detail_time_and_filters_running(self):
        self.client.request = Mock(side_effect=[{"rows": [
            {"rideId": 12, "startTime": "2026.10.18", "exerciseType": 0},
            {"rideId": 13, "exerciseType": 1}]},
            {"startTime": "2026-10-18T08:30:00+08:00"}])
        rows = self.client.activities()
        self.assertEqual(rows, [{"RideId": 12, "StartTime": "2026-10-18 08:30:00+08:00"}])
        self.assertIn("sortType=1", self.client.request.call_args_list[0].args[1])

    def test_invalid_list_fails(self):
        self.client.request = Mock(return_value={"unexpected": []})
        with self.assertRaises(RuntimeError):
            self.client.activities()

    @patch("igpsport.requests.get")
    def test_download_isolated_and_validated(self, get):
        self.client.request = Mock(return_value="https://files.example/ride.fit")
        get.return_value.content = b"12345678.FITdata"
        self.assertEqual(self.client.download(12), b"12345678.FITdata")
        get.assert_called_once_with("https://files.example/ride.fit", timeout=TIMEOUT)
        get.return_value.content = b"<html>Error</html>"
        with self.assertRaises(RuntimeError):
            self.client.download(12)

    def test_missing_secrets_fail_before_network(self):
        with self.assertRaises(RuntimeError):
            syncData(None, None)

    @patch("ActivitySync.requests.session")
    @patch("ActivitySync.IGPSportClient")
    def test_existing_ride_is_not_uploaded(self, factory, session):
        factory.return_value.activities.return_value = [{"RideId": 12, "StartTime": "2026-10-18 08:30:00+08:00"}]
        session.return_value.post.return_value.status_code = 200
        session.return_value.post.return_value.text = '{"data":{"username":"test"}}'
        from datetime import datetime
        start = int(datetime.fromisoformat("2026-10-18T08:30:00+08:00").timestamp()) * 1000
        session.return_value.get.return_value.json.return_value = {"data": {"data": [{"start_time": start}]}}
        self.assertTrue(syncData("test-user", "test-password"))
        factory.return_value.download.assert_not_called()
        self.assertEqual(session.return_value.post.call_count, 1)

    @patch("ActivitySync.requests.session")
    @patch("ActivitySync.IGPSportClient")
    def test_upload_missing_ride_and_surface_rejection(self, factory, session):
        factory.return_value.activities.return_value = [{"RideId": 12, "StartTime": "2026-10-18 08:30:00+08:00"}]
        factory.return_value.download.return_value = b"12345678.FITdata"
        login, upload = Mock(), Mock()
        login.status_code = 200
        login.text = '{"data":{"username":"test"}}'
        upload.json.return_value = {"code": 0}
        session.return_value.post.side_effect = [login, upload]
        session.return_value.get.return_value.json.return_value = {"data": {"data": []}}
        self.assertTrue(syncData("test-user", "test-password"))
        files = session.return_value.post.call_args.kwargs["files"]
        self.assertEqual(files["fit_file"][1], b"12345678.FITdata")
        upload.json.return_value = {"code": 400}
        session.return_value.post.side_effect = [login, upload]
        with self.assertRaises(RuntimeError):
            syncData("test-user", "test-password")

    @patch("ActivitySync.requests.session")
    @patch("ActivitySync.IGPSportClient")
    def test_destination_pagination(self, factory, session):
        factory.return_value.activities.return_value = []
        session.return_value.post.return_value.status_code = 200
        session.return_value.post.return_value.text = '{"data":{"username":"test"}}'
        first, last = Mock(), Mock()
        first.json.return_value = {"data": {"data": [{"start_time": n} for n in range(100)]}}
        last.json.return_value = {"data": {"data": []}}
        session.return_value.get.side_effect = [first, last]
        self.assertTrue(syncData("test-user", "test-password"))
        self.assertIn("offset=100", session.return_value.get.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
