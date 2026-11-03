import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from century_tracker.source import (BASE, FetchError, detail_availability, directory, fetch,
                                    map_rows, parse_community, retired_community_rows, safe_empty_community)
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
    def test_traditional_brand_card_and_directory(self):
        text=(FIX/'available.html').read_text().replace('Century Complete','Century Communities').replace('_CMP','_CCS')
        row=parse_community(C,text,{},brand='CCS')[0]
        self.assertEqual(row['brand'],'CCS');self.assertEqual(row['home_key'],'00011062_10503_CCS')
        cs=[dict(communityId=i,company='Century Communities') for i in range(150)]
        payload=dict(communities=cs,total=150,showLoadMore=False,relaxedMatch=False)
        self.assertEqual(len(directory(payload,brand='CCS')),150)
    def test_hidden_numeric_price_cannot_replace_advertised(self):
        text=(FIX/'available.html').read_text().replace('$168,990','$199,990')
        with self.assertRaises(HealthError):parse_community(C,text,{})
    def test_whole_dollar_display_accepts_source_rounding_cents(self):
        text=(FIX/'available.html').read_text().replace('168990','168989.96')
        row=parse_community(C,text,{})[0]
        self.assertEqual(row['price_cents'],16899000)
        with self.assertRaises(HealthError):
            parse_community(C,text.replace('168989.96','168980'),{})
    def test_submit_an_offer_is_an_identity_bound_purchase_action(self):
        text=(FIX/'available.html').read_text().replace('Buy Now','Submit An Offer').replace(
            '/buy-online/emailverification2/?sku=','/bid-online/?sku=')
        self.assertTrue(parse_community(C,text,{})[0]['active'])
        with self.assertRaises(HealthError):
            parse_community(C,text.replace('?sku=00011062_10503_CMP','?sku=other_CMP'),{})
    def test_unknown_availability_fails_closed(self):
        text=(FIX/'pending.html').read_text().replace('Pending','Waitlist')
        with self.assertRaises(HealthError):parse_community(C,text,{})
    def test_card_count_mismatch(self):
        text=(FIX/'available.html').read_text().replace('quick-move-in-card','broken-card')
        with self.assertRaises(HealthError):parse_community(C,text,{})
    def test_generic_error_page_not_zero_inventory(self):
        with self.assertRaises(HealthError):parse_community(C,'<html>Temporarily unavailable</html>',{})
    def test_only_explicitly_empty_404_or_410_community_is_skippable(self):
        empty=dict(C,quickMoveInAvailable=False)
        self.assertTrue(safe_empty_community(empty,FetchError(BASE+'/missing',404,22)))
        self.assertTrue(safe_empty_community(empty,FetchError(BASE+'/gone',410,22)))
        for community,error in [(dict(C,quickMoveInAvailable=True),FetchError(BASE+'/missing',404,22)),
                                (empty,FetchError(BASE+'/error',500,22)),
                                (empty,HealthError('timeout'))]:
            with self.subTest(community=community,error=error):
                self.assertFalse(safe_empty_community(community,error))
    def test_fetch_exposes_http_status_without_response_body(self):
        result=SimpleNamespace(returncode=22,stdout=b'',stderr=b'curl: (22) The requested URL returned error: 404')
        with patch('century_tracker.source.subprocess.run',return_value=result),self.assertRaises(FetchError) as caught:
            fetch(BASE+'/missing')
        self.assertEqual(caught.exception.status,404)
    def test_map_schema_unknown_status_and_wrong_brand(self):
        with self.assertRaises(HealthError):map_rows({'Type':'error'})
        for p in [dict(Type='Lot',Brand='CCS'),dict(Type='Lot',Brand='CMP',LotStatus='Mystery')]:
            with self.assertRaises(HealthError):map_rows(dict(Type='FeatureCollection',Features=[dict(Properties=p)]))
    def test_closed_history_cannot_satisfy_minimum_live_map_coverage(self):
        def payload(live,closed):
            features=[dict(Properties=dict(Type='Lot',Brand='CMP',LotStatus=status,
                       LotSku=f'0001_{i}_CMP'))
                      for i,status in enumerate(['SpecModel']*live+['Closed']*closed)]
            return dict(Type='FeatureCollection',Features=features)
        self.assertEqual(len(map_rows(payload(500,0))[0]),500)
        with self.assertRaisesRegex(HealthError,'non-closed national map'):
            map_rows(payload(499,6000))
    def test_conflicting_map_card_status_rejected(self):
        with self.assertRaises(HealthError):parse_community(C,(FIX/'available.html').read_text(),{'00011062_10503_CMP':{'LotStatus':'Pending'}})
    def test_exact_detail_page_resolves_stale_map_conflict(self):
        row=parse_community(C,(FIX/'available.html').read_text(),
                            {'00011062_10503_CMP':{'LotStatus':'Pending'}},
                            lambda sku,url:self.detail())[0]
        self.assertTrue(row['active'])
        self.assertEqual(row['source'],'community_card_detail_confirmed')
    def test_lot_change_detected(self):
        text=(FIX/'available.html').read_text().replace('Lot 10503','Lot 10504')
        with self.assertRaises(HealthError):parse_community(C,text,{})

    def detail(self, sku='00011062_10503_CMP', amount='$168,990', flag='', buy=True):
        return ('<div class="product_detail_contain" data-template="ProductDetailCommercePage_Lot" '
                f'data-product-id="{sku}"><span class="gallery_flags_icon">{flag}</span>'
                f'<p class="price">{amount}</p></div><nav class="sticky_footer_contain">'+
                (f'<a href="/buy-online/emailverification2/?sku={sku}">Buy Now</a>' if buy else '')+'</nav>')

    def test_missing_card_button_confirmed_by_matching_detail(self):
        text=(FIX/'available.html').read_text().replace('Buy Now','View Details')
        r=parse_community(C,text,{},lambda sku,url:self.detail())[0]
        self.assertTrue(r['active'])
        self.assertEqual(r['source'],'community_card_detail_confirmed')

    def test_detail_identity_price_and_unknown_status_fail_closed(self):
        sku='00011062_10503_CMP'
        for detail in [self.detail(sku='other_CMP'),self.detail(amount='$1'),self.detail(buy=False),
                       self.detail(flag='Pending'),self.detail().replace('?sku='+sku,'?sku=other_CMP')]:
            with self.subTest(detail=detail),self.assertRaises(HealthError):
                detail_availability(detail,sku,16899000)

    def test_detail_pending_does_not_use_stale_structured_stock(self):
        detail=self.detail(flag='Pending',buy=False)+'<script>{"availability":"InStock"}</script>'
        self.assertEqual(detail_availability(detail,'00011062_10503_CMP',16899000),'Pending')

    def test_advertised_office_sale_without_online_checkout(self):
        # Regression: Crosswinds 187 Paddle Wheel Path blocked the CCS capture
        # on 2026-11-02 despite matching advertised prices and Now Selling map.
        mapped=json.loads((FIX/'office-sale-map.json').read_text())
        detail=(FIX/'office-sale-detail.html').read_text()
        row=parse_community(C,(FIX/'office-sale-card.html').read_text(),
                            {mapped['LotSku']:mapped},lambda sku,url:detail,brand='CCS')[0]
        self.assertTrue(row['active'])
        self.assertEqual(row['price_cents'],47599000)
        self.assertEqual(row['source'],'community_card_detail_confirmed')

    def test_office_sale_requires_matching_affirmative_map_evidence(self):
        mapped=json.loads((FIX/'office-sale-map.json').read_text())
        detail=(FIX/'office-sale-detail.html').read_text()
        invalid=[None,{},dict(mapped,LotSku='other_CCS'),dict(mapped,LotStatus='Pending'),
                 dict(mapped,IsPublished=False),dict(mapped,IsModelHome=True),
                 dict(mapped,CanBuyOnline=True),dict(mapped,Flag='Coming Soon'),
                 dict(mapped,Price=470000),dict(mapped,Price=None)]
        for candidate in invalid:
            with self.subTest(mapped=candidate),self.assertRaises(HealthError):
                detail_availability(detail,mapped['LotSku'],47599000,candidate)
        for field in ('LotSku','LotStatus','IsPublished','IsModelHome','CanBuyOnline','Flag','Price'):
            missing={k:v for k,v in mapped.items() if k!=field}
            with self.subTest(missing=field),self.assertRaises(HealthError):
                detail_availability(detail,mapped['LotSku'],47599000,missing)

    def test_office_sale_keeps_detail_identity_price_and_status_checks(self):
        mapped=json.loads((FIX/'office-sale-map.json').read_text())
        detail=(FIX/'office-sale-detail.html').read_text()
        sku=mapped['LotSku']
        for candidate in (detail.replace(sku,'other_CCS'),detail.replace('$475,990','$470,000')):
            with self.subTest(detail=candidate),self.assertRaises(HealthError):
                detail_availability(candidate,sku,47599000,mapped)
        pending=detail.replace('Gourmet Kitchen','Pending')
        self.assertEqual(detail_availability(pending,sku,47599000,mapped),'Pending')

    def test_conflicting_duplicate_map_sale_evidence_is_rejected(self):
        mapped=json.loads((FIX/'office-sale-map.json').read_text())
        mapped.update(Type='Lot',Brand='CCS')
        for field,value in (('CanBuyOnline',True),('IsModelHome',True),('Flag','Coming Soon')):
            payload=dict(Type='FeatureCollection',Features=[
                dict(Properties=mapped),dict(Properties=dict(mapped,**{field:value}))])
            with self.subTest(field=field),self.assertRaisesRegex(HealthError,'Conflicting duplicate'):
                map_rows(payload,brand='CCS')

    def test_existing_advertisement_can_continue_when_map_omits_home(self):
        detail=(FIX/'continuing-advertisement-detail.html').read_text()
        sku='00012035_54CCC6B_CCS'
        prior=dict(home_key=sku,active=True,status='Available',price_cents=52499000)
        self.assertEqual(detail_availability(detail,sku,52499000,previous=prior),'Available')
        invalid=[None,{},dict(prior,home_key='other_CCS'),dict(prior,active=False),
                 dict(prior,status='Pending'),dict(prior,price_cents=52000000)]
        for candidate in invalid:
            with self.subTest(previous=candidate),self.assertRaises(HealthError):
                detail_availability(detail,sku,52499000,previous=candidate)
        for mapped in ({},dict(LotSku=sku,LotStatus='Model')):
            with self.subTest(mapped=mapped),self.assertRaises(HealthError):
                detail_availability(detail,sku,52499000,mapped,prior)
        unknown=detail.replace('</div>','<span class="lot-status-icon">Waitlist</span></div>')
        with self.assertRaises(HealthError):
            detail_availability(unknown,sku,52499000,previous=prior)
        pending=detail.replace('</div>','<span class="lot-status-icon">Pending</span></div>')
        self.assertEqual(detail_availability(pending,sku,52499000,previous=prior),'Pending')

    def test_card_passes_previous_home_to_detail_confirmation(self):
        sku='00011062_10503_CMP'
        text=(FIX/'available.html').read_text().replace('Buy Now','View Details')
        prior=dict(home_key=sku,active=True,status='Available',price_cents=16899000)
        row=parse_community(C,text,{},lambda sku,url:self.detail(buy=False),
                            previous_homes={sku:prior})[0]
        self.assertTrue(row['active'])
        unknown=text.replace('</li>','<span class="quick-icon">Waitlist</span></li>')
        with self.assertRaises(HealthError):
            parse_community(C,unknown,{},lambda sku,url:self.detail(buy=False),
                            previous_homes={sku:prior})
        with self.assertRaises(HealthError):
            parse_community(C,text,{},lambda sku,url:self.detail(buy=False),
                            previous_homes={sku:dict(prior,active=False)})

    def test_populated_retired_community_requires_exact_contracted_details(self):
        prior=dict(home_key='00011062_10503_CMP',listing_id='00011062_10503_CMP',brand='CMP',
                   community_id='00011062',directory_id='1',address='4186 Quincy Ave',lot='10503',
                   community='Test Community',url=BASE+'/lots/10503-quincy-ave/',status='Available',
                   active=True,price_cents=16899000,last_price_cents=16899000,state='AZ',market='AZ/Phoenix')
        previous=dict(community_ids=['1'],community_counts={'1':1})
        rows,evidence=retired_community_rows({'2'},previous,{prior['home_key']:prior},
                                             lambda home:self.detail(flag='Pending',buy=False))
        self.assertEqual(rows[0]['status'],'Pending')
        self.assertEqual(rows[0]['source'],'retired_community_detail_confirmed')
        self.assertEqual(evidence['1'][0]['home_key'],prior['home_key'])
        with self.assertRaisesRegex(HealthError,'still available'):
            retired_community_rows({'2'},previous,{prior['home_key']:prior},lambda home:self.detail())

    def test_available_card_does_not_need_detail_fetch(self):
        def unexpected(*args): raise AssertionError('Unexpected detail request')
        self.assertTrue(parse_community(C,(FIX/'available.html').read_text(),{},unexpected)[0]['active'])
