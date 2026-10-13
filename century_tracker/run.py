"""Collect, validate, and publish a daily observation."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .engine import advance, empty_state, failure, reports, csv_text, dollars
from .source import collect


SERIES = {
    'CMP': dict(name='Century Complete', data='data', reports='reports', ready='.publish-ready'),
    'CCS': dict(name='Century Communities', data='data/century_communities',
                reports='reports/century_communities', ready='.publish-ready-ccs'),
}


def save_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    os.replace(temp,path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',default='.')
    parser.add_argument('--brand',choices=sorted(SERIES),default='CMP')
    args=parser.parse_args()
    root=Path(args.root)
    series=SERIES[args.brand]
    data_root=root/series['data']
    report_root=root/series['reports']
    ready=root/series['ready']
    ready.unlink(missing_ok=True)
    now=datetime.now(timezone.utc)
    day=now.astimezone(ZoneInfo('America/Chicago')).date().isoformat()
    run_id=now.strftime('%Y%m%dT%H%M%S%fZ')
    state_path=data_root/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else empty_state()
    if state['last_success']==day:
        ready.write_text('unchanged\n')
        print(f"{day} {series['name']}: already captured; daily observation is immutable")
        return 0
    raw=data_root/'raw'/run_id
    manifest=dict(run_id=run_id,date=day,brand=args.brand,started_at=now.isoformat(),source_version=2)
    try:
        rows,coverage=collect(raw,brand=args.brand)
        updated=advance(state,day,rows,coverage,args.brand)
    except Exception as exc:
        manifest.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        save_json(data_root/'runs'/f'{run_id}.json',manifest)
        save_json(state_path,failure(state,day,str(exc)))
        reports(failure(state,day,str(exc)),report_root,day,series['name']+' Listing Flow Tracker')
        ready.write_text(run_id+' rejected\n')
        print(f'Capture rejected: {exc}',file=sys.stderr)
        return 1
    snapshot=[]
    for row in rows:
        home=updated['homes'][row['home_key']]
        snapshot.append(dict(row,snapshot_date=day,advertised_price=dollars(row['price_cents']),
                             **{k:home.get(k) for k in ('first_seen','last_seen','removed_date','reappeared_date')}))
    snapshot_path=data_root/'snapshots'/f'{day}.csv';snapshot_path.parent.mkdir(parents=True,exist_ok=True)
    snapshot_path.write_text(csv_text('snapshot_date listing_id home_key address lot community url status advertised_price first_seen last_seen removed_date reappeared_date active source'.split(),snapshot),encoding='utf-8')
    save_json(data_root/'coverage'/f'{day}.json',coverage)
    save_json(state_path,updated)
    reports(updated,report_root,day,series['name']+' Listing Flow Tracker')
    manifest.update(status='success',brand=args.brand,active=coverage['observed_active'],rows=len(rows),finished_at=datetime.now(timezone.utc).isoformat())
    save_json(data_root/'runs'/f'{run_id}.json',manifest)
    ready.write_text(run_id+' accepted\n')
    print(f"{day} {series['name']}: accepted {len(rows)} observations; {coverage['observed_active']} available homes")
    return 0


if __name__=='__main__':
    sys.exit(main())
