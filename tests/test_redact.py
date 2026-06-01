"""Redaction golden corpus: catch obvious secrets, do not maul prose."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lib"))
import cairn  # noqa: E402


class TestRedact(unittest.TestCase):
    def _redacted(self, s):
        return cairn.redact_text(s)

    def test_catches_secrets(self):
        cases = [
            ("sk-ant-" + "api03-abcd1234efgh5678ijkl9012", "anthropic_key"),
            ("sk-proj-" + "ABCDEFGHIJKLMNOPQRSTUVWX1234", "openai_key"),
            ("AKIA" + "IOSFODNN7EXAMPLE", "aws_key"),
            ("ghp_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "github_token"),
            ("github_pat_" + "11ABCDEFG0abcdefghij_klmnop", "github_pat"),
            ("xoxb-" + "1234567890-ABCDEFGHIJKLMNO", "slack_token"),
            ("AIza" + "SyA1234567890abcdefghijklmnopqrstuvw", "google_key"),
        ]
        for secret, label in cases:
            out = self._redacted("token here: " + secret + " end")
            self.assertIn("[REDACTED:%s]" % label, out,
                          "did not redact %s" % label)
            self.assertNotIn(secret, out)

    def test_jwt_and_pem_and_bearer(self):
        jwt = ("eyJ" + "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
               "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0."
               "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")
        self.assertIn("[REDACTED:jwt]", self._redacted("auth " + jwt))
        bearer = "Bearer abcdefABCDEF0123456789xyz"
        self.assertIn("[REDACTED:bearer]", self._redacted(bearer))
        pem = ("-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKC\nabc\n"
               "-----END RSA PRIVATE KEY-----")
        out = self._redacted(pem)
        self.assertIn("[REDACTED:pem_key]", out)
        self.assertNotIn("MIIEpAIBAAKC", out)

    def test_assignment_form(self):
        for s in ['api_key = "s3cr3tVALUE123"', "password: hunter2hunter2",
                  "AUTH_TOKEN=abcdef1234567890"]:
            out = self._redacted(s)
            self.assertIn("[REDACTED:", out, "missed assignment in %r" % s)

    def test_does_not_over_redact_prose(self):
        prose = ("We reset the password flow and rotated the API key policy; "
                 "the token bucket limiter and access key rotation worked. "
                 "Commit a1b2c3d4 touched main.py.")
        # No "=" or ":" + value, so nothing should be redacted.
        self.assertEqual(self._redacted(prose), prose)

    def test_keeps_git_sha_and_paths(self):
        s = "see /proj/main.py at commit deadbeefcafebabe1234567890abcdef12345678"
        self.assertEqual(self._redacted(s), s)

    def test_empty_safe(self):
        self.assertEqual(self._redacted(""), "")
        self.assertEqual(self._redacted(None), None)


if __name__ == "__main__":
    unittest.main()
