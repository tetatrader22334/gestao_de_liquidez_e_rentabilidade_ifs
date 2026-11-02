"""GMM regulatório complementar; resultados CSV/JSON, sem seleção por significância.
Uso: python executar_gmm_complementar.py --input base_final_exportada.xlsx --output resultados
Dependências: pandas, numpy, scipy, openpyxl, pydynpd==0.2.2, prettytable.
As três especificações são sensibilidades de hipóteses de momentos, não uma competição por valor-p.
"""
import argparse,contextlib,hashlib,io,json,platform,traceback,warnings
from pathlib import Path
from importlib.metadata import version
import numpy as np
import pandas as pd
from pydynpd import regression

SCENARIOS=[('historico','2:3','1:2'),('liquidez_endogena','2:3','2:3'),('instrumentos_reduzidos','2:2','2:2')]

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('resultados'));a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 df=pd.read_excel(a.input,sheet_name='base');cols=['id_entidade','AnoMes_ord','ROA','ROE','NIM','lcr_dec','nsfr_dec']
 missing=set(cols)-set(df)
 if missing:raise ValueError(f'Colunas ausentes: {missing}')
 df=df[cols].copy()
 if df[cols].isna().any().any():raise ValueError('Valores ausentes nas variáveis requeridas; não remover silenciosamente.')
 if df.duplicated(['id_entidade','AnoMes_ord']).any():raise ValueError('Chaves duplicadas.')
 dates=pd.to_datetime(df.AnoMes_ord.astype(int).astype(str),format='%Y%m')
 if not dates.dt.month.isin([3,6,9,12]).all():raise ValueError('Competência não trimestral.')
 q=dates.dt.to_period('Q');df['time_gmm']=q.astype('int64')-q.min().ordinal+1
 df['id_gmm']=pd.factorize(df.id_entidade,sort=True)[0]+1
 # pydynpd 0.2.2 não efetiva a ordenação interna; entrada deve ser entidade-tempo.
 df=df.sort_values(['id_gmm','time_gmm']).reset_index(drop=True)
 if list(zip(df.id_gmm,df.time_gmm))!=sorted(zip(df.id_gmm,df.time_gmm)):raise ValueError('Painel fora de ordem.')
 for c in cols[2:]:df[c]=pd.to_numeric(df[c],errors='raise')
 if not np.isfinite(df[cols[2:]].to_numpy()).all():raise ValueError('Valores não finitos.')
 grid=pd.MultiIndex.from_product([sorted(df.id_entidade.unique()),range(1,int(df.time_gmm.max())+1)],names=['id_entidade','time_gmm'])
 gaps=grid.difference(pd.MultiIndex.from_frame(df[['id_entidade','time_gmm']]))
 protocol={'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'source_drive_id':'1bapTuN842p2aAxPvRSiKgy4RyfGADEGkxx4Vo2gs2D8','N':int(df.id_gmm.nunique()),'T':int(df.time_gmm.max()),'rows':len(df),'missing_entity_quarters':[list(x) for x in gaps],'period':[str(q.min()),str(q.max())],'scenarios':SCENARIOS,'estimators':['difference','system'],'targets':['ROA','ROE','NIM'],'collapse':True,'steps':2,'time_dummies':False,'controls':[],'purpose':'Reprodução e complemento do bloco regulatório; não constitui especificação ajustada completa nem validação causal.','system_assumptions':'Momentos adicionais em níveis exigem restrições sobre condições iniciais e relação das diferenças com o efeito individual; não verificadas por construção.','limitations':['N pequeno e T >= N; redução de instrumentos não elimina limitação assintótica.','LCR/NSFR são proxies contábeis.','Ausência de controles e efeitos comuns completos impede interpretação como associação plenamente ajustada.','Diferença de Hansen não implementada nesta bateria.','Não escolher especificação por significância ou p-valor de Hansen.'],'python':platform.python_version(),'versions':{s:version(s) for s in ['pydynpd','pandas','numpy','scipy']}}
 (a.output/'protocolo_pre_execucao.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
 diagnostics=[];coefs=[];errors=[]
 for scenario,ylags,xlags in SCENARIOS:
  for dep in ['ROA','ROE','NIM']:
   for mode in ['difference','system']:
    label=f'{scenario}_{dep}_{mode}';cmd=f'{dep} L1.{dep} lcr_dec nsfr_dec | gmm({dep}, {ylags}) gmm(lcr_dec nsfr_dec, {xlags}) | '+('nolevel ' if mode=='difference' else '')+'collapse'
    capture=io.StringIO()
    try:
     with warnings.catch_warnings(record=True) as ws,contextlib.redirect_stdout(capture):
      warnings.simplefilter('always');r=regression.abond(cmd,df[['id_gmm','time_gmm',dep,'lcr_dec','nsfr_dec']].copy(),['id_gmm','time_gmm'])
     if len(r.models)!=1:raise RuntimeError('Esperado exatamente um modelo.')
     m=r.models[0];ninst=int(m.z_information.num_instr)
     row={'scenario':scenario,'dependent':dep,'mode':mode,'command':cmd,'n_obs':int(m.num_obs),'N':int(m.N),'T':int(m.T),'n_instruments':ninst,'hansen_p':float(m.hansen.p_value),'hansen_df':int(m.hansen.df),'ar1_p':float(m.AR_list[0].P_value),'ar2_p':float(m.AR_list[1].P_value),'instruments_below_groups':bool(ninst<m.N),'T_ge_N':bool(m.T>=m.N),'warnings':[str(w.message) for w in ws],'difference_hansen':'not_computed'}
     diagnostics.append(row);t=m.regression_table.copy();t.insert(0,'scenario',scenario);t.insert(1,'dependent',dep);t.insert(2,'mode',mode);coefs.append(t)
     print(label,'obs',m.num_obs,'inst',ninst,flush=True)
    except (Exception,SystemExit) as e:
     errors.append({'model':label,'command':cmd,'error':str(e),'traceback':traceback.format_exc()});print(label,'FAILED',str(e),flush=True)
    finally:(a.output/f'{label}.log').write_text(cmd+'\n'+capture.getvalue(),encoding='utf-8')
 if coefs:pd.concat(coefs,ignore_index=True).to_csv(a.output/'coeficientes.csv',index=False)
 pd.DataFrame(diagnostics).to_csv(a.output/'diagnosticos.csv',index=False)
 safe=[{k:(None if isinstance(v,float) and not np.isfinite(v) else v) for k,v in row.items()} for row in diagnostics]
 (a.output/'diagnosticos.json').write_text(json.dumps(safe,ensure_ascii=False,indent=2,allow_nan=False))
 (a.output/'erros.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2))
 print('Completed',len(diagnostics),'failed',len(errors))
 if errors:raise SystemExit(1)

if __name__=='__main__':main()
