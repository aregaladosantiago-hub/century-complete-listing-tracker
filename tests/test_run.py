import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from century_tracker.run import main
from test_engine import home, coverage

class PublicationTests(unittest.TestCase):
    def invoke(self, root, brand='CMP'):
        with patch('sys.argv',['tracker','--root',root,'--brand',brand]):
            return main()
    def test_success_and_same_day_dispatch_are_idempotent(self):
        with tempfile.TemporaryDirectory() as root, patch('century_tracker.run.collect',return_value=([home()],coverage())) as collect:
            self.assertEqual(self.invoke(root),0)
            original=Path(root,'data/state.json').read_bytes()
            self.assertEqual(self.invoke(root),0)
            self.assertEqual(collect.call_count,1)
            self.assertEqual(Path(root,'data/state.json').read_bytes(),original)
            self.assertTrue(Path(root,'.publish-ready').exists())
    def test_failed_first_scrape_records_failure_without_snapshot(self):
        with tempfile.TemporaryDirectory() as root, patch('century_tracker.run.collect',side_effect=TimeoutError('source timeout')):
            self.assertEqual(self.invoke(root),1)
            s=json.loads(Path(root,'data/state.json').read_text())
            self.assertIsNone(s['last_success']);self.assertEqual(s['events'],[])
            self.assertFalse(Path(root,'data/snapshots').exists());self.assertTrue(Path(root,'.publish-ready').exists())
    def test_output_failure_cannot_publish_partial_files(self):
        with tempfile.TemporaryDirectory() as root, patch('century_tracker.run.collect',return_value=([home()],coverage())), patch('century_tracker.run.reports',side_effect=OSError('disk failure')):
            Path(root,'.publish-ready').write_text('stale marker')
            with self.assertRaises(OSError):self.invoke(root)
            self.assertFalse(Path(root,'.publish-ready').exists())
    def test_traditional_series_uses_independent_paths(self):
        row=dict(home('0001_01_CCS'),brand='CCS')
        with tempfile.TemporaryDirectory() as root, patch('century_tracker.run.collect',return_value=([row],coverage())):
            self.assertEqual(self.invoke(root,'CCS'),0)
            self.assertTrue(Path(root,'data/century_communities/state.json').exists())
            self.assertFalse(Path(root,'data/state.json').exists())
            report=Path(root,'reports/century_communities/weekly_report.md').read_text()
            self.assertIn('Century Communities Listing Flow Tracker',report)
            self.assertTrue(Path(root,'.publish-ready-ccs').exists())
