import os
import unittest

from security.file_validator import validate_mp3, sanitize_metadata_value, extract_mp3_metadata


class SecurityUploadTests(unittest.TestCase):
    def test_sanitize_metadata_value_removes_html_and_controls(self):
        value = '<script>alert("x")</script>\nTitle\t'
        cleaned = sanitize_metadata_value(value)
        self.assertNotIn('<', cleaned)
        self.assertNotIn('>', cleaned)
        self.assertNotIn('\n', cleaned)
        self.assertNotIn('\t', cleaned)
        self.assertIn('alert', cleaned)

    def test_validate_mp3_rejects_embedded_executable_signatures(self):
        payload = b'\xff\xfb\x90\x00' + (b'A' * 512) + b'MZ'
        ok, err = validate_mp3('evil.mp3', payload)
        self.assertFalse(ok)
        self.assertIn('Suspicious', err)

    def test_extract_mp3_metadata_reads_title_artist_and_duration(self):
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test.mp3')
        metadata = extract_mp3_metadata(file_path)
        self.assertIn('title', metadata)
        self.assertIn('artist', metadata)
        self.assertIn('duration', metadata)
        self.assertGreaterEqual(float(metadata['duration']), 0)


if __name__ == '__main__':
    unittest.main()
