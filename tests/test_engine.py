from __future__ import annotations
import copy
import numpy as np
import pytest
from scipy.stats import poisson
from pydantic import ValidationError
from api.schemas import RunRequest, Observation
from engine.sis import coupling_matrix,rhs,rk4_step,delay_index
from engine.filtering import ou_step,snapshot_loglik,incident_loglik,update_weights,systematic_indices
from engine.queueing import queue_step,tagged_ship,invert_hazard,land_completion
from engine.calibration import analytic_land,estimate_gamma,synthetic_observations
from engine.simulation import run_simulation,action_reasons

@pytest.mark.parametrize("t",[1.,2.,4.])
def test_sis_matches_independent_analytic_solution(t):
    x=np.array([[.5,0.]])
    for _ in range(round(t*120)):
        x=rk4_step(x,np.array([.8,.6]),np.array([.4,.9]),coupling_matrix(),1/120)
    assert x[0,0]==pytest.approx(.5,abs=1e-12)
    assert x[0,1]==pytest.approx(float(analytic_land(t)),abs=1e-8)


def test_population_ratio_and_direction_preserved():
    x=np.array([[.3,.1]]);N=np.array([100.,250.]);C=coupling_matrix(2)
    beta=np.array([.8,.6]);gamma=np.array([.4,.9]);I=x*N
    count_rhs=beta*(1-I/N)*(I@C.T)-gamma*I
    assert rhs(x,beta,gamma,C,N)==pytest.approx(count_rhs/N)
    assert C[0,1]==0 and C[1,0]==1


def test_delay_index_is_not_deadline_probability():
    x=np.array([[.5,.0],[.5,.2346]])
    assert delay_index(x,[.8,.6],[.4,.9],coupling_matrix())==pytest.approx([1,1])


def test_sis_zero_and_saturated_boundaries():
    C=coupling_matrix()
    assert np.all(rhs(np.zeros((1,2)),[.8,.6],[.4,.9],C)==0)
    assert np.all(rhs(np.ones((1,2)),[.8,.6],[.4,.9],C)<0)


def test_ou_exact_transition_moments():
    theta=.6;sigma=.3;dt=.4;z=np.full(100000,.2)
    sample=ou_step(z,theta,0.,sigma,dt,np.random.default_rng(74))
    mean=.2*np.exp(-theta*dt)
    var=sigma**2*(1-np.exp(-2*theta*dt))/(2*theta)
    assert abs(sample.mean()-mean)<6*np.sqrt(var/len(z))
    assert sample.var()==pytest.approx(var,rel=.03)


def test_ou_zero_noise_and_seed():
    z=np.array([.2,-.3]);a=ou_step(z,.6,0,0,.5,np.random.default_rng(1))
    assert a==pytest.approx(z*np.exp(-.3))
    assert np.array_equal(ou_step(z,.6,0,.3,.5,np.random.default_rng(2)),
                          ou_step(z,.6,0,.3,.5,np.random.default_rng(2)))


def test_two_particle_hand_calculation():
    ll=snapshot_loglik(6,10,np.array([.2,.6]),10.)
    weights,ess,_=update_weights(np.array([.5,.5]),ll)
    assert weights==pytest.approx([.125,.875],abs=1e-12)
    assert weights@np.array([.2,.6])==pytest.approx(.55,abs=1e-12)
    assert ess==pytest.approx(1.28,abs=1e-12)
    assert not ess<1


def test_bounded_observation_and_degenerate_probabilities():
    assert snapshot_loglik(0,10,np.array([0.]))[0]==0
    assert snapshot_loglik(10,10,np.array([1.]))[0]==0
    assert np.isneginf(snapshot_loglik(1,10,np.array([0.]))[0])
    with pytest.raises(ValueError):snapshot_loglik(11,10,[.2])
    with pytest.raises(ValueError):update_weights([.5,.5],[-np.inf,-np.inf])


def test_incident_zero_mean():
    assert incident_loglik(0,np.array([0.]))[0]==0
    assert np.isneginf(incident_loglik(1,np.array([0.]))[0])


def test_systematic_resampling_reproducible():
    w=np.array([.1,.2,.3,.4])
    a=systematic_indices(w,np.random.default_rng(42))
    b=systematic_indices(w,np.random.default_rng(42))
    assert np.array_equal(a,b) and len(a)==4 and np.all((a>=0)&(a<4))


def test_queue_pure_birth_matches_poisson():
    q=np.zeros((1,22));q[0,0]=1
    result=queue_step(q,1.,0.,2,1.)[0]
    assert result[:21]==pytest.approx(poisson.pmf(np.arange(21),1),abs=2e-13)
    assert result.sum()==pytest.approx(1,abs=1e-12)


def test_overflow_is_absorbing_not_hidden_at_cap():
    q=np.array([[1.,0.,0.,0.]])
    result=queue_step(q,2.,0.,1,1.)
    assert result[0,-1]==pytest.approx(poisson.sf(2,2),abs=1e-12)
    later=queue_step(result,0.,2.,1,.5)
    assert later[0,-1]==pytest.approx(result[0,-1],abs=1e-12)


def test_queue_closed_without_arrivals_has_no_transition():
    q=np.array([[0.,1.,0.,0.]])
    assert np.array_equal(queue_step(q,0.,0.,2,1.),q)


def test_tagged_ship_empty_system_starts_immediately():
    times=np.linspace(0,50,501);hazard=np.tile(2*times,(4,1))
    begin,finish=tagged_ship(times,hazard,np.zeros(4,dtype=int),1.,2,np.random.default_rng(99))
    work=np.random.default_rng(99).exponential(1.,4)
    assert begin==pytest.approx(np.ones(4))
    assert finish==pytest.approx(1.+work/2,abs=1e-12)


def test_target_cannot_complete_during_outage():
    t=np.array([0.,1.,2.,3.,4.]);hazard=np.array([0.,0.,0.,1.,2.])
    assert invert_hazard(t,hazard,.5,earliest=1.)==pytest.approx(2.5)
    assert np.isinf(invert_hazard(t,hazard,3.))


def test_land_event_order_and_no_duplicate_ship_wait():
    t=np.array([0.,1.,2.,3.,4.,5.]);Q=np.array([t*2,t*2])
    start,finish=land_completion(t,Q,np.array([2.,1.]),1.5)
    assert start==pytest.approx([2.,1.5])
    assert finish==pytest.approx([2.5,2.])

@pytest.mark.parametrize("mode,expected",[("clean",.8999322754106104),("noise_a",.9117228389),("noise_b",.8874269136)])
def test_calibration_values_are_recomputed(mode,expected):
    result=estimate_gamma(synthetic_observations(mode))
    assert result["gamma_land_per_h"]==pytest.approx(expected,abs=1e-8)


def test_uninformative_or_invalid_calibration_rejected():
    observations=synthetic_observations()
    for o in observations:o["land_fraction"]=0
    with pytest.raises(ValueError):estimate_gamma(observations)
    observations=synthetic_observations();observations[1]["time_h"]=-1
    with pytest.raises(ValueError):estimate_gamma(observations)


def test_temporal_and_count_input_validation():
    with pytest.raises(ValidationError):Observation(value=21,sample_size=20)
    with pytest.raises(ValidationError):Observation(available_at="2026-10-21T11:00:00+09:00")
    with pytest.raises(ValidationError):RunRequest(particles=1000000)
    with pytest.raises(ValidationError):RunRequest(kappa=float("nan"))


def test_action_constraints_cutoff_boundary():
    a=RunRequest().actions[1].model_dump()
    assert action_reasons(a)==[]
    a["change_cutoff_h"]=2.5-1/60
    assert "변경 확정시간 부족" in action_reasons(a)
    a["reservation"]="unknown"
    assert "예약 미확인" in action_reasons(a)

@pytest.fixture(scope="module")
def base_config():
    return RunRequest(particles=64).model_dump(mode="json")

@pytest.fixture(scope="module")
def base_result(base_config):
    return run_simulation(copy.deepcopy(base_config))


def test_complete_chain_uses_estimated_gamma(base_result):
    r=base_result
    assert r["parameters"]["gamma_per_h"][1]==r["calibration"]["gamma_land_per_h"]
    assert r["queue"]["mass_error"]<1e-10
    assert r["time"]["original_deadline_h"]==8
    assert len(r["candidates"])==3
    assert all(0<=a["risk_lower"]<=a["risk_upper"]<=1 for a in r["candidates"])
    if r["decision"]["action_id"]:
        selected=next(a for a in r["candidates"] if a["id"]==r["decision"]["action_id"])
        assert selected["eligible"] and selected["cost_complete"]


def test_seed_reproduces_full_computation(base_config,base_result):
    again=run_simulation(copy.deepcopy(base_config))
    assert again["reproducibility_sha256"]==base_result["reproducibility_sha256"]


def test_changed_observation_changes_posterior(base_config,base_result):
    c=copy.deepcopy(base_config);c["observation"]["value"]=14
    r=run_simulation(c)
    assert r["filter"]["posterior_mean"][1]>base_result["filter"]["posterior_mean"][1]


def test_absent_observation_not_treated_as_zero(base_config):
    c=copy.deepcopy(base_config);c["observation"]=None
    r=run_simulation(c)
    assert r["filter"]["prior_mean"]==pytest.approx(r["filter"]["posterior_mean"])
    assert r["filter"]["ess"]==64


def test_shutdown_censoring_does_not_fake_completion(base_config):
    c=copy.deepcopy(base_config);c["berth_closed_hours"]=14
    r=run_simulation(c)
    assert r["events"]["ready_censored_mass"]==pytest.approx(1)
    assert r["decision"]["status"]=="calculation_incomplete"
    assert all(a["cost_krw"] is None for a in r["candidates"])
    assert all(a["risk_lower"]==pytest.approx(1) for a in r["candidates"])


def test_all_actions_unknown_never_recommended(base_config):
    c=copy.deepcopy(base_config);c["risk_limit"]=1
    for a in c["actions"]:a["reservation"]="unknown"
    r=run_simulation(c)
    assert r["decision"]["action_id"] is None
    assert all(not a["eligible"] for a in r["candidates"])
