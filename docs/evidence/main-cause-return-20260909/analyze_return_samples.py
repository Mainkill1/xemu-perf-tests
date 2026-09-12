#!/usr/bin/env python3
"""Summarize periodic XEMU_RETURN records against same-thread XEMU_CAUSE totals."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

def rows(path, prefix):
    output=[]
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith(prefix): output.append(json.loads(line[len(prefix):]))
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--stderr', type=Path, required=True)
    p.add_argument('--start-utc-us', type=int, required=True)
    p.add_argument('--end-utc-us', type=int, required=True)
    p.add_argument('--cause-jsonl', type=Path, required=True)
    p.add_argument('--return-jsonl', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args()
    causes=rows(a.stderr, 'XEMU_CAUSE '); returns=rows(a.stderr, 'XEMU_RETURN ')
    a.cause_jsonl.write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in causes), encoding='utf-8')
    a.return_jsonl.write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in returns), encoding='utf-8')
    returns=[x for x in returns if a.start_utc_us<=x['utc_us']<=a.end_utc_us]
    if len(returns)<2 or len({x['tid'] for x in returns})!=1: raise SystemExit('need >=2 same-thread returns in exact window')
    first,last=returns[0],returns[-1]; tid=first['tid']
    def aggregate(row):
        counts=defaultdict(int); chains={}
        for site in row['sites']:
            key=(site['pc'],site['flags']); counts[key]+=site['count']; chains.setdefault(key,(site['first_tb_pc'],site['first_tb_size']))
        return counts,chains
    first_counts,first_chains=aggregate(first); last_counts,last_chains=aggregate(last); sites=[]
    for key in set(first_counts)|set(last_counts):
        count=last_counts[key]-first_counts[key]
        if count<0: raise SystemExit('cumulative site counter decreased')
        if count:
            pc,flags=key; tb_pc,tb_size=first_chains.get(key) or last_chains[key]
            sites.append({'pc':pc,'pc_hex':f'0x{pc:08x}','flags':flags,'count':count,'first_tb_pc':tb_pc,'first_tb_pc_hex':f'0x{tb_pc:08x}','first_tb_size':tb_size})
    sites.sort(key=lambda x:(-x['count'],x['pc'],x['flags']))
    thread=[x for x in causes if x['tid']==tid]
    cause_first=[x for x in thread if x['utc_us']<=first['utc_us']][-1]
    cause_last=[x for x in thread if x['utc_us']<=last['utc_us']][-1]
    null_delta=cause_last['return_null']-cause_first['return_null']; overflow=last['overflow']-first['overflow']; sampled=sum(x['count'] for x in sites); projected=(sampled+overflow)*last['sample_period']; phase=projected-null_delta
    out={'schema_version':1,'purpose':'periodic XEMU_RETURN samples; not benchmark acceptance','performance_acceptance':False,'sample_period':last['sample_period'],'window':{'start_utc_us':a.start_utc_us,'end_utc_us':a.end_utc_us},'records_in_window':len(returns),'tid':tid,'first_record_utc_us':first['utc_us'],'last_record_utc_us':last['utc_us'],'overflow_first':first['overflow'],'overflow_last':last['overflow'],'overflow_delta':overflow,'sampled_total_delta':sampled,'sampled_plus_overflow_delta':sampled+overflow,'projected_return_null_delta':projected,'cause_snapshots_used':{'first_utc_us':cause_first['utc_us'],'last_utc_us':cause_last['utc_us']},'cause_return_null_delta':null_delta,'projected_minus_cause_delta':phase,'period_phase_bound_abs_lt':last['sample_period'],'period_phase_bound_pass':abs(phase)<last['sample_period'],'comparison':'Same-thread CAUSE snapshots immediately preceding the first and last in-window RETURN snapshots. Sample totals (including overflow) multiplied by the 4093 period match NULL return counts within one sampling period; periodic sampling remains potentially biased.','top_sites':sites[:10],'all_sites':sites}
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
