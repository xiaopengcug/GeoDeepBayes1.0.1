import json, math, sys, os, unicodedata

def canonical(v):
    try:
        return isinstance(v,str) and bool(v.strip()) and v==v.strip() and v==unicodedata.normalize("NFC",v) and not any(unicodedata.category(c) in ("Cc","Cf","Cs") for c in v) and bool(v.encode("utf-8"))
    except (TypeError, ValueError, UnicodeError):
        return False

cfg=json.load(open(sys.argv[1],encoding="utf-8-sig"))
ct=json.load(open(os.path.join(os.path.dirname(sys.argv[1]),"decision-contract.json"),encoding="utf-8-sig"))
raw=json.load(open(sys.argv[2],encoding="utf-8-sig"))
if list(raw)!=["draw_totals","summary","decision","replay"]:raise SystemExit("raw exact schema")
if list(raw["replay"])!=["evaluation_split","n","raw_model","calibration_model","threshold_selection","test_predictions","brier","log_score","sharpness","threshold","reliability","cluster_bootstrap","decision_curve"]:raise SystemExit("raw replay exact schema")
if list(raw["replay"]["raw_model"])!=["model","feature","intercept","slope","iterations","train_row_ids","train_cluster_ids"]:raise SystemExit("raw model exact schema")
if list(raw["replay"]["calibration_model"])!=["model","input","intercept","slope","iterations","calibration_row_ids"]:raise SystemExit("calibration model exact schema")
if any(list(x)!=["id","cluster_id","feature","raw_score","probability","event"] for x in raw["replay"]["test_predictions"]):raise SystemExit("prediction exact schema")
if any(list(x)!=["draw_id","chain_id","sample_id","ancestor_id","voxel_ids","weight","volume_m3","tonnage_t","in_situ_metal_t","recovered_metal_t"] for x in raw["draw_totals"]):raise SystemExit("draw total exact schema")
if any(not canonical(v) for v in raw["replay"]["raw_model"]["train_row_ids"]+raw["replay"]["raw_model"]["train_cluster_ids"]+raw["replay"]["calibration_model"]["calibration_row_ids"]) or any(not canonical(v) for x in raw["replay"]["test_predictions"] for v in (x["id"],x["cluster_id"])):raise SystemExit("raw replay identity")
if list(raw["summary"])!=["volume_m3","tonnage_t","in_situ_metal_t","recovered_metal_t"] or any(list(x)!=["q0_10","q0_50","q0_90"] for x in raw["summary"].values()):raise SystemExit("summary exact schema")
if list(raw["decision"])!=["cashflow_time_unit","enpv","best_action","tie_rule","tie_absolute_tolerance","evpi","evsi","net_evsi","sensitivity","nested_mc"]:raise SystemExit("decision exact schema")
if list(raw["decision"]["enpv"])!=["no_drill","pilot","full"]:raise SystemExit("enpv exact schema")
sk=[f"r_{float(v):.15g}" for v in cfg["cashflow_contract"]["sensitivity"]["discount_rate"]]
for group,prefix in (("price_multiplier","price"),("capex_multiplier","capex"),("opex_multiplier","opex")):sk += [f"{prefix}_{float(v):.15g}" for v in cfg["cashflow_contract"]["sensitivity"][group]]
if list(raw["decision"]["sensitivity"])!=sk or any(not math.isfinite(float(v)) for v in raw["decision"]["sensitivity"].values()):raise SystemExit("sensitivity exact schema")
if list(raw["replay"]["threshold_selection"])!=["selected_on","criterion","candidates","scores","optimal_value","selected_threshold"]:raise SystemExit("threshold exact schema")
if any(list(x)!=["lower","upper","n","mean_probability","event_rate"] for x in raw["replay"]["reliability"]):raise SystemExit("reliability exact schema")
if list(raw["replay"]["cluster_bootstrap"])!=["seed","index_scheme","indices","unit","n_clusters","replicates","brier_lo","brier_hi"]:raise SystemExit("bootstrap exact schema")
if list(raw["replay"]["decision_curve"])!=["model","treat_all","treat_none"]:raise SystemExit("decision curve exact schema")
mc=raw["decision"]["nested_mc"]
if list(mc)!=["seed","common_random_numbers","budget_n","budget_2n","actions_by_outcome","best_actions_n","best_actions_2n","at_n","at_2n","error_budget_mcse_multiplier","exact_gross_evsi","exact_net_evsi","stable"]:raise SystemExit("nested mc exact schema")
if list(mc["actions_by_outcome"])!=["positive","negative"] or any(list(mc[g])!=["gross_evsi","net_evsi","mcse","outcome_counts"] or list(mc[g]["outcome_counts"])!=["positive","negative"] for g in ("at_n","at_2n")):raise SystemExit("mc result exact schema")
def close(a,b,t=1e-10):
    if not math.isfinite(float(a)) or abs(float(a)-float(b))>t: raise SystemExit(f"mismatch {a} {b}")
def logistic_fit(rows):
    a=b=0.0
    for it in range(50):
        g0=g1=h00=h01=h11=0.0
        for x,y in rows:
            p=1/(1+math.exp(-(a+b*x)));w=p*(1-p);g0+=y-p;g1+=(y-p)*x;h00+=w;h01+=w*x;h11+=w*x*x
        det=h00*h11-h01*h01
        if det<=1e-12: raise SystemExit("logistic separation/nonidentifiable")
        da=(h11*g0-h01*g1)/det;db=(-h01*g0+h00*g1)/det;a+=da;b+=db
        if max(abs(da),abs(db))<1e-10:return a,b,it+1
    raise SystemExit("logistic MLE did not converge")

if "actions" in cfg["decision"]: raise SystemExit("duplicate economic truth")
draw=[]; lineage=set(); canonical_voxels=None
for d in cfg["draws"]:
    identity=tuple(d.get(k,"") for k in ("draw_id","chain_id","sample_id","ancestor_id"))
    key=identity[1:3]
    if not all(canonical(v) for v in identity): raise SystemExit("draw identity")
    if key in lineage: raise SystemExit("lineage")
    lineage.add(key); ids=[x["id"] for x in d["voxels"]]
    if any(not canonical(x) for x in ids):raise SystemExit("voxel identity")
    if len(ids)!=len(set(ids)) or (canonical_voxels is not None and ids!=canonical_voxels): raise SystemExit("voxel lineage")
    canonical_voxels=ids;v=t=ins=rec=0.0
    for x in d["voxels"]:
        if x["ore"] not in (0,1): raise SystemExit("ore")
        if any(not math.isfinite(x[k]) or not 0<=x[k]<=1 for k in ("grade_fraction","recovery","dilution_factor","loss_factor")): raise SystemExit("proportion")
        a=x["ore"]*x["volume_m3"];v+=a;tonne=a*x["density_t_m3"];t+=tonne;metal=tonne*x["grade_fraction"];ins+=metal;rec+=metal*x["recovery"]*x["dilution_factor"]*x["loss_factor"]
    draw.append((d["weight"],v,t,ins,rec))
for got,d,exp in zip(raw["draw_totals"],cfg["draws"],draw):
    for k in ("draw_id","chain_id","sample_id","ancestor_id"):
        if not canonical(got[k]):raise SystemExit("raw draw identity")
        if got[k]!=d[k]:raise SystemExit("lineage output")
    if any(not canonical(v) for v in got["voxel_ids"]):raise SystemExit("raw voxel identity")
    if got["voxel_ids"]!=canonical_voxels:raise SystemExit("voxel output")
    for k,e in zip(("weight","volume_m3","tonnage_t","in_situ_metal_t","recovered_metal_t"),exp):close(got[k],e)
def wq(col,q):
    c=0
    for w,v in sorted(((d[0],d[col]) for d in draw),key=lambda z:z[1]):
        c+=w
        if c+1e-15>=q:return v
for name,col in (("volume_m3",1),("tonnage_t",2),("in_situ_metal_t",3),("recovered_metal_t",4)):
    for label,q in (("q0_10",.1),("q0_50",.5),("q0_90",.9)):close(raw["summary"][name][label],wq(col,q))

def npv(action,state,r,pm=1,cm=1,om=1):
    return sum((c["revenue"]*pm-c["implementation_cost"]-c["failure_loss"]-c["capex"]*cm-c["opex"]*om-c["tax"]+c["salvage"])/(1+r)**c["t"] for c in cfg["cashflow_contract"]["action_state"][action][state])
def enpv(action,prob,r=None,pm=1,cm=1,om=1):
    r=cfg["discount_rate_real"] if r is None else r
    return sum(prob[s]*npv(action,s,r,pm,cm,om) for s in prob)
p=cfg["decision"]["state_probabilities"];actions=list(cfg["cashflow_contract"]["action_state"])
if set(actions)!={"no_drill","pilot","full"} or any(set(cfg["cashflow_contract"]["action_state"][a])!={"dry","ore"} or any(not cfg["cashflow_contract"]["action_state"][a][s] for s in ("dry","ore")) for a in actions):raise SystemExit("cashflow set")
if any(cfg["cashflow_contract"][k]!=1 for k in ("price_multiplier","capex_multiplier","opex_multiplier")):raise SystemExit("base multiplier")
vals={a:enpv(a,p) for a in actions}
for a,v in vals.items():close(raw["decision"]["enpv"][a],v)
expected_sens={}
for v in cfg["cashflow_contract"]["sensitivity"]["discount_rate"]:expected_sens[f"r_{float(v):.15g}"]=max(enpv(a,p,v) for a in actions)
for v in cfg["cashflow_contract"]["sensitivity"]["price_multiplier"]:expected_sens[f"price_{float(v):.15g}"]=max(enpv(a,p,pm=v) for a in actions)
for v in cfg["cashflow_contract"]["sensitivity"]["capex_multiplier"]:expected_sens[f"capex_{float(v):.15g}"]=max(enpv(a,p,cm=v) for a in actions)
for v in cfg["cashflow_contract"]["sensitivity"]["opex_multiplier"]:expected_sens[f"opex_{float(v):.15g}"]=max(enpv(a,p,om=v) for a in actions)
for k,v in expected_sens.items():close(raw["decision"]["sensitivity"][k],v)
if any(type(ct[k]) is not int for k in ("nested_mc_seed","nested_mc_budget","nested_mc_max_budget","nested_mc_total_budget")) or mc["seed"]!=ct["nested_mc_seed"] or mc["budget_n"]!=ct["nested_mc_budget"] or mc["budget_2n"]!=2*mc["budget_n"] or not 2<=mc["budget_n"]<=ct["nested_mc_max_budget"] or mc["budget_2n"]>ct["nested_mc_total_budget"] or mc["error_budget_mcse_multiplier"]!=ct["nested_mc_error_budget_mcse_multiplier"] or not math.isfinite(float(ct["nested_mc_error_budget_mcse_multiplier"])) or not mc["common_random_numbers"]:raise SystemExit("mc contract")
base_action=sorted(a for a,v in vals.items() if abs(v-max(vals.values()))<=1e-10)[0]
choices={}
for y,lik in cfg["decision"]["survey"]["outcomes"].items():
    py=sum(p[s]*lik[s] for s in p);postp={s:p[s]*lik[s]/py for s in p}
    cv={a:enpv(a,postp) for a in actions};choices[y]=sorted(a for a,v in cv.items() if abs(v-max(cv.values()))<=1e-10)[0]
if mc["actions_by_outcome"]!=choices:raise SystemExit("mc posterior action")
seed=mc["seed"]&0xffffffff;inc=[];ys=[];states=[]
for _ in range(mc["budget_2n"]):
    seed=(1664525*seed+1013904223)&0xffffffff;state="dry" if seed/4294967296.0<p["dry"] else "ore"
    seed=(1664525*seed+1013904223)&0xffffffff;y="positive" if seed/4294967296.0<cfg["decision"]["survey"]["outcomes"]["positive"][state] else "negative"
    inc.append(npv(choices[y],state,cfg["discount_rate_real"])-npv(base_action,state,cfg["discount_rate_real"]));ys.append(y);states.append(state)
def sample_policy(count):
    out={}
    for y in ("positive","negative"):
        values={a:sum(npv(a,states[i],cfg["discount_rate_real"]) for i in range(count) if ys[i]==y)/sum(ys[i]==y for i in range(count)) for a in actions}
        out[y]=sorted(a for a,v in values.items() if abs(v-max(values.values()))<=ct["decision_tie_absolute_tolerance"])[0]
    return out
if mc["best_actions_n"]!=sample_policy(mc["budget_n"]) or mc["best_actions_2n"]!=sample_policy(mc["budget_2n"]) or mc["best_actions_n"]!=mc["best_actions_2n"] or mc["best_actions_2n"]!=choices:raise SystemExit("mc stability")
for group,count in (("at_n",mc["budget_n"]),("at_2n",mc["budget_2n"])):
    z=inc[:count];mean=sum(z)/count;se=math.sqrt(sum((v-mean)**2 for v in z)/(count-1)/count)
    close(mc[group]["gross_evsi"],mean);close(mc[group]["net_evsi"],mean-cfg["decision"]["survey"]["cost"]);close(mc[group]["mcse"],se)
    if mc[group]["outcome_counts"]!={"positive":ys[:count].count("positive"),"negative":ys[:count].count("negative")}:raise SystemExit("mc outcome prefix")
tol=raw["decision"]["tie_absolute_tolerance"];candidates=sorted(a for a,v in vals.items() if abs(v-max(vals.values()))<=tol)
if raw["decision"]["tie_rule"]!="ordinal_action_name_ascending" or raw["decision"]["best_action"]!=candidates[0]:raise SystemExit("tie")
base=max(vals.values());perfect=sum(p[s]*max(enpv(a,{s:1.0}) for a in actions) for s in p);close(raw["decision"]["evpi"],perfect-base)
survey=cfg["decision"]["survey"];post=0.0
for lik in survey["outcomes"].values():
    py=sum(p[s]*lik[s] for s in p);pp={s:p[s]*lik[s]/py for s in p};post+=py*max(enpv(a,pp) for a in actions)
evsi=post-base;close(raw["decision"]["evsi"],evsi);close(raw["decision"]["net_evsi"],evsi-survey["cost"]);close(mc["exact_gross_evsi"],evsi);close(mc["exact_net_evsi"],evsi-survey["cost"])
for group in ("at_n","at_2n"):
    product=mc["error_budget_mcse_multiplier"]*mc[group]["mcse"]
    if not math.isfinite(float(mc[group]["mcse"])) or not math.isfinite(product):raise SystemExit("nonfinite mc error budget")
    if abs(mc[group]["gross_evsi"]-evsi)>product+1e-12:raise SystemExit("mc exact error budget")
if not mc["stable"]:raise SystemExit("mc stability")

rows=cfg["replay"]["rows"]
if len({r["id"] for r in rows})!=len(rows) or any(not canonical(r["id"]) or not canonical(r["cluster_id"]) for r in rows):raise SystemExit("replay id")
if any("probability" in r or "score" in r for r in rows):raise SystemExit("external prediction")
seen={}
for r in rows:
    if r["cluster_id"] in seen and seen[r["cluster_id"]]!=r["split"]:raise SystemExit("cluster leakage")
    seen[r["cluster_id"]]=r["split"]
train=[r for r in rows if r["split"]=="train"];ra,rb,ri=logistic_fit([(r["feature"],r["event"]) for r in train])
rm=raw["replay"]["raw_model"];close(rm["intercept"],ra);close(rm["slope"],rb)
if rm["feature"]!="feature" or rm["train_row_ids"]!=[r["id"] for r in train] or rm["train_cluster_ids"]!=[r["cluster_id"] for r in train]:raise SystemExit("raw lineage")
cal=[r for r in rows if r["split"]=="calibration"];ca,cb,ci=logistic_fit([(ra+rb*r["feature"],r["event"]) for r in cal])
cm=raw["replay"]["calibration_model"];close(cm["intercept"],ca);close(cm["slope"],cb)
cal_predictions=[]
for r in cal:
    score=ra+rb*r["feature"];cal_predictions.append(dict(event=r["event"],probability=1/(1+math.exp(-(ca+cb*score)))))
candidates=sorted(cfg["replay"]["threshold_candidates"]);scores={};best_threshold=None;best_score=-math.inf
for candidate in candidates:
    tp=sum(r["probability"]>=candidate and r["event"]==1 for r in cal_predictions);fp=sum(r["probability"]>=candidate and r["event"]==0 for r in cal_predictions)
    score=tp/len(cal_predictions)-fp/len(cal_predictions)*candidate/(1-candidate);scores[format(float(candidate),".17g")]=score
    if score>best_score+1e-15:best_score=score;best_threshold=float(candidate)
ts=raw["replay"]["threshold_selection"]
if ts["selected_on"]!="calibration" or ts["criterion"]!="calibration_net_benefit_max_ordinal_smallest" or ts["candidates"]!=cfg["replay"]["threshold_candidates"]:raise SystemExit("threshold selection metadata")
close(ts["selected_threshold"],best_threshold);close(ts["optimal_value"],best_score);close(raw["replay"]["threshold"],best_threshold)
if set(ts["scores"])!=set(scores):raise SystemExit("threshold score keys")
for key,value in scores.items():close(ts["scores"][key],value)
test=[dict(r,raw_score=ra+rb*r["feature"]) for r in rows if r["split"]=="test"]
for r in test:r["probability"]=1/(1+math.exp(-(ca+cb*r["raw_score"])))
for got,exp in zip(raw["replay"]["test_predictions"],test):
    if got["id"]!=exp["id"] or got["cluster_id"]!=exp["cluster_id"]:raise SystemExit("test lineage")
    for k in ("feature","raw_score","probability","event"):close(got[k],exp[k])
eps=cfg["replay"]["log_epsilon"];rate=sum(r["event"] for r in test)/len(test);brier=sum((r["probability"]-r["event"])**2 for r in test)/len(test)
log=-sum(r["event"]*math.log(max(eps,min(1-eps,r["probability"])))+(1-r["event"])*math.log(max(eps,min(1-eps,1-r["probability"]))) for r in test)/len(test)
close(raw["replay"]["brier"],brier);close(raw["replay"]["log_score"],log);close(raw["replay"]["sharpness"],sum((r["probability"]-rate)**2 for r in test)/len(test))
if "calibration_intercept" in raw["replay"] or "calibration_slope" in raw["replay"]:raise SystemExit("test-fit field")
groups=[]
for cid in sorted({r["cluster_id"] for r in test}):groups.append([r for r in test if r["cluster_id"]==cid])
boot=raw["replay"]["cluster_bootstrap"]
if not 0<len(groups)<=64 or len(test)>10000:raise SystemExit("bootstrap limit")
state=boot["seed"] & 0xffffffff
if state==0 or boot["index_scheme"]!="xorshift32_modulo_cluster_v1" or boot["replicates"]!=256:raise SystemExit("bootstrap contract")
idx=[];values=[]
for _ in range(256):
    ix=[]
    for __ in groups:
        state ^= (state << 13) & 0xffffffff;state ^= state >> 17;state ^= (state << 5) & 0xffffffff;state &= 0xffffffff
        ix.append(state % len(groups))
    idx.append(ix);selected=[r for i in ix for r in groups[i]];values.append(sum((r["probability"]-r["event"])**2 for r in selected)/len(selected))
if boot["n_clusters"]!=len(groups) or boot["indices"]!=[",".join(map(str,x)) for x in idx]:raise SystemExit("bootstrap")
values.sort();close(boot["brier_lo"],values[math.floor(.025*(len(values)-1))]);close(boot["brier_hi"],values[math.floor(.975*(len(values)-1))])
print("PASS oracle")
