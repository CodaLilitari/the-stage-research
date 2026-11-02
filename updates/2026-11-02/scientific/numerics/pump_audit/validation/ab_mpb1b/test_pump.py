# SPDX-License-Identifier: Apache-2.0
# Frozen assertions by Coda (Codex Lily), before pump implementation.
from dataclasses import replace
from decimal import Decimal,localcontext
import math,unittest
from admitted import A,A_ROWS,DESIGN,initial,verify_a
import pump

def independent_flow(r,d,p):
    # Bisection of feasibility inequalities; no production helper or sqrt.
    if d==0 or p==0:return 0.0
    with localcontext() as context:
        context.prec=70
        rr,dd,pp=(Decimal(str(x)) for x in (r,d,p))
        lo=Decimal(0);hi=dd/rr
        for _ in range(80):
            middle=(lo+hi)/2
            if rr*middle<=dd and rr*middle*middle<=pp:lo=middle
            else:hi=middle
        return float((lo+hi)/2)

class PumpTests(unittest.TestCase):
    def check_point(self,r,q,pressure,power,active):
        got=pump.operating_point(r)
        for key,want in [('flow_ml_s',q),('actual_pressure_kpa',pressure),('actual_hydraulic_power_mw',power)]:
            self.assertAlmostEqual(got[key],want,delta=2e-14)
        self.assertEqual(got['active_constraint'],active)
    def test_power_limited_r20(self):self.check_point(20,.4,8,3.2,'power')
    def test_pressure_limited_r80(self):self.check_point(80,.15,12,1.8,'pressure')
    def test_transition_r45(self):self.check_point(45,4/15,12,3.2,'both')
    def test_zero_caps(self):
        for r in (1,20,80):
            for d,p in ((0,3.2),(12,0),(0,0)):
                with self.subTest(r=r,d=d,p=p):
                    got=pump.operating_point(r,pump.PumpCaps(d,p))
                    self.assertEqual((got['flow_ml_s'],got['actual_pressure_kpa'],got['actual_hydraulic_power_mw']),(0,0,0))
                    self.assertEqual(got['active_constraint'],'zero')
    def test_invalid_domain(self):
        bad=(True,'20',-1,float('inf'),float('nan'),None)
        for value in (0,)+bad:
            with self.subTest(r=value):
                with self.assertRaises(ValueError):pump.operating_point(value)
        with self.assertRaises(ValueError):pump.operating_point(0,pump.PumpCaps(0,0))
        for value in bad:
            for d,p in ((value,3.2),(12,value)):
                with self.subTest(d=d,p=p):
                    with self.assertRaises(ValueError):pump.operating_point(20,pump.PumpCaps(d,p))
    def test_unrepresentable_positive_flow_rejected(self):
        with self.assertRaises(ValueError):pump.operating_point(1e308,pump.PumpCaps(5e-324,1))
    def test_independent_decimal_feasibility_bisection(self):
        for r in (1,7,20,45,80):
            for d in (0,1,12):
                for p in (0,.3,3.2):
                    with self.subTest(r=r,d=d,p=p):
                        want=independent_flow(r,d,p);got=pump.operating_point(r,pump.PumpCaps(d,p))
                        self.assertAlmostEqual(got['flow_ml_s'],want,delta=3e-14*max(1,want))
    def test_monotonic_resistance_and_caps(self):
        flows=[pump.operating_point(r)['flow_ml_s'] for r in (1,10,20,40,45,80,200)]
        self.assertTrue(all(a>=b for a,b in zip(flows,flows[1:])))
        self.assertGreater(flows[0],flows[-1])
        for r in (20,45,80):
            ds=[pump.operating_point(r,pump.PumpCaps(d,3.2))['flow_ml_s'] for d in (0,1,6,12,24)]
            ps=[pump.operating_point(r,pump.PumpCaps(12,p))['flow_ml_s'] for p in (0,.1,1,3.2,10)]
            for seq in (ds,ps):self.assertTrue(all(a<=b for a,b in zip(seq,seq[1:])))
    def test_dimensionally_consistent_scaling(self):
        for r in (20,45,80):
            one=pump.operating_point(r);ten=pump.operating_point(10*r,pump.PumpCaps(120,32))
            self.assertAlmostEqual(one['flow_ml_s'],ten['flow_ml_s'],delta=3e-14)
            for key in ('actual_pressure_kpa','actual_hydraulic_power_mw'):self.assertTrue(math.isclose(10*one[key],ten[key],rel_tol=3e-14,abs_tol=3e-14))
    def test_constraints_feasible_and_active(self):
        for r in (1,7,20,40,45,80,200):
            got=pump.operating_point(r);q=got['flow_ml_s']
            self.assertLessEqual(r*q,12*(1+3e-14));self.assertLessEqual(r*q*q,3.2*(1+3e-14))
            self.assertTrue(math.isclose(r*q,12,rel_tol=3e-14) or math.isclose(r*q*q,3.2,rel_tol=3e-14))
        self.assertLess(pump.operating_point(20)['actual_pressure_kpa'],12)
        self.assertLess(pump.operating_point(80)['actual_hydraulic_power_mw'],3.2)
    def test_nine_matched_flow_A_reductions(self):
        for row in A_ROWS:
            with self.subTest(condition=row['condition'],time=row['time_s']):
                config=A.Config(**row['configuration'])
                cond=next(c for c in DESIGN['conditions'] if c['name']==row['condition'])
                model,values=initial(config,cond)
                got=pump.solve_pumped(config,values,row['time_s'],.01,20)
                self.assertLessEqual(max(abs(a-b) for a,b in zip(got['result']['amounts'],row['final_amounts'])),2e-14)
                self.assertAlmostEqual(got['result']['steps']*got['result']['actual_dt'],row['time_s'],delta=1e-12)
    def test_zero_flow_circulation_control(self):
        c=A.Config(channel_cells=1,exchange=0,kon=0,koff=0,sink=0);m=A.build(c)
        y=A.state(m,[3,0],[0,0],[0,0],[0])
        got=pump.solve_pumped(c,y,3,.002,20,pump.PumpCaps(0,3.2))
        self.assertEqual(got['result']['amounts'],y)
        moving=pump.solve_pumped(c,y,3,.002,20)
        self.assertLess(moving['result']['amounts'][0],3)
        self.assertAlmostEqual(moving['result']['amounts'][0],2+math.exp(-1.8),delta=2e-7)
    def test_mesh_independence_and_flow_override(self):
        for count in (1,3,16):
            c=A.Config(channel_cells=count,flow=9);m=A.build(c);y=A.uniform_state(m)
            got=pump.solve_pumped(c,y,0,.01,20)
            self.assertAlmostEqual(got['configuration']['flow'],.4,delta=2e-15)
            self.assertEqual(got['pump']['resistance_kpa_s_per_ml'],20)
    def test_pumped_inventory_uniform_site_field(self):
        c=A.Config(return_volume=.7,return_cells=2);m=A.build(c);y=A.uniform_state(m,.8,1,2/3)
        got=pump.solve_pumped(c,y,5,.01,40)['result'];values=got['amounts']
        self.assertLess(got['max_oxygen_error'],1e-11);self.assertLess(got['max_site_error'],1e-11);self.assertGreaterEqual(got['minimum_seen'],-1e-14)
        for i,v in enumerate(m.volumes):self.assertAlmostEqual((values[m.n+i]+values[2*m.n+i])/v,1,delta=1e-11)
    def test_initial_inventory_and_partition_controls(self):
        c=A.Config(**DESIGN['configuration'])
        for cond in DESIGN['conditions']:
            m,y=initial(c,cond);oxygen,sites=A.inventories(m,y)
            self.assertAlmostEqual(oxygen,cond['expected_oxygen_umol'],delta=1e-13)
            self.assertAlmostEqual(sites,cond['expected_sites_umol'],delta=1e-13)
            self.assertAlmostEqual(math.fsum(y[:m.n]),3*cond['free_concentration'],delta=1e-13)
            self.assertAlmostEqual(math.fsum(y[m.n:2*m.n]),sites*cond['bound_fraction'],delta=1e-13)
    def test_wrong_model_witnesses(self):
        wrong_max=max(12/80,math.sqrt(3.2/80));self.assertGreater(80*wrong_max,12)
        wrong_linear=3.2/20;self.assertGreater(abs(wrong_linear-pump.operating_point(20)['flow_ml_s']),.1)
        wrong_mesh=pump.operating_point(20*3)['flow_ml_s'];right=pump.operating_point(20)['flow_ml_s']
        self.assertGreater(abs(wrong_mesh-right),.1)
    def test_all_admitted_A_files_unchanged(self):self.assertEqual(verify_a(),33)

if __name__=='__main__':unittest.main()
