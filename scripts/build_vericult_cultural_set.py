#!/usr/bin/env python3
import json, re, os, sys, unicodedata
from collections import defaultdict
import pandas as pd
import requests
from datasets import load_dataset

OUT120 = "vericult_cultural_prompts_120_exact.txt"
OUT140 = "vericult_cultural_prompts_140_all7_exact.txt"

CULTURE_TERMS = [
    "culture","cultural","tradition","traditional","custom","customary","etiquette","religion","religious","faith",
    "family","parents","grandparent","elder","wedding","marriage","married","funeral","greeting","respect","hospitality",
    "guest","gift","community","festival","holiday","prayer","church","mosque","temple","cuisine","food","values","social norm",
    "cultura","cultural","tradição","tradicional","costume","religião","família","casamento","respeito","avós","comunidade","festa","presente","culinária","fé","valores",
    "tradition","coutume","religion","famille","mariage","respect","communauté","fête","cadeau","cuisine","foi","valeurs",
    "cultura","tradizione","usanza","religione","famiglia","matrimonio","rispetto","comunità","festa","regalo","cucina","fede","valori",
    "संस्कृति","परंपरा","धर्म","परिवार","शादी","विवाह","सम्मान","समुदाय","त्योहार","भोजन","मूल्य",
    "عائلة","احترام","هدية","ضيف","ضيافة","تحية","زواج","رمضان","كرم","ثقافة","تقاليد","عادة","والدين","أجداد",
    "礼","家族","結婚","贈","挨拶","敬語","年上","文化","伝統","習慣","お祝い",
    "家庭","家人","婚礼","婚姻","礼物","问候","尊重","长辈","文化","传统","习俗","客人","待客"
]
HIGH_TERMS = [
    "culture","cultural","tradition","traditional","custom","customary","etiquette","religion","religious","wedding","marriage",
    "cultura","tradição","costume","religião","casamento","tradition","coutume","religion","mariage",
    "cultura","tradizione","religione","matrimonio","संस्कृति","परंपरा","धर्म","शादी","विवाह",
    "ثقافة","تقاليد","عادة","زواج","文化","伝統","習慣","結婚","文化","传统","习俗","婚礼"
]
EXCLUDE_TERMS = ["suicide","kill","weapon","bomb","terrorist","war","self-harm","sexual assault","rape","how to hack","drugs","murder"]

def norm(s):
    return unicodedata.normalize("NFKC", str(s or "")).strip()

def score_text(s):
    t = norm(s).lower()
    if not t or any(x in t for x in EXCLUDE_TERMS):
        return -999
    score = 0
    for x in CULTURE_TERMS:
        if x.lower() in t: score += 2
    for x in HIGH_TERMS:
        if x.lower() in t: score += 3
    if "should i" in t or "what should" in t or "how should" in t or "is it appropriate" in t or "acceptable" in t:
        score += 2
    if 40 <= len(t) <= 900: score += 1
    return score

def pick_diverse(cands, n=20, group=None, max_per_group=None):
    cands = sorted(cands, key=lambda x: (-x.get("_score",0), x.get("_order",0)))
    out=[]; seen=set(); counts=defaultdict(int)
    for x in cands:
        key=(norm(x["prompt"]), norm(x["response"]))
        if key in seen: continue
        g=norm(x.get(group,"")) if group else ""
        if group and max_per_group is not None and counts[g] >= max_per_group: continue
        seen.add(key); out.append(x); counts[g]+=1
        if len(out)>=n: break
    if len(out)<n:
        for x in cands:
            key=(norm(x["prompt"]), norm(x["response"]))
            if key in seen: continue
            seen.add(key); out.append(x)
            if len(out)>=n: break
    if len(out)!=n:
        raise RuntimeError(f"Could only select {len(out)} of {n}")
    return out

def rec(dataset, culture, language, split, sid, url, rtype, prompt, response, extra=None, score=0, order=0):
    d={"dataset":dataset,"culture":norm(culture),"language":norm(language),"split":norm(split),"id":norm(sid),
       "url":url,"response_type":rtype,"prompt":norm(prompt),"response":norm(response),"_score":score,"_order":order}
    if extra: d.update(extra)
    return d

def care_records():
    configs=[("arabic","Arab / Arabic-speaking contexts","Arabic"),("chinese","China / Chinese contexts","Chinese"),("japanese","Japan / Japanese contexts","Japanese")]
    quotas={"arabic":7,"chinese":7,"japanese":6}
    out=[]
    for cfg,culture,lang in configs:
        ds=load_dataset("geyang627/CARE-eval",cfg,split="test")
        c=[]
        for i,r in enumerate(ds):
            if norm(r.get("culture_type")).lower()!="social norms": continue
            s=score_text(r["question"])+5
            c.append(rec("CARE",culture,lang,f"{cfg}/test",i,
                f"https://huggingface.co/datasets/geyang627/CARE-eval/viewer/{cfg}/test",
                "reference answer",r["question"],r["answer"],
                {"culture_type":r.get("culture_type"),"associated_culture":r.get("associated_culture"),"geographic_scope":r.get("geographic_scope")},s,i))
        out.extend(pick_diverse(c,quotas[cfg]))
    return out

def community_records():
    ds=load_dataset("facebook/community-alignment-dataset",split="train",streaming=True)
    c=[]; order=0
    for r in ds:
        prompt=norm(r.get("first_turn_prompt"))
        s=score_text(prompt)
        if s<4: order+=1; continue
        pref=norm(r.get("first_turn_preferred_response"))
        response=""
        if pref in {"response_a","response_b","response_c","response_d"}:
            response=norm(r.get("first_turn_"+pref))
        elif pref:
            response=pref
        if len(response)<60: order+=1; continue
        country=norm(r.get("annotator_country"))
        lang=norm(r.get("assigned_lang"))
        c.append(rec("Community Alignment",country,lang,"train",r.get("conversation_id"),
            "https://huggingface.co/datasets/facebook/community-alignment-dataset",
            "human-preferred LLM response",prompt,response,
            {"preferred_response_label":pref,"annotator_country":country,"assigned_lang":lang,
             "feedback":norm(r.get("first_turn_feedback"))},s,order))
        order+=1
        if len(c)>=600:
            break
    return pick_diverse(c,20,group="annotator_country",max_per_group=8)

def plural_records():
    ds=load_dataset("agdhruv/plural-alignment",split="train",streaming=True)
    c=[]; order=0
    for r in ds:
        prompt=norm(r.get("prompt")); response=norm(r.get("pref"))
        s=score_text(prompt)
        # PLURAL is value-sensitive even when cultural terms are implicit.
        if any(x in prompt.lower() for x in ["family","parents","community","relig","marri","gender","respect","tradition","work","authority","neighbor"]): s+=3
        if s<4 or len(response)<60: order+=1; continue
        c.append(rec("PLURAL",r.get("country"),"English","train",r.get("id"),
            "https://huggingface.co/datasets/agdhruv/plural-alignment",
            "survey-derived preferred response",prompt,response,
            {"dispreferred_response":norm(r.get("dispref")),"sex":r.get("sex"),"age":r.get("age"),"education":r.get("education"),"region_iso":r.get("region_iso")},s,order))
        order+=1
        if len(c)>=600:
            break
    return pick_diverse(c,20,group="culture",max_per_group=8)

def pact_records():
    ds=load_dataset("Angana192/pact-culture-personalization","base_instances",split="train",streaming=True)
    c=[]; order=0
    for r in ds:
        if norm(r.get("scenario_type")).lower()!="same": order+=1; continue
        prompt=norm(r.get("scenario")); response=norm(r.get("culture_following"))
        s=score_text(prompt)+4
        if norm(r.get("dataset")).lower()=="normad": s+=3
        if len(response)<20: order+=1; continue
        c.append(rec("PACT",r.get("base_country"),"English","base_instances/train",r.get("pact_item_id"),
            "https://huggingface.co/datasets/Angana192/pact-culture-personalization",
            "culture_following candidate",prompt,response,
            {"preference_allowing":norm(r.get("preference_allowing")),"source_dataset":r.get("dataset"),"source_row":r.get("source_row"),
             "source_gold_label":r.get("source_gold_label")},s,order))
        order+=1
    return pick_diverse(c,20,group="culture",max_per_group=1)

def thaicli_records():
    urls=[
      ("instruction","https://raw.githubusercontent.com/UpstageAI/ThaiCLI_H6/main/cli/CLI_instruction.parquet"),
      ("factoid","https://raw.githubusercontent.com/UpstageAI/ThaiCLI_H6/main/cli/CLI_factoid.parquet")
    ]
    c=[]; order=0
    def unpack_answers(v):
        if v is None: return "",""
        if hasattr(v,"tolist") and not isinstance(v,(str,dict,list,tuple)):
            v=v.tolist()
        if isinstance(v,str):
            vv=v.strip()
            try: v=json.loads(vv)
            except Exception: return vv,""
        if isinstance(v,dict):
            low={str(k).lower():val for k,val in v.items()}
            chosen=low.get("chosen") or low.get("accepted") or low.get("good") or low.get("preferred") or ""
            rejected=low.get("rejected") or low.get("bad") or low.get("dispreferred") or ""
            return norm(chosen),norm(rejected)
        if isinstance(v,(list,tuple)):
            vals=list(v); chosen=""; rejected=""
            for item in vals:
                if isinstance(item,dict):
                    low={str(k).lower():val for k,val in item.items()}
                    label=norm(low.get("label") or low.get("type") or low.get("preference")).lower()
                    text=low.get("answer") or low.get("text") or low.get("response") or low.get("content")
                    if label in {"chosen","preferred","good","accepted"}: chosen=norm(text)
                    elif label in {"rejected","dispreferred","bad"}: rejected=norm(text)
                    if not chosen and low.get("chosen") is not None: chosen=norm(low.get("chosen"))
                    if not rejected and low.get("rejected") is not None: rejected=norm(low.get("rejected"))
            if chosen: return chosen,rejected
            flat=[norm(x) for x in vals if norm(x)]
            return (flat[0] if flat else ""), (flat[1] if len(flat)>1 else "")
        return norm(v),""

    for typ,url in urls:
        df=pd.read_parquet(url)
        cols={str(x).lower():x for x in df.columns}
        qcol=cols.get("question") or cols.get("prompt")
        themecol=cols.get("theme") or cols.get("category")
        if qcol is None:
            raise RuntimeError(f"ThaiCLI question column unsupported: {list(df.columns)}")
        for i,row in df.iterrows():
            if "answers" in cols:
                chosen,rejected=unpack_answers(row[cols["answers"]])
            else:
                chosen=norm(row[cols["chosen"]]) if "chosen" in cols else ""
                rejected=norm(row[cols["rejected"]]) if "rejected" in cols else ""
            prompt=norm(row[qcol])
            if not prompt or not chosen: continue
            theme=norm(row[themecol]) if themecol is not None else ""
            s=score_text(prompt)+(8 if typ=="instruction" else 3)
            if theme.lower() in {"culture","religion","lifestyle","humanity"}: s+=5
            c.append(rec("ThaiCLI","Thailand","Thai",typ,row.get("id",i),
                f"https://github.com/UpstageAI/ThaiCLI_H6/blob/main/cli/CLI_{typ}.parquet",
                "human-reviewed chosen answer",prompt,chosen,
                {"rejected_response":rejected,"theme":theme},s,order))
            order+=1
    return pick_diverse(c,20)

def prism_records():
    # Survey map gives participant cultural/geographic provenance.
    survey=load_dataset("HannahRoseKirk/prism-alignment","survey",split="train",streaming=True)
    user_meta={}
    for r in survey:
        loc=r.get("location") or {}
        if isinstance(loc,dict):
            birth=loc.get("birth_country") or loc.get("birth_countryISO") or ""
            reside=loc.get("reside_country") or loc.get("reside_countryISO") or ""
        else:
            birth=reside=""
        user_meta[norm(r.get("user_id"))]={"birth":norm(birth),"reside":norm(reside)}
    ds=load_dataset("HannahRoseKirk/prism-alignment","conversations",split="train",streaming=True)
    c=[]; order=0
    for r in ds:
        prompt=norm(r.get("opening_prompt"))
        s=score_text(prompt)
        ctype=norm(r.get("conversation_type"))
        if ctype in {"values guided","controversy guided"}: s+=2
        if s<4: order+=1; continue
        hist=r.get("conversation_history") or []
        models=[x for x in hist if isinstance(x,dict) and x.get("role")=="model" and x.get("turn")==0 and x.get("content")]
        if not models: order+=1; continue
        def numscore(x):
            try:return float(x.get("score"))
            except:return -1
        best=max(models,key=numscore)
        response=norm(best.get("content"))
        if len(response)<60: order+=1; continue
        uid=norm(r.get("user_id")); meta=user_meta.get(uid,{})
        culture=meta.get("birth") or meta.get("reside") or "Participant culture not specified in selected row"
        c.append(rec("PRISM",culture,"English","conversations/train",r.get("conversation_id"),
            "https://huggingface.co/datasets/HannahRoseKirk/prism-alignment",
            "highest-rated opening-turn LLM response",prompt,response,
            {"user_id":uid,"participant_birth_country":meta.get("birth",""),"participant_reside_country":meta.get("reside",""),
             "conversation_type":ctype,"response_score":best.get("score"),"model_provider":best.get("model_provider"),"model_name":best.get("model_name")},s+max(0,numscore(best)/25),order))
        order+=1
    return pick_diverse(c,20,group="culture",max_per_group=3)

def blend_records():
    ds=load_dataset("uilab/BLEnD","annotations",streaming=True)
    c=[]; order=0
    # iterate all country/region splits
    for split, iterable in ds.items():
        for r in iterable:
            prompt=norm(r.get("question")); enq=norm(r.get("en_question"))
            anns=r.get("annotations") or []
            if not anns: continue
            def cnt(a):
                try:return int(a.get("count",0))
                except:return 0
            a=max(anns,key=cnt)
            answers=a.get("answers") or []
            if not answers: continue
            response=norm(answers[0])
            if not response: continue
            s=score_text(enq)+2
            # favor customs/social life over generic geography
            if any(x in enq.lower() for x in ["wedding","birthday","celebrat","family","school","food","eat","drink","holiday","festival","gift","greet","wear","traditional","custom","funeral"]): s+=5
            c.append(rec("BLEnD",split,"Local language","annotations/"+split,r.get("ID"),
                "https://huggingface.co/datasets/uilab/BLEnD",
                "top-voted human short answer",prompt,response,
                {"english_question":enq,"answer_vote_count":a.get("count"),"english_answers":a.get("en_answers")},s,order))
            order+=1
    return pick_diverse(c,20,group="culture",max_per_group=2)

def format_record(i,r):
    extras=[]
    skip={"dataset","culture","language","split","id","url","response_type","prompt","response","_score","_order"}
    for k,v in r.items():
        if k in skip or v in (None,"",[]): continue
        if isinstance(v,(dict,list)): v=json.dumps(v,ensure_ascii=False)
        extras.append(f"{k.upper()}: {v}")
    return "\n".join([
        f"RECORD {i:03d}",
        f"DATASET: {r['dataset']}",
        f"CULTURE/COUNTRY: {r['culture']}",
        f"LANGUAGE: {r['language']}",
        f"SOURCE_SPLIT/CONFIG: {r['split']}",
        f"SOURCE_ROW/ID: {r['id']}",
        f"SOURCE_URL: {r['url']}",
        f"RESPONSE_TYPE: {r['response_type']}",
        *extras,
        "PROMPT:",
        r["prompt"],
        "RESPONSE:",
        r["response"]
    ])

def write_file(path, records, note):
    assert len(records) in (120,140)
    pairs=[(r["prompt"],r["response"]) for r in records]
    assert len(set(pairs))==len(pairs)
    counts=defaultdict(int)
    for r in records: counts[r["dataset"]]+=1
    header=[
      "VERICULT CULTURAL PROMPT–RESPONSE EVALUATION SET",
      f"RECORD COUNT: {len(records)}",
      note,
      "CULTURELLM: EXCLUDED.",
      "SCOPE: Cultural alignment / cultural appropriateness only; generic safety, toxicity, jailbreak, and red-team material excluded by selection.",
      "SELECTION: Records are selected from public source releases using culture/social-norm relevance heuristics, preference/rating metadata, response completeness, and cross-country diversity. Text is copied from source fields without paraphrase or translation.",
      "COUNTS: "+", ".join(f"{k}={v}" for k,v in counts.items()),
      "IMPORTANT: PACT culture_following is a candidate direction, not a universal ground-truth label. PLURAL pref is survey-derived synthetic preference text. PRISM/Community responses are human-rated/preferred model outputs. BLEnD is human short-answer cultural knowledge.",
      "="*80
    ]
    body=("\n\n"+"="*80+"\n\n").join(format_record(i+1,r) for i,r in enumerate(records))
    open(path,"w",encoding="utf-8").write("\n".join(header)+"\n\n"+body+"\n")
    print(path, len(records), dict(counts))

def main():
    parts={}
    builders=[
      ("CARE",care_records),("Community Alignment",community_records),("PLURAL",plural_records),
      ("PACT",pact_records),("ThaiCLI",thaicli_records),("PRISM",prism_records),("BLEnD",blend_records)
    ]
    for name,fn in builders:
        print("BUILD",name,flush=True)
        rows=fn()
        if len(rows)!=20: raise RuntimeError(f"{name}: expected 20 got {len(rows)}")
        parts[name]=rows
        print("OK",name,len(rows),flush=True)
    # User asked 120 but listed 7 datasets × 20 = 140. Produce both:
    core_names=["CARE","Community Alignment","PLURAL","PACT","ThaiCLI","PRISM"]
    core=[r for n in core_names for r in parts[n]]
    all7=[r for n in core_names+["BLEnD"] for r in parts[n]]
    write_file(OUT120,core,"120-record core = 20 each from CARE, Community Alignment, PLURAL, PACT, ThaiCLI, PRISM. BLEnD is supplied in the companion 140-record all-seven file because 7×20=140.")
    write_file(OUT140,all7,"All seven requested datasets = 20 each. Arithmetic total is 140, not 120.")
if __name__=="__main__":
    main()
