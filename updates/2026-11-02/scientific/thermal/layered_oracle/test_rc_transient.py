"""Acceptance tests precede implementation. Read prior reference; never import Fable."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module
prior=load("prior_reference",HERE.parent/"thermal"/"thermal_reference.py")
model=load("rc_transient",HERE/"rc_transient.py") if (HERE/"rc_transient.py").exists() else None

class ThermalAcceptance(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(model,"Implementation absent: tests were declared first.")

    def params(self,**changes):
        values=dict(ch=20.,cs=5.,g=1.,ga=.1,gr=.5,ambient=25.,reservoir=25.,rconv=5.)
        values.update(changes)
        return model.Parameters(**values)

    def test_uniform_zero_power(self):
        r=model.simulate(self.params(),(25.,25.),[dict(duration=10.,p=0.,j=0.)],1.)
        self.assertLess(max(abs(x[k]-25.) for x in r["trace"] for k in ("H","S")),1e-11)

    def test_exact_one_node_limit_and_order(self):
        p=self.params(ch=10.,cs=7.,g=0.,ga=1.,gr=.5,ambient=20.,reservoir=20.,rconv=.5)
        exact=26-6/math.e
        errors=[]
        for dt in (1.,.5,.25):
            r=model.simulate(p,(20.,20.),[dict(duration=20.,p=3.,j=0.)],dt)
            errors.append(abs(r["trace"][-1]["H"]-exact))
            self.assertAlmostEqual(r["trace"][-1]["S"],20.,delta=1e-11)
        self.assertLess(errors[1],.05)
        for a,b in zip(errors,errors[1:]): self.assertTrue(1.8<a/b<2.1)

    def test_coupled_exact_modes(self):
        p=self.params(ch=1.,cs=1.,g=1.,ga=1.,gr=1.,ambient=0.,reservoir=0.,rconv=.5)
        expected=((math.exp(-1)+math.exp(-3))/2,(math.exp(-1)-math.exp(-3))/2)
        errors=[]
        for dt in (.1,.05,.025):
            r=model.simulate(p,(1.,0.),[dict(duration=1.,p=0.,j=0.)],dt)
            x=r["trace"][-1]
            errors.append(max(abs(x["H"]-expected[0]),abs(x["S"]-expected[1])))
        for a,b in zip(errors,errors[1:]): self.assertTrue(1.7<a/b<2.2)

    def test_material_capacities(self):
        for stack,want in (("H1",16.2239),("H2",31.6739),("H3",62.5739)):
            self.assertAlmostEqual(model.nominal(stack).cs,want,delta=1e-10)

    def test_long_time_rational_equilibrium(self):
        for stack in ("H1","H2","H3"):
            with self.subTest(stack=stack):
                want=prior.nominal(stack,5)
                r=model.simulate(model.nominal(stack),(25.,25.),[dict(duration=10000.,p=5.,j=.1)],10.)
                for k in ("H","S"): self.assertAlmostEqual(r["trace"][-1][k],float(want[k]),delta=1e-9)

    def test_equilibrium_is_fixed_point(self):
        p=model.nominal("H1"); want=prior.nominal("H1",5)
        r=model.simulate(p,(float(want["H"]),float(want["S"])),[dict(duration=100.,p=5.,j=.1)],2.)
        for row in r["trace"]:
            for k in ("H","S"): self.assertAlmostEqual(row[k],float(want[k]),delta=1e-10)

    def test_insulated_inventory(self):
        p=self.params(ch=2.,cs=3.,g=1.,ga=0.,gr=0.,rconv=0.)
        r=model.simulate(p,(30.,10.),[dict(duration=10.,p=1.,j=.1)],.25)
        last=r["trace"][-1]
        self.assertAlmostEqual(2*last["H"]+3*last["S"]-90,11,delta=1e-10)
        self.assertEqual(last["front"],0.); self.assertEqual(last["rear"],0.)

    def test_energy_reconstructed_from_trace(self):
        p=model.nominal("H2")
        r=model.simulate(p,(25.,25.),[dict(duration=60.,p=5.,j=.1),dict(duration=30.,p=0.,j=.1,gr=0.)],.5)
        terms=[]
        for row in r["trace"][1:]:
            terms.append(row["dt"]*(row["p"]+row["j"]-row["front"]-row["rear"]))
        last=r["trace"][-1]
        dE=p.ch*(last["H"]-25)+p.cs*(last["S"]-25)
        self.assertAlmostEqual(dE,math.fsum(terms),delta=1e-8)
        self.assertLess(r["max_energy_residual_abs_J"],r["energy_tolerance_J"])

    def test_reverse_reservoir_flux_is_not_clipped(self):
        p=self.params(ambient=0.,reservoir=10.,ga=1.,gr=1.,rconv=.5)
        r=model.simulate(p,(0.,0.),[dict(duration=1.,p=0.,j=0.)],.1)
        self.assertLess(r["trace"][1]["rear"],0.)
        self.assertGreater(r["trace"][-1]["H"],0.)
        self.assertLess(r["max_energy_residual_abs_J"],r["energy_tolerance_J"])

    def test_rear_loss_event_continuity(self):
        p=model.nominal("H1")
        schedule=[dict(duration=600.,p=5.,j=.1),dict(duration=300.,p=5.,j=.1,gr=0.)]
        loss=model.simulate(p,(25.,25.),schedule,1.)
        intact=model.simulate(p,(25.,25.),[dict(duration=900.,p=5.,j=.1)],1.)
        ev=loss["events"][1]
        self.assertEqual(ev["time"],600.)
        self.assertEqual(ev["before_state"],ev["after_state"])
        self.assertEqual(loss["trace"][601]["rear"],0.)
        for k in ("H","S"): self.assertGreater(loss["trace"][-1][k],intact["trace"][-1][k])

    def test_sensor_self_heating_and_location(self):
        p=model.nominal("H1")
        want=prior.steady(1/p.g,1/p.ga,1/p.gr,0,.1,25,25,p.rconv)
        r=model.simulate(p,(25.,25.),[dict(duration=10000.,p=0.,j=.1)],10.)
        for k in ("H","S"):
            self.assertAlmostEqual(r["trace"][-1][k],float(want[k]),delta=1e-9)
            self.assertGreater(r["trace"][-1][k],25)
        self.assertGreater(r["trace"][-1]["S"],r["trace"][-1]["H"])

    def test_fault_temporal_convergence(self):
        p=model.nominal("H1")
        seg=[dict(duration=600.,p=5.,j=.1),dict(duration=300.,p=5.,j=.1,gr=0.),dict(duration=2700.,p=0.,j=.1,gr=0.)]
        traces=[model.simulate(p,(25.,25.),seg,dt)["trace"] for dt in (1.,.5,.25)]
        differences=[]
        for coarse,fine in zip(traces,traces[1:]):
            differences.append(max(abs(a[k]-fine[2*i][k]) for i,a in enumerate(coarse) for k in ("H","S")))
        self.assertLess(differences[1],.05)
        self.assertLess(differences[1],differences[0])

    def test_every_parameter_rejects_nonfinite(self):
        fields=("ch","cs","g","ga","gr","ambient","reservoir","rconv")
        for field in fields:
            for bad in (math.nan,math.inf,-math.inf,True,"1"):
                with self.subTest(field=field,bad=bad),self.assertRaises(ValueError): self.params(**{field:bad})

    def test_invalid_physical_parameters(self):
        for field,bad in (("ch",0),("cs",-1),("g",-1),("ga",-1),("gr",-1),("rconv",-1),("rconv",11)):
            with self.subTest(field=field),self.assertRaises(ValueError): self.params(**{field:bad})

    def test_source_bounds_and_nonfinite(self):
        for field,bad in (("p",11),("p",-1),("j",.3),("j",-1),("p",math.nan),("j",math.inf)):
            segment=dict(duration=1.,p=1.,j=.1);segment[field]=bad
            with self.subTest(field=field,bad=bad),self.assertRaises(ValueError):
                model.simulate(self.params(),(25.,25.),[segment],1.)

    def test_time_state_and_workload_guards(self):
        for dt in (0.,-1.,math.nan,math.inf,True):
            with self.subTest(dt=dt),self.assertRaises(ValueError):
                model.simulate(self.params(),(25.,25.),[dict(duration=1.,p=1.,j=.1)],dt)
        for duration in (0.,-1.,math.nan,math.inf):
            with self.subTest(duration=duration),self.assertRaises(ValueError):
                model.simulate(self.params(),(25.,25.),[dict(duration=duration,p=1.,j=.1)],1.)
        with self.assertRaises(ValueError): model.simulate(self.params(),(math.nan,25.),[dict(duration=1.,p=1.,j=.1)],1.)
        with self.assertRaises(ValueError): model.simulate(self.params(),(25.,25.),[dict(duration=1e9,p=1.,j=.1)],.1)

    def test_fault_parameter_admission(self):
        for bad in (-1.,math.nan,math.inf):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                model.simulate(self.params(),(25.,25.),[dict(duration=1.,p=1.,j=.1,gr=bad)],1.)

if __name__=="__main__":
    phase=sys.argv[1] if len(sys.argv)>1 else "green"
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(ThermalAcceptance))
    record=dict(phase=phase,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),
                first_failure=result.failures[0][1].splitlines()[-1] if result.failures else None,
                failed_tests=[str(t) for t,_ in result.failures],fable_response_read=False)
    (HERE/(phase+"_results.json")).write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(record))
    sys.exit(0 if result.wasSuccessful() else 1)
