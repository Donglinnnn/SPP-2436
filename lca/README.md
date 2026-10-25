# SPP LCA group

[← SPP 2436 home](../README.md)

This area collects selected research code for life-cycle assessment in the context of SPP 2436 *Net-Zero Concrete*. It is not the complete output of the [SPP LCA working group](https://www.wib.tu-darmstadt.de/spp2436/coordination_researchers/working_groups/life_cycle_assesment/lca_working_group.en.jsp) or an official programme service.

## Current project

### [SCM LCA framework website](scm-framework/README.md)

A local website for describing waste-derived supplementary cementitious material (SCM) processing routes, calculating foreground inventories and climate impacts, saving SCM materials, and using them in concrete, mortar, or paste recipes. [Open the code and setup guide](scm-framework/README.md).

| Area | Location |
| --- | --- |
| Website interface | [frontend](scm-framework/frontend/) |
| SCM process and formula code | [src/calculation](scm-framework/src/calculation/) |
| Mix recipes and background LCA | [src/recipes](scm-framework/src/recipes/) |
| Installation and configuration | [SCM framework README](scm-framework/README.md) |

The software needs a separately configured licensed background database for full LCIA. No ecoinvent data, account credentials, local project history, or paper-specific validation archives are included.
