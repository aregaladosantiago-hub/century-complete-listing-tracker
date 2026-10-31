"""Append-only observations and event accounting."""
import copy
import csv
import io
import json
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


class HealthError(ValueError):
    pass


CONTRACTED = {'Pending','Reserved','Under Contract','Already Taken','Sold','Closed'}


def price(value):
    if value is None or value == '':
        return None
    text = str(value).strip()
    if not re.fullmatch(r'\$?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?', text):
        raise HealthError(f'Invalid advertised price: {value!r}')
    amount = Decimal(text.replace('$', '').replace(',', ''))
    if amount == 0:
        return None
    if not Decimal('10000') <= amount <= Decimal('5000000'):
        raise HealthError(f'Implausible advertised home price: {value!r}')
    return int(amount * 100)


def dollars(cents):
    return '' if cents is None else f'{Decimal(cents) / 100:.2f}'


def metrics(events):
    removed = [e for e in events if e['kind'] == 'removed']
    prices = [e['price_cents'] for e in removed if e['price_cents'] is not None]
    added = sum(e['kind'] == 'added' for e in events)
    return dict(added=added, removed=len(removed), net_change=added-len(removed),
                removal_asp='' if not prices else str((Decimal(sum(prices))/len(prices)/100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)),
                priced_removals=len(prices), advertised_removed_value=dollars(sum(prices)))


def empty_state():
    return dict(version=1, last_success=None, first_date=None, homes={}, events=[], daily=[], weeks=[], coverage=None)


def validate_coverage(rows, coverage, previous, expected_brand='CMP', previous_homes=None, previous_day=None):
    if not coverage.get('complete'):
        raise HealthError('Incomplete source capture')
    ids = [r['home_key'] for r in rows]
    if len(ids) != len(set(ids)):
        raise HealthError('Duplicate physical homes')
    if any(r.get('brand') != expected_brand for r in rows):
        raise HealthError(f'Unexpected brand in {expected_brand} series')
    physical = [(r['community_id'], re.sub(r'\W', '', r['address'].lower())) for r in rows if r['active']]
    if len(physical) != len(set(physical)):
        raise HealthError('Multiple SKUs for the same address; identity review required')
    for candidate in (coverage, previous):
        if candidate is None:
            continue
        counts = candidate.get('map_status_counts')
        if counts is not None and (any(type(n) is not int or n < 0 for n in counts.values()) or
                                   sum(counts.values()) != candidate['map_lots']):
            raise HealthError('Invalid map status coverage counts')
    if previous:
        previous_counts = previous.get('community_counts', {})
        unavailable = {
            community for community in coverage.get('unavailable_communities', [])
            if previous_counts.get(community, 0) != 0
        }
        if unavailable:
            raise HealthError(f'Previously populated community page unavailable: {sorted(unavailable)}')
        for field in ('communities', 'observed_active'):
            if coverage[field] < previous[field] * .8:
                raise HealthError(f'Abnormal national coverage decline: {field}')
        current_map, previous_map = coverage['map_lots'], previous['map_lots']
        if 'map_status_counts' in coverage and 'map_status_counts' in previous:
            current_map -= coverage['map_status_counts'].get('Closed', 0)
            previous_map -= previous['map_status_counts'].get('Closed', 0)
        if current_map < previous_map * .8:
            raise HealthError('Abnormal national coverage decline: map_lots')
        current={r['home_key']:r for r in rows}
        def accounted_for(prior, field, value):
            return all(h['home_key'] in current and (
                (current[h['home_key']]['active'] and current[h['home_key']].get(field)==value) or
                (not current[h['home_key']]['active'] and current[h['home_key']]['status'] in CONTRACTED))
                for h in prior)
        for market, old in previous['markets'].items():
            new = coverage['markets'].get(market, 0)
            if old >= 10 and new < old * .7:
                # A long capture gap can include a real concentration of sales.
                # Accept it only if every previously observed available SKU is
                # still observed in that market or explicitly contracted now.
                prior=[h for h in (previous_homes or {}).values()
                       if h.get('active') and h.get('market')==market and h.get('last_seen')==previous_day]
                accounted=len(prior)==old and accounted_for(prior,'market',market)
                if not accounted:
                    raise HealthError(f'Abnormal market coverage decline: {market}')
        for community, old in previous.get('community_counts', {}).items():
            if old >= 5 and coverage.get('community_counts', {}).get(community, 0) < old * .5:
                prior_cards=[h for h in (previous_homes or {}).values()
                             if h.get('last_seen')==previous_day and h.get('directory_id')==community and
                             h.get('source','').startswith('community_card')]
                accounted=(len(prior_cards)==old and accounted_for(
                    [h for h in prior_cards if h['active']],'directory_id',community))
                if not accounted:
                    raise HealthError(f'Abnormal community coverage decline: {community}')
        # A community with no observed homes can legitimately disappear when
        # Century retires an empty directory entry.  That cannot create false
        # listing removals, so only fail closed when a missing community had
        # inventory in the last accepted capture.
        resolved_retirements=set(coverage.get('retired_communities', {}))
        missing = {
            community for community in set(previous['community_ids']) - set(coverage['community_ids'])
            if previous_counts.get(community) != 0 and community not in resolved_retirements
        }
        if missing:
            raise HealthError(f'Community directory contracted; review required: {sorted(missing)}')


def advance(state, day, rows, coverage, expected_brand='CMP'):
    """Return new state; never mutate the accepted state on validation failure."""
    date.fromisoformat(day)
    if state['last_success'] and day <= state['last_success']:
        raise HealthError('Successful dates are immutable; no same-day replacement or backfill')
    validate_coverage(rows, coverage, state['coverage'], expected_brand, state['homes'], state['last_success'])
    s = copy.deepcopy(state)
    baseline = s['last_success'] is None
    s['first_date'] = s['first_date'] or day
    current = {r['home_key']: r for r in rows}
    events = []
    def emit(kind, key, home, reason, reappearance=False):
        e = dict(event_id=f'{day}:{key}:{kind}', date=day, home_key=key, kind=kind,
                 price_cents=home.get('last_price_cents') if kind == 'removed' else home.get('price_cents'),
                 price_date=home.get('last_price_date') if kind == 'removed' else day,
                 previous_snapshot=s['last_success'], reason=reason, reappearance=reappearance,
                 prior_removal_id=home.get('last_removal_id') if reappearance else None,
                 **{k: home.get(k, '') for k in ('address','lot','community','url')})
        events.append(e)
        return e['event_id']
    for key in sorted(set(s['homes']) | set(current)):
        old = s['homes'].get(key)
        row = current.get(key)
        was_active = bool(old and old['active'])
        home = copy.deepcopy(old) if old else dict(first_seen=day, removed_date=None, reappeared_date=None,
                                                  last_price_cents=None, last_price_date=None, last_removal_id=None)
        if row:
            home.update(row)
            home.update(last_seen=day, missing_count=0)
            now_active = row['active']
            reason = row['status']
        else:
            home['missing_count'] = home.get('missing_count', 0) + 1
            now_active = was_active and home['missing_count'] < 2
            reason = 'absent_twice'
        if was_active and not now_active:
            home['removed_date'] = day
            home['last_removal_id'] = emit('removed', key, home, reason)
        if now_active and not was_active and not baseline:
            reappeared = bool(old and old.get('last_removal_id'))
            emit('added', key, home, 'reappeared' if reappeared else 'newly_available', reappeared)
            if reappeared:
                home['reappeared_date'] = day
        # Prices observed after removal never replace the pre-removal price.
        if row and now_active:
            if row['price_cents'] is not None:
                home['last_price_cents'] = row['price_cents']
                home['last_price_date'] = day
        home['active'] = now_active
        s['homes'][key] = home
    s['events'].extend(events)
    m = metrics(events)
    s['daily'] = [d for d in s['daily'] if d['date'] != day]
    s['daily'].append(dict(date=day, active=sum(h['active'] for h in s['homes'].values()),
                          **{k: ('' if baseline and k != 'removal_asp' else m[k]) for k in ('added','removed','net_change','removal_asp')},
                          scrape_status='baseline' if baseline else 'success'))
    s['last_success'], s['coverage'] = day, coverage
    close_weeks(s, day)
    return s


def weekly_row(s, start, end, closed):
    start_s, end_s = start.isoformat(), end.isoformat()
    obs = [d for d in s['daily'] if start_s <= d['date'] <= end_s and d['scrape_status'] in ('success','baseline')]
    comparable = [d for d in obs if d['scrape_status'] == 'success']
    m = metrics([e for e in s['events'] if start_s <= e['date'] <= end_s])
    complete = len(obs) == 7 and len(comparable) == 7
    return dict(week=f"Week {(start-date.fromisoformat(s['first_date'])).days//7+1}", period_start=start_s,
                period_end=end_s, active=obs[-1]['active'] if obs else '',
                **{k: m[k] if comparable else '' for k in ('added','removed','net_change','removal_asp')},
                status=('closed' if complete else 'closed_incomplete') if closed else 'current')


def close_weeks(s, as_of):
    if not s['first_date']:
        return
    start = date.fromisoformat(s['first_date']) + timedelta(days=7*len(s['weeks']))
    today = date.fromisoformat(as_of)
    while start + timedelta(days=6) < today:
        s['weeks'].append(weekly_row(s, start, start+timedelta(days=6), True))
        start += timedelta(days=7)


def failure(state, day, error):
    s = copy.deepcopy(state)
    if not any(d['date'] == day and d['scrape_status'] in ('success','baseline') for d in s['daily']):
        s['daily'] = [d for d in s['daily'] if d['date'] != day]
        s['daily'].append(dict(date=day, active='', added='', removed='', net_change='', removal_asp='', scrape_status='failed'))
        s['daily'].sort(key=lambda d:d['date'])
    close_weeks(s, day)
    return s


def csv_text(fields, rows):
    buf = io.StringIO(newline='')
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction='ignore');w.writeheader()
    for row in rows:
        # Prevent spreadsheet formula execution in descriptive text.
        w.writerow({k: ("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items() if k in fields})
    return '\ufeff'+buf.getvalue()


def reports(s, root, as_of, title='Century Complete Listing Flow Tracker'):
    root = Path(root);root.mkdir(parents=True, exist_ok=True)
    weeks = list(s['weeks'])
    if s['first_date']:
        start = date.fromisoformat(s['first_date']) + timedelta(days=7*len(weeks))
        weeks.append(weekly_row(s,start,start+timedelta(days=6),False))
    def write(name, fields, rows):
        (root/name).write_text(csv_text(fields.split(),rows), encoding='utf-8')
    write('weekly_history.csv','week period_start period_end active added removed net_change removal_asp status',weeks)
    write('daily_movement.csv','date active added removed net_change removal_asp scrape_status',sorted(s['daily'],key=lambda d:d['date']))
    period = weeks[-1]['period_start'] if weeks else as_of
    for kind in ('added','removed'):
        field = 'advertised_price' if kind=='added' else 'last_advertised_price'
        events=[dict(e,**{field:dollars(e['price_cents'])}) for e in s['events'] if e['kind']==kind and period<=e['date']<=as_of]
        write(f'current_{kind}.csv',f'date address lot community {field} url',events)
    q=date.fromisoformat(as_of);q=q.replace(month=1+3*((q.month-1)//3),day=1)
    qm=metrics([e for e in s['events'] if q.isoformat()<=e['date']<=as_of and e['kind']=='removed'])
    write('qtd_pricing.csv','period_start as_of removed priced_removals removal_asp advertised_removed_value',[dict(period_start=q.isoformat(),as_of=as_of,**qm)])
    lines=[f'# {title}','',f"Last successful observation: {s['last_success'] or 'none'}. Report as of {as_of}.",'',
           '| Week | Period | Active | Added | Removed | Net Change | Removal ASP |','|---|---|---:|---:|---:|---:|---:|']
    for w in weeks:
        vals=[w[k] if w[k]!='' else '—' for k in ('active','added','removed','net_change')]
        asp=f"${Decimal(w['removal_asp']):,.2f}" if w['removal_asp'] else '—'
        lines.append(f"| {w['week']} | {w['period_start']} to {w['period_end']} | "+' | '.join(map(str,vals))+f' | {asp} |')
    lines.extend(['','The final row is the current fixed week. Blank movement means no comparable observation. See CSV status for incomplete closed periods.',
                  'Active includes homes awaiting a second successful absence confirmation. Removed homes are an order proxy; Removal ASP is an advertised-price proxy.'])
    (root/'weekly_report.md').write_text('\n'.join(lines)+'\n')
