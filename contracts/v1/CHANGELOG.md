# Contract v1 changes

- Draft 1 (initial): request, evidence, prediction request and prediction response.
- Draft 2: added snapshot, comparison and worker result. The evidence and request schemas are unchanged.
- Draft 3: schema ids are absolute URIs under schemas.upgradeguard.invalid (a reserved name that never resolves) so strict validators accept them. The references between files are unchanged.
- Draft 4: added the explanation graph schema (nodes, edges, findings and limitations that explain a finished report). Nothing else changed. Java and ML keep their own copies; only Java uses it.
