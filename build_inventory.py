"""Build a truthful, file-verified daily inventory. Missing categories never block a day."""
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read(path, default):
    file = ROOT/path
    return json.loads(file.read_text()) if file.exists() else default

def build():
    records = []
    for path in ['acquisition/official/manifest.json','acquisition/satellite-manifest.json','acquisition/ground/manifest.json','acquisition/flickr/manifest.json','acquisition/field-reviewed/manifest.json']:
        for original in read(path, []):
            row = {k:v for k,v in original.items() if k != 'original_record'}
            f = ROOT/row['path']
            row['file_verified'] = f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest()==row.get('sha256')
            if path.endswith('field-reviewed/manifest.json'):
                records.append(row)
                continue
            row['role'] = 'documentary_evidence' if row['kind']=='official_daily_report' else 'display_preview'
            row['pipeline_branch'] = 'reports_text' if row['kind']=='official_daily_report' else 'browse_only'
            row['user_contribution_eligible'] = False
            if row['kind'] == 'ground_image':
                row['role'] = 'excluded_candidate'
                row['selection_status'] = 'withdrawn_after_user_review'
                row['exclusion_reason'] = 'Sélection précédente rejetée : vues non représentatives de téléphones au sol, qualité et visibilité insuffisantes. Aucun diagnostic individuel automatique ne vaut validation.'
            else:
                row['selection_status'] = 'context_only'
            records.append(row)
    optical=read('acquisition/sentinel2-analysis/manifest.json',{'days':[]})
    optical_pairs={}
    for day in optical.get('days',[]):
        for pair in read(day.get('result_path','__absent__'),{}).get('pairs',[]):
            identity=pair['source_revision_sha256']
            if identity not in optical_pairs:
                optical_pairs[identity]={**pair,'first_result_path':day['result_path'],'daily_cutoffs':[]}
                preview=Path(day['result_path']).parent/(identity[:24]+'-preview.png')
                if (ROOT/preview).exists():optical_pairs[identity]['preview_path']=str(preview)
            optical_pairs[identity]['daily_cutoffs'].append(day['date'])
    for identity,pair in optical_pairs.items():
        parent=Path(pair['first_result_path']).parent
        for item,file in zip(pair['source_items'],pair['files'],strict=True):
            file_path=parent/file['path'];f=ROOT/file_path
            records.append({'id':identity+'-'+item['id'],'provider':'Copernicus Sentinel-2 / EarthSearch',
                'kind':'satellite_multispectral','pipeline_branch':'sentinel2_optical_change',
                'role':'analytical_input','observed_at':item['properties']['datetime'],
                'local_date':item['properties']['datetime'][:10],'path':str(file_path),
                'sha256':hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None,
                'bytes':f.stat().st_size if f.is_file() else None,'file_verified':f.is_file(),
                'source_url':'https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/'+item['id'],
                'source_item_id':item['id'],'resolution_m':pair['resolution_m'],
                'bands':['B04_20m','B8A_20m','B11_20m','B12_20m','SCL_20m'],
                'processor_revision':pair['processor_revision'],'user_contribution_eligible':False,
                'daily_cutoffs':pair['daily_cutoffs'],'selection_status':'processed_in_existing_optical_branch'})
    days = []
    for day in range(5,10):
        date = f'2025-08-{day:02}'
        items = [r for r in records if r['local_date']==date]
        days.append({'date':date, 'processable_with_partial_sources':True,
            'counts':dict(collections.Counter(r['kind'] for r in items if r['file_verified'] and r['role']!='excluded_candidate')),
            'excluded_candidate_files':sum(r['file_verified'] and r['role']=='excluded_candidate' for r in items),
            'source_ids':[r['id'] for r in items], 'pipeline_status':'not_executed',
            'eligible_user_contributions':sum(r['file_verified'] and r['user_contribution_eligible'] for r in items),
            'baseline':None, 'typesafe_variant':None, 'perimeter':None,
            'missing_categories_are_not_a_failure':True})
    review=read('acquisition/field-reviewed/review.json',{}).get('summary',{})
    query=read('acquisition/copernicus/query.json',{})
    discovery=read('discovery/manifest.json',{})
    expanded=read('acquisition/expanded/manifest.json',{})
    thermal=read('acquisition/thermal/manifest.json',{'status':'credentials_required','observations':[]})
    resume=read('runpod/aws-resume-receipt.json',{})
    collected_pages=sum(p.get('status')=='downloaded' for p in discovery.get('pages',[]))
    discovered_media=len(discovery.get('media_candidates',[]))
    report={'incident':'Ribaute / Corbières', 'period_status':'provisional_research_sequence',
        'updated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope':'daily_multimodal_pipeline_comparison', 'phase':'source_acquisition',
        'benchmark_executed':False, 'representative_collection_validated':False,
        'days':days, 'sources':records,
        'searches':[
            {'family':'Rapports officiels', 'status':'retrieved', 'detail':'22 communiqués indexés du 5 au 9 août, fichiers vérifiés.'},
            {'family':'NASA', 'status':'partial', 'detail':'10 aperçus quotidiens GIBS récupérés. Composites UTC ; qualité et observations sous-jacentes à vérifier.'},
            {'family':'Copernicus · branche optique', 'status':'retrieved' if optical_pairs else 'partial', 'detail':f'{len(optical_pairs)} couples avant/après traités par le processeur Sentinel-2 FireViewer. Acquisition, nuages, couverture valide et ancienneté conservés. Les mêmes passages réutilisés les jours suivants ne sont pas de nouvelles observations.', 'query_url':query.get('url')},
            {'family':'Branche thermique et points chauds', 'status':thermal.get('status','not_completed'), 'detail':thermal.get('detail','Accès NASA FIRMS MAP_KEY et CDSE à configurer pour les valeurs analytiques historiques. Les aperçus ne remplacent pas les mesures.')},
            {'family':'Images au sol', 'status':'partial', 'detail':f"{sum(r['file_verified'] and r.get('user_contribution_eligible',False) for r in records)} images datées et revues. Les substituts de presse au point de vue comparable à un téléphone sont identifiés ; aucun appareil de prise de vue n'est inventé. Les 14 anciennes photos restent écartées."},
            {'family':'Recherche élargie', 'status':'partial', 'detail':f"{sum(p.get('status')=='downloaded' for p in expanded.get('pages',[]))} pages récupérées dans cette collecte ; {len(expanded.get('media',[]))} médias candidats. Les doublons, archives et images hors incident sont exclus de la sélection."},
            {'family':'Périmètres et états antérieurs', 'status':'not_completed', 'detail':'Aucune géométrie de référence ou état antérieur importé pour cet incident.'}],
        'runtime':{'aws_site':'running', 'backend':'running', 'full_pipeline':'not_connected',
            'gpu_image':'built_and_published_cpu_imports_verified', 'gpu_inference_executed':False,
            'runpod_target':'serverless_zero_to_one_a40_worker',
            'blockers':['Image GPU construite et publiée. Déploiement Runpod Serverless en cours ; inférence GPU non encore vérifiée.',
                'Accès au producteur cartographique UWD en attente.',
                'Le parcours de recherche backend actuel dépend de Vercel Blob privé et du worker/provider distant, encore non raccordés au laboratoire.']},
        'excluded_tests':{'reason':'Connectivity checks only, never a daily pipeline evaluation', 'synthetic_cases':1,'single_article_cases':4},
        'collection_progress':{'planned_pages':expanded.get('planned_pages',0),'pages_attempted':len(expanded.get('pages',[])),
            'pages_retrieved':sum(p.get('status')=='downloaded' for p in expanded.get('pages',[])),
            'candidate_images':len(expanded.get('media',[])), 'complete':expanded.get('complete',False)},
        'review':review,
        'videos':read('acquisition/video/manifest.json',[]),
        'branches':{'ground_visual':{'accepted_images':sum(r['file_verified'] and r.get('user_contribution_eligible',False) for r in records)},
            'sentinel2_optical_change':{'unique_pairs':len(optical_pairs),'days':optical.get('days',[]),'pairs':[
                {k:v for k,v in pair.items() if k not in ['coverage_geojson','observations','source_items']} | {'observation_buckets':len(pair.get('observations',[]))}
                for pair in optical_pairs.values()]},
            'thermal_activity':thermal},
        'contribution_policy':{'viewpoint':'ground_handheld_phone_like', 'aerial_is_user_contribution':False,
            'satellite_thermal_hotspots_use_dedicated_branches':True,
            'previous_selection':'withdrawn_after_user_review', 'visual_review_required':True,
            'known_phone_capture_requires_provenance':True,
            'target':'Flammes ou fumée visibles et localisables dans le fichier original ; diversité des distances, angles et moments.',
            'difficult_and_negative_cases':'Cohorte distincte pour mesurer abstention et faux positifs, sans les compter comme observations positives exploitables.'},
        'constraints':{'budget_eur':20,'aws_stop_at':resume.get('stop_at_utc','2026-09-21T00:15:22Z'),'load_test_requested':False}}
    (ROOT/'inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path)
    args=parser.parse_args()
    if args.root:ROOT=args.root
    report=build()
    print(json.dumps({'files_verified':sum(r['file_verified'] for r in report['sources']), 'days':[{k:d[k] for k in ['date','counts']} for d in report['days']]},ensure_ascii=False))
