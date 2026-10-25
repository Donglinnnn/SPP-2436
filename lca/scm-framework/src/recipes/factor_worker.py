"""Isolated Brightway calculation from read-only processed packages, JSON in/out."""
import contextlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile


def main():
    request = json.load(sys.stdin)
    with tempfile.TemporaryDirectory(prefix='scm-recipe-bw-') as folder:
        os.environ['BRIGHTWAY2_DIR'] = folder
        os.environ['BRIGHTWAY2_OUTPUT_DIR'] = folder
        with contextlib.redirect_stdout(sys.stderr):
            import bw2calc as bc
            import bw2data as bd
            import numpy as np
            if not Path(bd.projects.dir).resolve().is_relative_to(Path(folder).resolve()):
                raise RuntimeError('Brightway did not use the isolated temporary project directory')
            packages = [Path(p) for p in request['packages']]
            records = request['records']
            elementary_records = request.get('elementary_records', [])
            if not records:
                raise ValueError('At least one selected activity is required')
            lca = bc.LCA({int(records[0]['id']): 1}, data_objs=packages)
            lca.lci(factorize=True)
            lca.lcia()
            if not lca.characterization_matrix.nnz:
                raise ValueError('Configured LCIA package has no characterization factors')
            scores = {}
            residuals = []
            for record in records:
                lca.redo_lcia({int(record['id']): 1})
                score = float(lca.score)
                residual = float(np.max(np.abs(lca.technosphere_matrix @ lca.supply_array - lca.demand_array)))
                if not math.isfinite(score) or residual > 1e-7:
                    raise ValueError('Non-finite score or failed linear-system residual')
                scores[record['code']] = score
                residuals.append(residual)
            elementary_scores = {}
            for record in elementary_records:
                index = lca.dicts.biosphere[int(record['id'])]
                row = lca.characterization_matrix.getrow(index)
                if any(column != index for column in row.indices):
                    raise ValueError('LCIA characterization matrix is not diagonal for the selected emission')
                factor = float(lca.characterization_matrix[index, index])
                if not math.isfinite(factor):
                    raise ValueError('Non-finite elementary characterization factor')
                elementary_scores[record['code']] = factor
        print(json.dumps(dict(scores=scores, elementary_scores=elementary_scores,
            validation=dict(method_has_characterization=True,
            max_absolute_solver_residual=max(residuals, default=0), original_database_written=False))))


if __name__ == '__main__':
    main()
