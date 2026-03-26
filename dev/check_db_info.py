import sqlite3
conn = sqlite3.connect('db/knowledge.db')
print('sim_errors_v2 schema:')
for row in conn.execute("SELECT sql FROM sqlite_master WHERE name='sim_errors_v2'"):
    print(row[0])
print()
total = conn.execute('SELECT COUNT(*) FROM sim_errors_v2').fetchone()[0]
print(f'Total records: {total}')
need = conn.execute("""SELECT COUNT(*) FROM sim_errors_v2 
WHERE (physics_cause IS NULL OR physics_cause = '') 
   OR (code_cause IS NULL OR code_cause = '')""").fetchone()[0]
print(f'Needing enrichment: {need}')
print()
print('Sample records:')
rows = conn.execute("""SELECT id, error_class, error_type, error_message, symptom, 
    trigger_code, run_mode, device_type, resolution, pml_thickness, wavelength_um, dim,
    uses_adjoint, physics_cause, code_cause, root_cause_chain
FROM sim_errors_v2 
WHERE (physics_cause IS NULL OR physics_cause = '')
ORDER BY id LIMIT 3""").fetchall()
for row in rows:
    print(f'  id={row[0]}, error_class={row[1]}, error_type={row[2]}')
    print(f'  error_message={str(row[3])[:150]}')
    print(f'  symptom={str(row[4])[:100]}')
    print(f'  trigger_code={str(row[5])[:100] if row[5] else None}')
    print(f'  run_mode={row[6]}, device_type={row[7]}, resolution={row[8]}')
    print(f'  pml_thickness={row[9]}, wavelength_um={row[10]}, dim={row[11]}')
    print(f'  physics_cause={row[13]}, code_cause={row[14]}')
    print()
conn.close()
