"""Materialize the visual/provenance review of the frozen 65-page collection.

The decisions below are human-readable agent review, not model predictions or
reference annotations. Publication timestamps never become capture timestamps.
"""
import collections, datetime as dt, hashlib, html, json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
m=json.loads((ROOT/'acquisition/expanded/manifest.json').read_text())
large=[x for x in m['media'] if x.get('width',0)>=800 and x.get('height',0)>=400]
assert len(large)==146 and large[145]['id']=='field-candidate-6d6941de1b5aec0da854', 'Review order changed'
pages={p['id']:p for p in m['pages']}
# index: (capture day, provenance precision, visible scene, credit, origin)
positive={
 0:(5,'same_day_report_context','Flammes près des habitations, vue au sol.','Idriss Bigou-Gilles / AFP','press'),
 3:(5,'same_day_report_context','Front de flammes sur une colline, vue au sol.','Idriss Bigou-Gilles / AFP','press'),
 5:(5,'dated_caption','Flammes et fumée très proches, vue depuis un véhicule.','Sécurité civile','emergency_service'),
 6:(5,'dated_caption','Flammes hautes et fumée sur le relief de Tournissan.','Idriss Bigou-Gilles / AFP','press'),
 8:(5,'dated_caption','Flammes proches ; habitants qui filment depuis le sol.','Idriss Bigou-Gilles / AFP','press'),
 11:(5,'dated_caption','Incendie nocturne sur le relief de Tournissan.','Idriss Bigou-Gilles / AFP','press'),
 46:(7,'on_scene_report_context','Pompier au premier plan et flammes visibles derrière lui.','Denis Masliah / Le Dauphiné','press'),
 55:(6,'dated_image_alt','Personnes au bord de la route face aux flammes, Durban-Corbières.','AP / Euronews','press'),
 56:(5,'dated_image_alt','Flammes hautes dans la végétation, vue depuis le sol.','AP / Euronews','press'),
 57:(5,'caption_weekday_and_incident_context','Paysage au sol, foyers visibles et panache.','Richard Capoulade / UGC via AP','credited_ugc'),
 58:(7,'dated_image_alt','Pompiers et feu dans un champ ; capture le 7, fournie à la presse le 8.','Sécurité civile via AP','emergency_service'),
 63:(5,'same_day_report_context','Village au premier plan, flammes et panache sur la colline.','Météo Languedoc','weather_witness_relay'),
 108:(5,'same_day_report_context','Crête en flammes et panache noir, paysage au sol.','MAXPPP / L’Indépendant','press'),
 128:(5,'live_report_context','Route au sol sous un panache orange très dense.','Christophe Parra / L’Indépendant','press'),
 129:(5,'dated_caption','Vignes au premier plan et flammes sur le relief ; légende : 5 août, 19 h.','Gaëlle Guéant','credited_witness'),
 130:(5,'live_report_context','Flammes sur une colline vues depuis Lagrasse.','Nathalie Amen Vals / L’Indépendant','press'),
 131:(5,'live_report_context','Habitations et front sur la colline, depuis Lagrasse.','Nathalie Amen Vals / L’Indépendant','press'),
 139:(6,'dated_caption','Flammes dans les arbres à Saint-Laurent-de-la-Cabrerisse.','Philippe Magoni / EPA / EFE','press'),
 144:(6,'dated_caption','Front nocturne à Saint-Laurent-de-la-Cabrerisse.','Saboor Abdul / Reuters','press'),
}
difficult={
 7:(5,'dated_caption','Habitant arrosant ; fumée diffuse et végétation qui masquent le feu.','Idriss Bigou-Gilles / AFP','press'),
 35:(6,'dated_caption','Agriculteur à Fontjoncouse ; visibilité faible, sans front net.','Lionel Bonaventure / AFP','press'),
 59:(8,'dated_image_alt','Arbres brûlés à Fontjoncouse, sans flamme visible.','Manu Fernandez / AP','press'),
 142:(6,'dated_caption','Canadair devant un relief enfumé ; flamme peu discernable.','Manon Cruz / Reuters','press'),
}
# Visually useful, but the image itself has no sufficiently supported capture day.
uncertain={
 61:'Secours de nuit face aux flammes ; article rétrospectif du 8 août.',
 92:'Route et panache ; erreur « juillet » dans la légende, date à résoudre.',
 95:'Front nocturne et arbres en silhouette ; galerie mise à jour plusieurs jours.',
 98:'Flammes sur colline au crépuscule ; galerie sans jour de capture par image.',
 99:'Convoi de secours et feu nocturne ; galerie sans jour de capture par image.',
 100:'Ligne de feu nocturne lointaine ; galerie sans jour de capture par image.',
 101:'Grandes flammes sur le relief ; même reportage que plusieurs images, dépendance conservée.',
 107:'Panache au-dessus d’un terrain parcouru par le feu ; date de capture manquante.',
 110:'Flammes dans une parcelle herbacée ; article rétrospectif sans date de photo.',
 111:'Pompier et flammes proches ; crédit Facebook insuffisant pour dater la photo.',
 118:'Pompiers devant les flammes ; crédit Pompiers 34, capture du 5 ou 6 non départagée.',
 121:'Feu proche des habitations ; crédit Cé Lyne / Météo Languedoc, jour non départagé.',
 132:'Flammes et grande colonne de fumée, vue au sol ; crédit Lionel Bonaventure / AFP, jour de capture absent de la légende accessible.',
 136:'Flammes sur le relief, vue au sol ; galerie du 6 août sans date de capture par image.',
}
duplicate_groups=[[2,7],[4,11,37],[6,34],[8,97],[1,40],[15,26,70,89,93,98],
 [17,33,72],[23,32,78,79,86,108],[28,92],[30,94],[31,95],[35,36],[45,46],
 [60,61],[62,63],[66,107],[68,106],[69,87],[73,76],[74,77],[82,85],
 [25,88,104],[102,124,128],[105,127,131],[113,114],[116,117],[118,119],
 [120,121],[122,123],[125,129],[126,130],[55,134],[11,137,138],[139,140],[142,143],[144,145]]
retained=set(positive)|set(difficult)|set(uncertain)
duplicate_of={}
for group in duplicate_groups:
    chosen=next((i for i in group if i in retained),group[-1])
    for i in group:
        if i!=chosen:duplicate_of[i]=chosen
wrong_incident={22,82,83,84,85,116,117}
archive_unverified={94,112,114,115}
aerial_or_map={27,29,42,43,54,90,91,103,109,133}
irrelevant={12,14,18,19,20,21,50,53,64,67,73,74,75,76,77,80,81,141}
outside_period={49,51,52}
rows=[];decisions=[]
for i,row in enumerate(large):
    p=pages[row['page_id']];doc=BeautifulSoup((ROOT/p['path']).read_text(),'html.parser')
    token=row['url'].split('/view/')[-1].split('/')[0] if '/view/' in row['url'] else row['url'].split('/')[-1].split('?')[0]
    matches=[]
    for im in doc.find_all('img'):
        if token in str(im) and im.get('alt'):matches.append(im['alt'])
    for fig in doc.select('figure'):
        if token in str(fig):matches.append(fig.get_text(' ',strip=True))
    for ob in p.get('structured_data',[]):
        if ob.get('@type')=='ImageObject' and token in (ob.get('url') or ob.get('contentUrl') or ''):
            matches.append(ob.get('caption') or ob.get('name') or '')
    captions=list(dict.fromkeys(html.unescape(x) for x in matches if x))
    decision={'id':row['id'],'review_index':i,'sha256':row['sha256'],'review_method':'agent_visual_contact_sheet_and_source_provenance',
        'source_page':row['source_page'],'caption_evidence':captions[:5]}
    if i in retained:
        known=i in positive or i in difficult
        day,precision,note,credit,origin=(positive|difficult).get(i,(None,'unresolved_capture_day',uncertain.get(i),'See source caption','source_credit_unresolved'))
        role='positive_ground_scene' if i in positive else 'difficult_or_negative' if i in difficult else 'visual_candidate_day_unresolved'
        decision.update(decision=role,note=note)
        modified=next((o.get('dateModified') for o in p.get('structured_data',[]) if o.get('dateModified')),None)
        rows.append({**row,'kind':'ground_image','source_url':row['source_page'],'provider':credit,
            'pipeline_branch':'ground_visual','role':role,'selection_status':'reviewed',
            'local_date':f'2025-08-{day:02}' if day else None,'date_status':precision,
            'observed_at':None,'capture_time_precision':'day' if day else 'unknown',
            'capture_day_inferred':precision.endswith('context'),
            'caption_evidence':captions[:5],'review_note':note,'origin':origin,
            'phone_device_confirmed':False,'viewpoint':'ground_phone_like',
            'actual_fireviewer_user_submission':False,'user_contribution_eligible':i in positive,
            'evaluation_cohort':role,'page_modified_at':modified,
            'historical_availability_verified':False,
            'replay_policy':'retrospective_visual_evaluation; exact historical availability must be verified before strict as-of replay',
            'independence_group':credit if credit!='See source caption' else row['page_id'],
            'visual_annotation_status':'not_annotated','review_method':decision['review_method']})
    elif i in duplicate_of:decision.update(decision='duplicate_or_alternate_crop',duplicate_of=large[duplicate_of[i]]['id'])
    elif i in wrong_incident:decision.update(decision='wrong_incident_or_historical_archive')
    elif i in archive_unverified:decision.update(decision='archive_or_illustration_capture_not_proven')
    elif i in aerial_or_map:decision.update(decision='different_viewpoint_or_map',note='Retained in raw discovery; not a phone contribution or raw spectral measurement.')
    elif i in irrelevant:decision.update(decision='no_useful_fire_observation')
    elif i in outside_period:decision.update(decision='outside_target_period')
    else:decision.update(decision='not_admitted_capture_or_visibility_insufficient')
    decisions.append(decision)
video=json.loads((ROOT/'acquisition/video/manifest.json').read_text())[0]
for j,scene in enumerate(video['scenes']):
    path=ROOT/scene['review_frame'];data=path.read_bytes();is_positive=j!=1
    rows.append({'id':video['id']+f'-review-frame-{j+1}','kind':'ground_image','path':scene['review_frame'],
        'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'provider':'Euronews / No Comment',
        'source_url':video['source_url'],'pipeline_branch':'ground_visual','published_at':video['published_at'],
        'parent_video_id':video['id'],'independence_group':video['id'],'observed_at':None,'local_date':scene['capture_date'],
        'date_status':'video_on_screen_date','capture_time_precision':'day','capture_day_inferred':False,
        'historical_availability_verified':False,'phone_device_confirmed':False,'actual_fireviewer_user_submission':False,
        'viewpoint':'ground_phone_like','selection_status':'reviewed_video_frame',
        'role':'positive_ground_scene' if is_positive else 'difficult_or_negative','user_contribution_eligible':is_positive,
        'review_note':scene['location_label']+' · '+scene['visual_content']+' · extrait de contrôle vers '+str(scene['approx_video_offset_s'])+' s (±2 s).',
        'visual_annotation_status':'not_annotated','rights':video['rights'],'scene_provenance':scene})
out=ROOT/'acquisition/field-reviewed';out.mkdir(exist_ok=True)
(out/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
summary={'reviewed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'raw_candidates':len(m['media']),
    'visual_reviewed':len(large),'video_review_frames':len(video['scenes']),'retained_images':len(rows),'decisions':dict(collections.Counter(d['decision'] for d in decisions)),
    'positive_by_capture_day':dict(collections.Counter(r['local_date'] for r in rows if r['user_contribution_eligible'])),
    'phone_device_confirmed':0,'representative_collection_validated':False,
    'limitations':['Positive scenes are concentrated on 5 August; days 6–9 remain uneven.',
        'No exact camera pose, flame/smoke reference annotation or verified first-publication history.',
        'Publisher and photographer correlations must not become independent evidence votes.',
        'The 14 previously rejected images remain excluded.']}
(out/'review.json').write_text(json.dumps({'summary':summary,'decisions':decisions},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
