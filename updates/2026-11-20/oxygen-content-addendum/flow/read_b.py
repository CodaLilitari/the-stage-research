"""Post-freeze native readings. Keep isolated marks distinct from overlaps and source rank."""
from pathlib import Path
import hashlib,csv,json
import numpy as np
ROOT=Path(__file__).resolve().parent
LOCK='0423744ec22898c5e8ef0c16c2718202a624bd61a70770042971c72cec970949'
assert hashlib.sha256((ROOT/'conditional-forecast-coefficients.json').read_bytes()).hexdigest()==LOCK
# Increasing native source-image row, highest to lowest flow concentration.
# These are envelopes of four position means, allowing co-located symbols. The
# lower stagnant comparison is a fifth marked series and never a flow position.
RANK=np.array([
 [344,346,355,366,375,380,384,386,386.5,385,384,382,379.5,377,373.5,370,366.5,364,360],
 [345.5,350,357.5,368,381,386,392,396,399,400,401,400,398,395,393,390,387,381,376],
 [351,367,382,388,392,396,397,400,400,401,403,403,403,402,402,399,397,392,387],
 [360.5,376,385,391,397,400,404,408.5,412.5,416,418.5,418,417,414,411,407.5,403.5,397.5,391],
],float)
assert np.all(np.diff(RANK,axis=0)>=0)
axis=np.polyfit([318,358,398,439,478,519],[250,200,150,100,50,0],1)
zs=np.arange(19)*100
# The diagonal tips of the cross can be individually recognized at these depths.
# Crosses in the four central overlap patches are omitted from the named subset.
x_read={0:351,100:367,200:382,300:388,400:392,500:396,600:397,1100:400,1200:398,
        1300:395,1400:393,1500:390,1600:387,1700:381,1800:376}
with (ROOT/'target-readings.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['trace','depth_um','oxygen_umol_per_l','chart_tolerance_umol_per_l','se_umol_per_l'])
    for depth,pixel in x_read.items():
        w.writerow(['position-4-readable-cross',depth,np.polyval(axis,pixel),3.5*abs(axis[0]),''])
with (ROOT/'rank-readings.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['depth_um','rank','marker_y_px','concentration_umol_per_l','tolerance_umol_per_l'])
    for j,z in enumerate(zs):
        for k in range(4):
            w.writerow([z,k+1,RANK[k,j],np.polyval(axis,RANK[k,j]),4.*abs(axis[0])])
print('calibration',axis,'positions',len(x_read),'separate ranks',RANK.shape)
