"""Synthetic end-to-end runtime v0.2.

New berth scenario B: 08:00 origin, a decision at 10:00, a tagged ship arriving
at 11:00, and an ORIGINAL 16:00 delivery deadline. This is deliberately not the
old manually-entered five-state/13:15 example. All alternatives share the same
posterior paths, original deadline, sampled ship and document conditions.
"""
from __future__ import annotations
import hashlib
import json
import numpy as np
from . import __version__
from .sis import coupling_matrix, incidence, rk4_step, delay_index
from .filtering import ou_step, snapshot_loglik, incident_loglik, update_weights, systematic_indices, weighted_quantile
from .queueing import queue_step, cumulative_integral, tagged_ship, land_completion
from .calibration import fit_sample

ORIGIN = "2026-10-21T08:00:00+09:00"
DECISION_H = 2.0
SHIP_ARRIVAL_H = 3.0
DEADLINE_H = 8.0
HORIZON_H = 16.0
STEP_H = 1/60


def _quantiles(values, weights):
    qs = weighted_quantile(values, weights)
    return [None if not np.isfinite(v) else float(v) for v in qs]


def _state_summary(t, x, beta, gamma, C, weights, stage):
    rd = delay_index(x, beta, gamma, C)
    return {"time_h":float(t), "stage":stage,
            "sea":_quantiles(x[:,0],weights), "land":_quantiles(x[:,1],weights),
            "sea_mean":float(weights@x[:,0]),"land_mean":float(weights@x[:,1]),
            "rd":_quantiles(rd,weights), "rd_mean":float(weights@rd)}


def action_reasons(action):
    reasons=[]
    for field,label in (("vehicle","차량"),("reservation","예약"),("approval","승인")):
        if action[field] != "confirmed":
            reasons.append(label + (" 이용 불가" if action[field]=="unavailable" else " 미확인"))
    if action["vehicle_at_h"] < DECISION_H:
        reasons.append("이미 지난 차량 도착시각")
    if action["is_change"]:
        confirmed = DECISION_H + 20/60 + 10/60
        if action["change_cutoff_h"] is None or confirmed > action["change_cutoff_h"]+1e-10:
            reasons.append("변경 확정시간 부족")
        if confirmed + .5 > action["vehicle_at_h"]+1e-10:
            reasons.append("변경 후 터미널 접근시간 부족")
    return reasons


def run_simulation(config: dict) -> dict:
    """Caller validates request with api.schemas.RunRequest before invocation."""
    fit = fit_sample(config["calibration"])
    gamma = np.array([.4, fit["gamma_land_per_h"]])
    C = coupling_matrix(config["kappa"])
    beta_base = np.array([.8,.6])
    count = int(config["particles"])
    streams = np.random.SeedSequence(config["seed"]).spawn(5)
    init_rng, ou_rng, resample_rng, queue_rng, ship_rng = [np.random.default_rng(s) for s in streams]
    x = np.column_stack([init_rng.beta(20,20,count), init_rng.beta(3,47,count)])
    sigma=float(config["ou_sigma"])
    theta=.6
    z=init_rng.normal(0,sigma/np.sqrt(2*theta),(count,2))
    weights=np.full(count,1/count)
    trajectory=[]
    incident=np.zeros((count,2))
    steps_to_decision=round(DECISION_H/STEP_H)
    for k in range(steps_to_decision+1):
        t=k*STEP_H
        beta=beta_base*np.exp(z)
        if k % 15 == 0:
            trajectory.append(_state_summary(t,x,beta,gamma,C,weights,"prior"))
        if k==steps_to_decision:
            break
        next_z=ou_step(z,theta,0.,sigma,STEP_H,ou_rng)
        # Exact OU endpoints, piecewise midpoint beta for numerical SIS RK4.
        beta_mid=beta_base*np.exp(.5*(z+next_z))
        new_x=rk4_step(x,beta_mid,gamma,C,STEP_H)
        incident += .5*(incidence(x,beta_mid,C)+incidence(new_x,beta_mid,C))*STEP_H
        x,z=new_x,next_z
    prior_mean=(weights@x).tolist()
    obs=config.get("observation")
    if obs is None:
        posterior=weights.copy();ess=float(count); evidence=None
        observation_note="관측 누락: 예측 가중치를 유지했습니다. 0건 관측으로 처리하지 않았습니다."
    else:
        j=0 if obs["node"]=="sea" else 1
        if obs["kind"]=="snapshot":
            ll=snapshot_loglik(obs["value"],obs["sample_size"],x[:,j],obs["concentration"])
            observation_note="10:00 현재 지연 표본의 베타-이항 갱신"
        else:
            ll=incident_loglik(obs["value"],incident[:,j],obs["dispersion"])
            observation_note="08:00~10:00 신규 지연 사건의 음이항 갱신; 보고율 1 가정"
        posterior,ess,evidence=update_weights(weights,ll)
    posterior_mean=(posterior@x).tolist()
    posterior_summary=_state_summary(DECISION_H,x,beta_base*np.exp(z),gamma,C,posterior,"posterior")
    filter_report={"observation":obs,"description":observation_note,
                   "prior_mean":prior_mean,"posterior_mean":posterior_mean,
                   "weights":posterior.tolist(),"ess":ess,"resampling_threshold":count/2,
                   "resampled":ess<count/2,"log_evidence":evidence,
                   "summary_stage":"weighted posterior BEFORE resampling"}
    if ess < count/2:
        ancestors=systematic_indices(posterior,resample_rng)
        x=x[ancestors].copy();z=z[ancestors].copy()
        weights=np.full(count,1/count)
    else:
        ancestors=np.arange(count);weights=posterior
    filter_report["ancestor_indices"]=ancestors.tolist()
    # At 10:00 the queue size is assumed directly known, not inferred from SIS.
    # There is no untracked queue history before this reset point in v0.2.
    trajectory.append(posterior_summary)
    times=np.arange(round((HORIZON_H-DECISION_H)/STEP_H)+1)*STEP_H+DECISION_H
    sea=np.empty((count,len(times)));land=np.empty_like(sea)
    sea[:,0]=x[:,0];land[:,0]=x[:,1]
    for k in range(1,len(times)):
        next_z=ou_step(z,theta,0.,sigma,STEP_H,ou_rng)
        beta_mid=beta_base*np.exp(.5*(z+next_z))
        x=rk4_step(x,beta_mid,gamma,C,STEP_H)
        z=next_z
        sea[:,k]=x[:,0];land[:,k]=x[:,1]
        if k%15==0:
            trajectory.append(_state_summary(times[k],x,beta_base*np.exp(z),gamma,C,weights,"forecast"))
    service=1.5*np.exp(-.8*sea)
    closure_end=DECISION_H+config["berth_closed_hours"]
    # Rates are left-constant on 1-minute intervals; this represents a known
    # shutdown/reopening schedule, not a forecast of a typhoon.
    service[:,times<closure_end-1e-10]=0
    dt=np.diff(times)
    berth_hazard=np.concatenate([np.zeros((count,1)),np.cumsum(service[:,:-1]*dt[None,:],axis=1)],axis=1)
    land_work=cumulative_integral(times,(1-.8*land)/.5)
    cap=int(config["queue_cap"])
    queue=np.zeros((count,cap+2));queue[:,config["initial_ships_at_decision"]]=1
    arrival_index=round((SHIP_ARRIVAL_H-DECISION_H)/STEP_H)
    for k in range(arrival_index):
        queue=queue_step(queue,.4,service[:,k],2,STEP_H)
    queue_mixture=weights@queue
    overflow_probability=float(queue_mixture[-1])
    uniforms=queue_rng.random(count)
    state=(np.cumsum(queue,axis=1)<uniforms[:,None]).sum(axis=1)
    overflow_samples=state>cap
    state[overflow_samples]=-1
    ship_start,ship_finish=tagged_ship(times,berth_hazard,state,SHIP_ARRIVAL_H,2,ship_rng)
    # Transfer=.25h; documents ready at 11:15. Added assumptions, not observations.
    ready=np.maximum(ship_finish+.25,3.25)
    censored_ready=~np.isfinite(ready)
    sample_unknown=float(weights@overflow_samples.astype(float))
    ready_censored_mass=float(weights@censored_ready.astype(float))
    warnings=[]
    if overflow_probability>1e-6:
        warnings.append("QUEUE_OVERFLOW: 상태 범위를 넘어갈 확률이 큽니다. 추천을 보류합니다.")
    if ready_censored_mass>1e-12:
        warnings.append("COST_CENSORED: 계산 종료까지 준비되지 않은 표본이 있어 총 대기비용을 확정하지 않습니다.")
    if obs is None:
        warnings.append("NO_OBSERVATION: 관측 없이 사전 예측만 사용했습니다.")
    candidates=[]
    for a in config["actions"]:
        reasons=action_reasons(a)
        start,gate=land_completion(times,land_work,ready,a["vehicle_at_h"])
        arrival=gate+1.5
        # Noncompletion by a horizon later than the fixed deadline is a known
        # miss; overflow paths are unknown and receive a probability bound.
        missed=arrival>DEADLINE_H
        risk_lower=float(weights@(missed & ~overflow_samples))
        risk_upper=min(1.,risk_lower+sample_unknown)
        wait_partial=np.maximum(np.minimum(ready,HORIZON_H)-a["vehicle_at_h"],0)
        wait_partial[overflow_samples]=0 # conservative lower bound on unknown paths
        expected_partial=float(weights@wait_partial)
        cost_lower=float(a["change_fee_krw"]+30000*expected_partial+600000*risk_lower)
        cost_complete=ready_censored_mass<1e-12 and overflow_probability<=1e-6
        executable=len(reasons)==0
        eligible=executable and cost_complete and risk_upper<=config["risk_limit"]+1e-12
        candidates.append({**a,"risk_lower":risk_lower,"risk_upper":risk_upper,
            "mean_wait_minutes_lower":60*expected_partial,
            "cost_krw":cost_lower if cost_complete else None,"cost_lower_krw":cost_lower,
            "cost_complete":cost_complete,"executable":executable,"eligible":eligible,
            "reasons":reasons,"arrival_quantiles_h":_quantiles(arrival,weights),
            "noncompletion_probability":float(weights@(~np.isfinite(arrival))),
            "conditional_only":not executable})
    eligible=[a for a in candidates if a["eligible"]]
    best=min(eligible,key=lambda a:(a["cost_krw"],a["risk_upper"],a["id"])) if eligible else None
    if best:
        decision={"status":"recommended","action_id":best["id"],"label":best["label"],
                  "message":"입력된 합성 조건에서 위험·실행기준을 충족한 최소 비교비용 후보"}
    elif ready_censored_mass>1e-12 or overflow_probability>1e-6:
        decision={"status":"calculation_incomplete","action_id":None,"label":"비용 계산 미완결",
                  "message":"기간 밖 준비 또는 대기열 넘침이 있어 확정 추천하지 않습니다."}
    elif not any(a["executable"] for a in candidates):
        decision={"status":"confirmation_required","action_id":None,"label":"실행조건 확인 필요",
                  "message":"차량·예약·승인·변경 시간을 확인한 후보가 없습니다."}
    else:
        decision={"status":"no_acceptable_action","action_id":None,"label":"기준 충족 후보 없음",
                  "message":"실행 가능한 후보 중 원래 마감위험 기준을 충족한 후보가 없습니다."}
    result={"model_version":__version__,"data_type":"synthetic","scenario":"B / synthetic berth-to-road",
        "time":{"origin":ORIGIN,"decision_h":DECISION_H,"ship_arrival_h":SHIP_ARRIVAL_H,
                "original_deadline_h":DEADLINE_H,"horizon_h":HORIZON_H,"step_h":STEP_H},
        "parameters":{"population":[100,100],"base_beta_per_h":beta_base.tolist(),
            "gamma_per_h":gamma.tolist(),"C":C.tolist(),"ou_theta_per_h":theta,
            "ou_sigma_per_sqrt_h":sigma,"berth_servers":2,"arrival_rate_per_h":.4,
            "normal_berth_service_per_h":1.5,"berth_delay_effect":.8,
            "land_base_handling_h":.5,"land_delay_effect":.8,"road_h":1.5,
            "wait_cost_krw_per_h":30000,"miss_cost_krw":600000},
        "calibration":fit,"filter":filter_report,"trajectory":trajectory,
        "queue":{"initial_ships_at_decision":config["initial_ships_at_decision"],
            "finite_states":list(range(cap+1)),"probabilities":queue_mixture[:-1].tolist(),
            "overflow_probability":overflow_probability,"cap":cap,
            "sample_overflow_weight":sample_unknown,"mass_error":float(abs(queue_mixture.sum()-1)),
            "assumptions":"FCFS, identical exponential servers, known initial count at 10:00, target inserted once at 11:00"},
        "events":{"ship_start_quantiles_h":_quantiles(ship_start,weights),
            "ship_finish_quantiles_h":_quantiles(ship_finish,weights),
            "ready_quantiles_h":_quantiles(ready,weights),"ready_censored_mass":ready_censored_mass},
        "candidates":candidates,"decision":decision,"warnings":warnings,
        "uncertainty_note":"Weighted empirical quantiles and conditional Monte Carlo probabilities; not field-calibrated confidence bounds. Resampling ancestry causes dependence.",
        "implementation_limits":["one on-time observation at 10:00; no late-observation replay",
          "queue size at decision assumed known; no queue-observation assimilation",
          "constant gamma calibration only; exogenous-variable ML not yet implemented",
          "no real customers, real data feeds, dispatch execution, public deployment or field validation"],
        "input":config}
    encoded=json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()
    result["reproducibility_sha256"]=hashlib.sha256(encoded).hexdigest()
    return result
