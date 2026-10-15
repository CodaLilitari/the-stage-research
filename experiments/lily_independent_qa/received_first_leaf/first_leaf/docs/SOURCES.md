# Selected current primary sources and read depth

Checks performed on 15 October 2026. These are narrow source checks, not an exhaustive literature review or independent replication. URLs identify public primary material. Supplied-document references F1 and F2 are defined in `COVERAGE_AND_ATTRIBUTION.md`. Proposed architecture and experiment rules are Lilitari's analysis unless explicitly described as reported results from a source.

| ID | Primary source | Read depth and use | Limit |
|---|---|---|---|
| S1 | Ahn et al., *Do As I Can, Not As I Say: Grounding Language in Robotic Affordances* | Author project page: abstract, approach, task/skill feasibility combination, results framing, and feedback limitation | No replication; no claim that this package implements SayCan |
| S2 | Kumar, Fu, Pathak, Malik, *RMA: Rapid Motor Adaptation for Legged Robots*, 2021 | arXiv abstract and author project description; base-policy/adaptation split and reported quadruped deployment | No full training or hardware study reproduced |
| S3 | Cully, Clune, Tarapore, Mouret, *Robots that can adapt like animals*, 2015 | arXiv abstract and author/publisher metadata; behavior repertoire guiding later damage adaptation | No reanalysis of original robot data |
| S4 | Hafner et al., *Mastering Diverse Domains through World Models* / DreamerV3 | arXiv abstract and author project/repository description; learned predictive models and behavior learning | Publisher full-text opening was unsuccessful; no claim of a complete methods read or local Dreamer training |
| S5 | Adams and MacKay, *Bayesian Online Changepoint Detection*, 2007 | arXiv abstract and methodological description; possible regime-duration reasoning | Current code is a windowed mean, not this algorithm |
| S6 | Google DeepMind, MuJoCo Python and simulation documentation; canonical PyPI 3.3.7 page | Installation/bundled engine, Apache 2.0 and third-party notices, stepping, state components, integration-state get/set and reproducibility passages; pinned wheel availability and expected digest | Stable docs may evolve independently of the pinned release; download failed; no runtime validation |
| S7 | Farama Foundation, Gymnasium official repository | Environment API, installation, versioning, and MIT license designation | Not installed or benchmarked here |
| S8 | Bullet Physics official repository and LICENSE.txt | Project purpose and explicit zlib license with Extras and third-party exceptions | No local installation; not a full audit of all model assets |
| S9 | Cyberbotics Webots official repository | Robot-development environment description, downloadable distribution, Apache 2.0 designation | Direct documentation page was JavaScript-limited; repository supports the narrowed claim; no benchmark |
| S10 | Isaac Lab official repository | Framework/workflow description, supported-version distinctions, BSD-3 core, Apache 2.0 mimic, dependency/asset exceptions, Isaac Sim versus kit-less Newton distinction | Current development branch is not a frozen recommended dependency; no install or runtime estimate |
| S11 | ggml-org llama.cpp repository and server README | Local runtime, server interfaces and JSON/schema facilities; MIT runtime designation | Model weights have their own terms; none downloaded or evaluated; structured output still needs external checking |
| S12 | Eon Systems, *How the Eon Team Produced a Virtual Embodied Fly*, 10 March 2026 | Primary technical account, controller/coupling qualifications and limitations | Company-authored account, not independent validation; does not establish wiring-only sufficiency |

## Primary locations

S1: https://say-can.github.io/ ; paper record https://arxiv.org/abs/2204.01691

S2: https://arxiv.org/abs/2107.04034 ; https://ashish-kmr.github.io/rma-legged-robots/

S3: https://arxiv.org/abs/1407.3501 ; https://www.nature.com/articles/nature14422

S4: https://arxiv.org/abs/2301.04104 ; https://danijar.com/project/dreamerv3/ ; publication metadata https://www.nature.com/articles/s41586-025-08744-2

S5: https://arxiv.org/abs/0710.3742

S6: https://mujoco.readthedocs.io/en/stable/python.html ; https://mujoco.readthedocs.io/en/stable/programming/simulation.html ; https://pypi.org/project/mujoco/3.3.7/

S7: https://github.com/Farama-Foundation/Gymnasium

S8: https://github.com/bulletphysics/bullet3 ; https://github.com/bulletphysics/bullet3/blob/master/LICENSE.txt

S9: https://github.com/cyberbotics/webots

S10: https://github.com/isaac-sim/IsaacLab

S11: https://github.com/ggml-org/llama.cpp ; https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

S12: https://eon.systems/updates/embodied-brain-emulation

## Reading order for implementation

Start with the package's executed experiment and interface contracts. Read MuJoCo's stepping/state documentation before the parity adapter. Read RMA and the Cully work for adaptation architecture, then SayCan for the language/skill boundary. Dreamer and changepoint modeling become implementation candidates only after the simpler baseline's failure pattern makes their added complexity useful.

## Scope of the simulator recommendation

The engine license is not automatically the asset, dependency, model-weight, or deployment-service license. Pin each selected component before installation or reuse. The code returned here contains original small XML models rather than redistributed third-party robot assets. No price, hardware purchase, biological platform, or claim of legal compliance is certified by this ledger.
