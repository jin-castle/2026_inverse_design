import subprocess

updates = [
    ("GaussianSource", "/static/results/concept_GaussianSource.png"),
    ("adjoint_objective_normalization", "/static/results/concept_adjoint_objective_normalization.png"),
    ("adjoint_source_correct_physics", "/static/results/concept_adjoint_source_correct_physics.png"),
    ("adjoint_symmetry_constraint_pitfall", "/static/results/concept_adjoint_symmetry_constraint_pitfall.png"),
    ("adjoint_beta_schedule_full", "/static/results/concept_adjoint_beta_schedule_full.png"),
    ("metagrating_2d_diffraction_efficiency", "/static/results/concept_metagrating_2d_diffraction_efficiency.png"),
]

for name, img_url in updates:
    sql = "UPDATE concepts SET result_images='{}', result_status='success' WHERE name='{}';".format(img_url, name)
    cmd = ["docker","exec","meep-kb-meep-kb-1","sqlite3","/app/db/knowledge.db", sql]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        print("OK:", name)
    else:
        print("ERR:", name, r.stderr[:150])
