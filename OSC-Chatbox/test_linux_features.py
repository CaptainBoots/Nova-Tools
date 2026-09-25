"""
test_linux_features.py
──────────────────────
Unit and integration tests for the new Linux hardware and media features in OSC-Chatbox.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock

# Import the modules under test
from hardware.cpu import _linux_cpu_temp, _linux_cpu_power, _last_rapl_data
from hardware.cpu import cpu_power_access, cpu_temp_access
from hardware.win32 import is_admin
from hardware.memory import _linux_vram
from monitors.media import (
    _dbus_list_players,
    _dbus_playback_status,
    _dbus_position_ms,
    _dbus_metadata,
    _linux_candidate_dbus,
)


class TestLinuxHardwareStats(unittest.TestCase):

    def setUp(self):
        # Reset the RAPL temporal tracking state before each test
        _last_rapl_data["energy"] = None
        _last_rapl_data["time"] = None

    @patch("glob.glob")
    @patch("builtins.open")
    def test_linux_cpu_temp_hwmon(self, mock_open, mock_glob):
        """Test that _linux_cpu_temp correctly parses temperature from hwmon."""
        mock_glob.side_effect = lambda pat: (
            ["/sys/class/hwmon/hwmon0"] if pat == "/sys/class/hwmon/hwmon*"
            else ["/sys/class/hwmon/hwmon0/temp1_input"] if pat == "/sys/class/hwmon/hwmon0/temp*_input"
            else []
        )
        
        # Mock file reads: name and temp1_input
        mock_file_name = MagicMock()
        mock_file_name.read.return_value = "coretemp\n"
        
        mock_file_temp = MagicMock()
        mock_file_temp.read.return_value = "55000\n"
        
        mock_open.side_effect = lambda path, *args, **kwargs: (
            mock_file_name if "name" in path
            else mock_file_temp if "temp1_input" in path
            else MagicMock()
        )
        
        temp = _linux_cpu_temp()
        self.assertEqual(temp, 55)

    @patch("glob.glob")
    @patch("builtins.open")
    def test_linux_cpu_temp_thermal_zone(self, mock_open, mock_glob):
        """Test that _linux_cpu_temp falls back to thermal_zone when hwmon fails."""
        mock_glob.side_effect = lambda pat: (
            [] if "hwmon*" in pat
            else ["/sys/class/thermal/thermal_zone0"] if "thermal_zone*" in pat
            else []
        )
        
        mock_file_type = MagicMock()
        mock_file_type.read.return_value = "x86_pkg_temp\n"
        
        mock_file_temp = MagicMock()
        mock_file_temp.read.return_value = "48000\n"
        
        mock_open.side_effect = lambda path, *args, **kwargs: (
            mock_file_type if "type" in path
            else mock_file_temp if "temp" in path
            else MagicMock()
        )
        
        temp = _linux_cpu_temp()
        self.assertEqual(temp, 48)

    @patch("glob.glob")
    @patch("builtins.open")
    @patch("time.time")
    def test_linux_cpu_power_differential(self, mock_time, mock_open, mock_glob):
        """Test that _linux_cpu_power calculates true Watts from RAPL differential."""
        mock_glob.return_value = ["/sys/class/powercap/intel-rapl/intel-rapl:0"]
        
        mock_file = MagicMock()
        mock_file.read.side_effect = ["100000000\n", "120000000\n"]  # +20 Joules
        mock_open.return_value = mock_file
        
        mock_time.side_effect = [1000.0, 1001.0]  # 1.0 second elapsed
        
        # First reading initializes the temporal baseline (returns 0)
        p1 = _linux_cpu_power()
        self.assertEqual(p1, 0)
        self.assertEqual(_last_rapl_data["energy"], 100000000)
        self.assertEqual(_last_rapl_data["time"], 1000.0)
        
        # Second reading calculates (120,000,000 - 100,000,000) / 1.0s / 1,000,000 = 20W
        p2 = _linux_cpu_power()
        self.assertEqual(p2, 20)


class TestCpuPowerAccess(unittest.TestCase):
    """cpu_power_access(): 'ok'|'denied'|'missing' — never estimated,
    the UI asks for admin on 'denied' instead."""

    @patch("glob.glob")
    def test_power_access_missing(self, mock_glob):
        """No powercap/hwmon files at all (VM, exotic driver)."""
        mock_glob.return_value = []
        self.assertEqual(cpu_power_access(), "missing")

    @patch("builtins.open")
    @patch("glob.glob")
    def test_power_access_denied(self, mock_glob, mock_open):
        """energy_uj exists but is root-only -> ask for admin."""
        mock_glob.side_effect = lambda pat: (
            ["/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"]
            if "powercap" in pat else []
        )
        mock_open.side_effect = PermissionError(13, "Permission denied")
        self.assertEqual(cpu_power_access(), "denied")

    @patch("builtins.open")
    @patch("glob.glob")
    def test_power_access_ok(self, mock_glob, mock_open):
        """energy_uj readable -> real measured Watts available."""
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = "x"
        mock_open.return_value = mock_file
        mock_glob.side_effect = lambda pat: (
            ["/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"]
            if "powercap" in pat else []
        )
        self.assertEqual(cpu_power_access(), "ok")

    @patch("hardware.cpu._linux_cpu_temp", return_value=45)
    def test_cpu_temp_access_ok(self, _mock_temp):
        self.assertEqual(cpu_temp_access(), "ok")

    @patch("hardware.cpu._linux_cpu_temp", return_value=0)
    def test_cpu_temp_access_missing(self, _mock_temp):
        self.assertEqual(cpu_temp_access(), "missing")

    def test_is_admin_returns_bool(self):
        self.assertIsInstance(is_admin(), bool)


class TestLinuxVRAMFallback(unittest.TestCase):

    @patch("glob.glob")
    @patch("subprocess.check_output")
    def test_linux_vram_nvidia_fallback(self, mock_subprocess, mock_glob):
        """Test that _linux_vram falls back to nvidia-smi if sysfs is missing."""
        mock_glob.return_value = [] # no sysfs cards
        
        mock_subprocess.return_value = "2048, 8192\n"
        
        used, total = _linux_vram(0)
        self.assertEqual(used, 2.0) # 2048 / 1024 = 2.0 GB
        self.assertEqual(total, 8.0) # 8192 / 1024 = 8.0 GB
        mock_subprocess.assert_called_with(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            encoding="utf-8", stderr=-3, timeout=5
        )


class TestLinuxDBusMediaFallback(unittest.TestCase):

    @patch("subprocess.check_output")
    def test_dbus_list_players(self, mock_subprocess):
        """Test listing MPRIS players via dbus-send."""
        mock_subprocess.return_value = (
            "method return time=123 sender=org.freedesktop.DBus\n"
            "   array [\n"
            "      string \"org.freedesktop.DBus\"\n"
            "      string \"org.mpris.MediaPlayer2.spotify\"\n"
            "      string \"org.mpris.MediaPlayer2.chromium.instance123\"\n"
            "   ]\n"
        )
        players = _dbus_list_players()
        self.assertEqual(players, ["org.mpris.MediaPlayer2.spotify", "org.mpris.MediaPlayer2.chromium.instance123"])

    @patch("subprocess.check_output")
    def test_dbus_playback_status(self, mock_subprocess):
        """Test fetching playback status via dbus-send."""
        mock_subprocess.return_value = (
            "method return time=123 sender=:1.0\n"
            "   variant       string \"Playing\"\n"
        )
        status = _dbus_playback_status("org.mpris.MediaPlayer2.spotify")
        self.assertEqual(status, "playing")

    @patch("subprocess.check_output")
    def test_dbus_position_ms(self, mock_subprocess):
        """Test fetching position in milliseconds via dbus-send."""
        mock_subprocess.return_value = (
            "method return time=123 sender=:1.0\n"
            "   variant       int64 123456000\n"
        )
        pos = _dbus_position_ms("org.mpris.MediaPlayer2.spotify")
        self.assertEqual(pos, 123456.0)

    @patch("subprocess.check_output")
    def test_dbus_metadata_parsing(self, mock_subprocess):
        """Test parsing complex DBus array and dictionary metadata structure."""
        mock_subprocess.return_value = (
            "variant       array [\n"
            "         dict entry(\n"
            "            string \"mpris:trackid\"\n"
            "            variant                string \"/com/spotify/track/123\"\n"
            "         )\n"
            "         dict entry(\n"
            "            string \"mpris:length\"\n"
            "            variant                uint64 240000000\n"
            "         )\n"
            "         dict entry(\n"
            "            string \"xesam:title\"\n"
            "            variant                string \"Test Song\"\n"
            "         )\n"
            "         dict entry(\n"
            "            string \"xesam:artist\"\n"
            "            variant                array [\n"
            "                  string \"Artist A\"\n"
            "                  string \"Artist B\"\n"
            "               ]\n"
            "         )\n"
            "      ]\n"
        )
        meta = _dbus_metadata("org.mpris.MediaPlayer2.spotify")
        self.assertEqual(meta.get("mpris:trackid"), "/com/spotify/track/123")
        self.assertEqual(meta.get("mpris:length"), "240000000")
        self.assertEqual(meta.get("xesam:title"), "Test Song")
        self.assertEqual(meta.get("xesam:artist"), "Artist A, Artist B")


if __name__ == "__main__":
    unittest.main()
