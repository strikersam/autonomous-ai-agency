import ctypes
import unittest
from unittest.mock import MagicMock, patch
import os
import packages.auth.admin as admin_auth
class TestWindowsAuth(unittest.TestCase):
    def setUp(self):
        # Mock ctypes.windll safely even if it doesn"t exist
        self.mock_windll = MagicMock()
        self.patcher_windll = patch("ctypes.windll", self.mock_windll, create=True)
        self.patcher_windll.start()

    def tearDown(self):
        self.patcher_windll.stop()

    @patch("os.name", "nt")
    def test_logon_failure(self):
        self.mock_windll.advapi32.LogonUserW.return_value = 0  # failure

        auth = admin_auth.WindowsCredentialAuthenticator()
        auth.enabled = True

        res = auth.authenticate("testuser", "testpass")

        self.assertIsNone(res)
        self.mock_windll.kernel32.CloseHandle.assert_not_called()

    @patch("os.name", "nt")
    def test_logon_success(self):
        self.mock_windll.advapi32.LogonUserW.return_value = 1  # success

        auth = admin_auth.WindowsCredentialAuthenticator()
        auth.enabled = True

        res = auth.authenticate("testuser", "testpass")

        self.assertIsNotNone(res)
        self.assertEqual(res.username, "testuser")
        self.mock_windll.kernel32.CloseHandle.assert_called_once()

if __name__ == "__main__":
    unittest.main()
