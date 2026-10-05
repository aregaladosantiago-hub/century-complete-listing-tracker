import json
import unittest
from pathlib import Path
from century_tracker.source import directory, parse_community, map_rows
from century_tracker.engine import HealthError

FIX=Path(__file__).parent/'fixtures'
C={'name':'Fixture','communityId':1}
class SourceTests(unittest.TestCase):
    def test_real_available_card(self):
        rows=parse_community(C,(FIX/'available.html').read_text(),{})
        self.assertEqual(len(rows),1);self.assertTrue(rows[0]['active']);self.assertEqual(rows[0]['price_cents'],16899000)
        self.assertEqual(rows[0]['address'],'4186 Quincy Ave');self.assertEqual(rows[0]['home_key'],'00011062_10503_CMP')
        self.assertTrue(rows[0]['url'].endswith('/lots/10503-quincy-ave/'))
    def test_pending_has_no_advertised_price(self):
        r=parse_community(C,(FIX/'pending.html').read_text(),{})[0]
        self.assertEqual(r['status'],'Pending');self.assertFalse(r['active']);self.assertIsNone(r['price_cents'])
    def test_api_pagination_contract(self):
        cs=[dict(communityId=i,company='Century Complete') for i in range(100)]
        p=dict(communities=cs,total=100,showLoadMore=False,relaxedMatch=False)
        self.assertEqual(len(directory(p)),100)
        for field,value in [('total',101),('showLoadMore',True),('relaxedMatch',True)]:
            with self.assertRaises(HealthError):directory(dict(p,**{field:value}))
    def test_mixed_brand_rejected(self):
        text=(FIX/'available.html').read_text().replace('Century Complete','Century Communities')
        with self.assertRaises(HealthError):parse_community(C,text,{})
    def test_hidden_numeric_price_cannot_replace_advertised(self):
        text=(FIX/'available.html').read_text().replace('$168,990','$199,990')
        with self.assertRaises(HealthError):parse_community(C,text,{})
    def test_unknown_availability_fails_closed(self):
        text=(FIX/'pending.html').read_text().replace('Pending','Waitlist')
        with self.assertRaises(HealthError):parse_community(C,text,{})
    def test_card_count_mismatch(self):
        text=(FIX/'available.html').read_text().replace('quick-move-in-card','broken-card')
        with self.assertRaises(HealthError):parse_community(C,text,{})
    def test_generic_error_page_not_zero_inventory(self):
        with self.assertRaises(HealthError):parse_community(C,'<html>Temporarily unavailable</html>',{})
    def test_map_schema_unknown_status_and_wrong_brand(self):
        with self.assertRaises(HealthError):map_rows({'Type':'error'})
        for p in [dict(Type='Lot',Brand='CCS'),dict(Type='Lot',Brand='CMP',LotStatus='Mystery')]:
            with self.assertRaises(HealthError):map_rows(dict(Type='FeatureCollection',Features=[dict(Properties=p)]))
    def test_conflicting_map_card_status_rejected(self):
        with self.assertRaises(HealthError):parse_community(C,(FIX/'available.html').read_text(),{'00011062_10503_CMP':{'LotStatus':'Pending'}})
    def test_lot_change_detected(self):
        text=(FIX/'available.html').read_text().replace('Lot 10503','Lot 10504')
        with self.assertRaises(HealthError):parse_community(C,text,{})
