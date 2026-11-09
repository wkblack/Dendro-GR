#!/usr/bin/env python3
"""Validate a bounded Dendro-GR / TwoPunctures installation test, not physics accuracy."""
import array, hashlib, json, math, re, struct, sys
from pathlib import Path
base=Path(sys.argv[1] if len(sys.argv)>1 else '.')
blob=(base/'smoke_q1_tpid_sol.bin').read_bytes()
n,=struct.unpack_from('=I',blob)
assert n==12*12*12, (n,'unexpected TP spectral size')
assert len(blob)==4+8*(31*n-1), (len(blob),'unexpected TP serialization size')
a=array.array('d'); a.frombytes(blob[4:]); assert all(map(math.isfinite,a)), 'nonfinite TP values'
log=(base/'tpid.log').read_text()
residuals=[float(x) for x in re.findall(r'Newton: it=\d+\s+\|F\|=([^\s]+)',log)]
assert residuals and residuals[-1]<=1e-10, residuals
assert (base/'tpid.exit').read_text().strip()=='0'
report={'purpose':'Installation smoke test only; no accuracy or convergence claim.', 'tpid':{'spectral_points':n,'bytes':len(blob),'all_values_finite':True,'final_Newton_residual':residuals[-1],'serialized_residual_maxabs':max(map(abs,a[:n-1])),'sha256':hashlib.sha256(blob).hexdigest()}}
if (base/'bssn.exit').exists():
    assert (base/'bssn.exit').read_text().strip()=='0'
    metas=list((base/'cp').glob('*_step.cp'))
    pairs=[(p,json.loads(p.read_text())) for p in metas]
    p,meta=max(pairs,key=lambda x:x[1]['DENDRO_TS_STEP_CURRENT'])
    assert meta['DENDRO_TS_STEP_CURRENT']==1, meta
    assert meta['DENDRO_TS_TIME_CURRENT']>0, meta
    assert meta['DENDRO_TS_NUM_VARS']==24, meta
    vars=list((base/'cp').glob('*.var'))
    assert vars, 'missing evolved checkpoint'
    stats=[]
    names=['alpha','chi','K','Gt0','Gt1','Gt2','beta0','beta1','beta2','B0','B1','B2','gt00','gt01','gt02','gt11','gt12','gt22','At00','At01','At02','At11','At12','At22']
    for v in vars:
        data=v.read_bytes(); total,begin,end=struct.unpack_from('=III',data)
        local=end-begin
        assert 0<=begin<end<=total
        assert len(data)==12+24*local*8,(v,len(data),local)
        values=array.array('d'); values.frombytes(data[12:])
        assert all(map(math.isfinite,values)), ('nonfinite checkpoint',v)
        stats.append({'file':v.name,'nodes':local,'bytes':len(data),'all_24_fields_finite':True,'range':{name:[min(values[i*local:(i+1)*local]),max(values[i*local:(i+1)*local])] for i,name in enumerate(names)}})
    report['bssn']={'checkpoint_metadata':p.name,'time':meta['DENDRO_TS_TIME_CURRENT'],'step':meta['DENDRO_TS_STEP_CURRENT'],'variables':24,'checkpoint_arrays':stats}
print(json.dumps(report,indent=2))
