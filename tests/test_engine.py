import copy
import csv
import io
import tempfile
import unittest
from pathlib import Path
from century_tracker.engine import (advance, empty_state, failure, metrics, price, reports, HealthError, csv_text)


def home(key='0001_01_CMP', amount=25000000, status='Available', **kwargs):
    return dict(home_key=key,brand='CMP',community_id=key.split('_')[0],address=key+' Main St',lot=key.split('_')[1],
                community='Test Community',url='https://example.test/'+key,status=status,active=status=='Available',price_cents=amount,**kwargs)


def coverage():
    return dict(complete=True,communities=163,map_lots=11000,observed_active=839,markets={'FL/Panhandle':100},community_ids=['1','2'])


class AccountingTests(unittest.TestCase):
    def start(self, rows=None):
        return advance(empty_state(),'2026-10-01',rows or [home()],coverage())
    def step(self,s,day,rows):
        return advance(s,day,rows,coverage())
    def test_baseline_not_added(self):
        s=self.start();self.assertEqual(s['events'],[]);self.assertEqual(s['daily'][0]['added'],'')
    def test_addition(self):
        s=self.step(self.start(),'2026-10-02',[home(),home('0001_02_CMP')]);self.assertEqual(s['daily'][-1]['added'],1)
    def test_pending_uses_last_available_price(self):
        s=self.start();s=self.step(s,'2026-10-02',[home(amount=24999000)])
        s=self.step(s,'2026-10-03',[home(amount=29999000,status='Pending')])
        self.assertEqual(s['events'][-1]['price_cents'],24999000);self.assertEqual(s['daily'][-1]['removal_asp'],'249990.00')
    def test_confirm_disappearance(self):
        s=self.step(self.start(),'2026-10-02',[]);self.assertEqual(s['daily'][-1]['removed'],0);self.assertEqual(s['daily'][-1]['active'],1)
        s=self.step(s,'2026-10-03',[]);self.assertEqual(s['daily'][-1]['removed'],1)
    def test_failure_never_advances_absence(self):
        s=self.step(self.start(),'2026-10-02',[]);s=failure(s,'2026-10-03','timeout')
        self.assertEqual(s['last_success'],'2026-10-02');self.assertEqual(s['homes']['0001_01_CMP']['missing_count'],1)
        self.assertEqual(s['events'],[]);self.assertEqual(s['daily'][-1]['removed'],'')
    def test_missing_then_present_is_not_reappearance(self):
        s=self.step(self.start(),'2026-10-02',[]);s=self.step(s,'2026-10-03',[home()]);self.assertEqual(s['events'],[])
    def test_reappearance_links_original_event(self):
        s=self.step(self.start(),'2026-10-02',[home(status='Pending')]);old=copy.deepcopy(s['events'][0])
        s=self.step(s,'2026-10-09',[home(amount=24000000)]);e=s['events'][-1]
        self.assertTrue(e['reappearance']);self.assertEqual(e['prior_removal_id'],old['event_id']);self.assertEqual(s['events'][0],old)
        s=self.step(s,'2026-10-10',[home(status='Pending')]);self.assertEqual(s['events'][-1]['price_cents'],24000000)
    def test_week_frozen_across_reappearance(self):
        s=self.step(self.start(),'2026-10-02',[home(status='Pending')]);s=self.step(s,'2026-10-08',[]);week=copy.deepcopy(s['weeks'][0])
        s=self.step(s,'2026-10-09',[home()]);self.assertEqual(s['weeks'][0],week)
    def test_url_and_address_changes_keep_identity(self):
        r=home();r.update(url='https://example.test/new',address='0001 01 Main Street')
        s=self.step(self.start(),'2026-10-02',[r]);self.assertEqual(s['events'],[])
    def test_failed_and_partial_capture_cannot_mutate(self):
        s=self.start();old=copy.deepcopy(s)
        for field,value in [('complete',False),('observed_active',1),('communities',1),('map_lots',1),('markets',{}),('community_ids',['1'])]:
            c=coverage();c[field]=value
            with self.subTest(field=field),self.assertRaises(HealthError):advance(s,'2026-10-02',[],c)
            self.assertEqual(s,old)
    def test_duplicate_and_wrong_brand_rejected(self):
        for rows in ([home(),home()],[dict(home(),brand='CCS')],[home(),dict(home('0001_02_CMP'),address=home()['address'])]):
            with self.assertRaises(HealthError):self.start(rows)
    def test_price_validation(self):
        self.assertEqual(price('$249,990.50'),24999050)
        for value in ('249,99','NaN','-250000','250k','1e6','1999/mo',True,'250000.001'):
            with self.subTest(value=value),self.assertRaises(HealthError):price(value)
        self.assertIsNone(price(0));self.assertIsNone(price(None))
    def test_missing_price_excluded_not_zero(self):
        m=metrics([dict(kind='removed',price_cents=x) for x in [25000000,None,27000000]])
        self.assertEqual(m['removed'],3);self.assertEqual(m['priced_removals'],2);self.assertEqual(m['removal_asp'],'260000.00')
    def test_missing_price_retains_last_advertised(self):
        s=self.step(self.start(),'2026-10-02',[home(amount=None)]);s=self.step(s,'2026-10-03',[home(status='Pending')])
        self.assertEqual(s['events'][-1]['price_cents'],25000000);self.assertEqual(s['events'][-1]['price_date'],'2026-10-01')
    def test_qtd_is_event_weighted_and_csv_roundtrips(self):
        s=self.start([home('0001_01_CMP',10000000),home('0001_02_CMP',30000000),home('0001_03_CMP',30000000)])
        s=self.step(s,'2026-10-02',[home('0001_01_CMP',status='Pending'),home('0001_02_CMP',30000000),home('0001_03_CMP',30000000)])
        s=self.step(s,'2026-10-09',[home('0001_01_CMP',status='Pending'),home('0001_02_CMP',status='Pending'),home('0001_03_CMP',status='Pending')])
        with tempfile.TemporaryDirectory() as d:
            reports(s,d,'2026-10-09');r=list(csv.DictReader(io.StringIO(Path(d,'qtd_pricing.csv').read_text(encoding='utf-8-sig'))))[0]
            self.assertEqual(r['removal_asp'],'233333.33');self.assertEqual(r['advertised_removed_value'],'700000.00')
            for p in Path(d).glob('*.csv'):
                self.assertTrue(p.read_bytes().startswith(b'\xef\xbb\xbf'));self.assertNotIn(None,next(csv.DictReader(io.StringIO(p.read_text(encoding='utf-8-sig'))),{}))
    def test_same_day_and_backfill_rejected(self):
        for day in ('2026-10-01','2026-09-30'):
            with self.assertRaises(HealthError):self.step(self.start(),day,[home()])
    def test_missing_week_is_frozen_incomplete(self):
        s=self.step(self.start(),'2026-10-20',[home()]);self.assertEqual(len(s['weeks']),2);self.assertEqual(s['weeks'][1]['status'],'closed_incomplete');self.assertEqual(s['weeks'][1]['active'],'')
    def test_failed_retry_preserves_accepted_day(self):
        s=self.start();f=failure(s,'2026-10-01','timeout');self.assertEqual(s,f)
    def test_two_cycles_in_one_week_count_events(self):
        s=self.start()
        for d,status in [('02','Pending'),('03','Available'),('04','Pending')]:s=self.step(s,'2026-10-'+d,[home(status=status)])
        m=metrics(s['events']);self.assertEqual((m['added'],m['removed'],m['net_change']),(1,2,-1))
    def test_csv_formula_escaped(self):
        text=csv_text(['address'],[{'address':'=1+1'}]);self.assertIn("'=1+1",text)
