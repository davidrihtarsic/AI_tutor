# Migracija na tečaje (v1.2)

v1.2 loči uporabnika od tečaja. Isti učenec je lahko vpisan v več tečajev. Novi pogovori so shranjeni kot `data/sessions/<course_id>/YYYY-MM-DD_HHMM.jsonl`; ob več sejah v isti minuti se dodajo `_02`, `_03`, ...

Pred migracijo ustavi strežnik in naredi:

```bash
python scripts/migrate_v12_courses.py
python scripts/migrate_v12_courses.py --apply
```

Prvi ukaz je samo pregled (dry-run). `--apply` pred spremembo ustvari varnostno kopijo v `data/backups/v12_courses_<timestamp>/`.

Stari `class` se pretvori v začetni tečaj (npr. `ELORA26` -> `elora26`). Po migraciji lahko v učiteljskem dashboardu dodaš nove tečaje, npr. `robotika26` in `elektronika26`. Učenec z obstoječim računom se v dodatni tečaj vpiše z istim uporabniškim imenom in geslom ter kodo novega tečaja.
