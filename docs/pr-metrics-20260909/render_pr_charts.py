#!/usr/bin/env python3
"""Render source-labelled PR metric panels. Requires matplotlib==3.10.6."""
import argparse
import json
import math
import textwrap
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def numeric(value):
    return isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value)

def render(source, destination):
    data=json.loads(source.read_text())
    rows=data['rows']
    if not rows:
        raise ValueError(f'{source}: no metric/status rows')
    count=math.ceil(len(rows)/2)
    fig,axes=plt.subplots(count,2,figsize=(12,2.05*count+1.5),squeeze=False)
    fig.patch.set_facecolor('#f7f9fc')
    for ax,row in zip(axes.flat,rows):
        ax.set_facecolor('#ffffff')
        title=f"{row['renderer']} · {row['metric']} ({row['unit']})" if row['renderer']!='Not applicable' else f"{row['metric']} ({row['unit']})"
        ax.set_title('\n'.join(textwrap.wrap(title,53)),loc='left',fontsize=10,pad=8)
        values=[row.get('baseline'),row.get('candidate')]
        shown=[row.get('baseline_display','Not measured'),row.get('candidate_display','Not measured')]
        maximum=max([float(v) for v in values if numeric(v)]+[0.0])
        limit=maximum*1.60 if maximum>0 else 1.0
        for i,(value,label,color) in enumerate(zip(values,shown,['#536b86','#d47b32'])):
            y=1-i
            if numeric(value):
                if value<0: raise ValueError(f'{source}: negative value needs a signed chart')
                ax.barh(y,value,height=.40,color=color)
                ax.text(float(value)+limit*.02,y,str(label),va='center',fontsize=9,color='#182635')
            else:
                ax.text(limit*.02,y,'\n'.join(textwrap.wrap(str(label),48)),va='center',fontsize=8,color='#657282')
        ax.set_yticks([1,0],['Baseline','Candidate / observed'],fontsize=8)
        ax.set_ylim(-.65,1.65); ax.set_xlim(0,limit)
        ax.tick_params(axis='x',labelsize=8)
        if maximum==0: ax.set_xticks([])
        ax.grid(axis='x',alpha=.16);ax.set_axisbelow(True)
        for spine in ['top','right','left']:ax.spines[spine].set_visible(False)
        ax.spines['bottom'].set_color('#d4dce6')
    for ax in list(axes.flat)[len(rows):]:ax.set_visible(False)
    title=f"{data['repo']} #{data['number']} — {data['headline']}"
    fig.suptitle('\n'.join(textwrap.wrap(title,100)),x=.035,ha='left',y=.985,fontsize=13,fontweight='bold',color='#182635')
    scope='Scope: '+data['scope']
    fig.text(.035,.018,'\n'.join(textwrap.wrap(scope,145)),fontsize=8,color='#394c60',va='bottom')
    fig.tight_layout(rect=(.02,.11,.98,.90),h_pad=1.7,w_pad=2.0)
    destination.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(destination,dpi=155,facecolor=fig.get_facecolor(),metadata={'Software':'matplotlib 3.10.6; source metrics stored beside this image'})
    plt.close(fig)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    for source in sorted(args.data.glob('*.json')):
        render(source,args.output/(source.stem+'.png'))
    print(f'Rendered {len(list(args.data.glob("*.json")))} source-labelled PR charts')
if __name__=='__main__':main()
