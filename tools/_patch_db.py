import sqlite3
DB = '/app/db/knowledge.db'
updates = [
    ('GaussianSource', '/static/results/concept_GaussianSource.png'),
    ('adjoint_objective_normalization', '/static/results/concept_adjoint_objective_normalization.png'),
    ('adjoint_source_correct_physics', '/static/results/concept_adjoint_source_correct_physics.png'),
    ('adjoint_symmetry_constraint_pitfall', '/static/results/concept_adjoint_symmetry_constraint_pitfall.png'),
    ('adjoint_beta_schedule_full', '/static/results/concept_adjoint_beta_schedule_full.png'),
    ('metagrating_2d_diffraction_efficiency', '/static/results/concept_metagrating_2d_diffraction_efficiency.png'),
]
conn = sqlite3.connect(DB)
for name, img in updates:
    conn.execute(
        "UPDATE concepts SET result_images=?, result_status=? WHERE name=?",
        (img, 'success', name)
    )
    print('OK:', name)
conn.commit()
conn.close()
print('Done')
