# Routing

Explicit `skillshelf run --agent` selection wins. Otherwise a deterministic router may direct a high-confidence single-domain task at confidence 0.90 or above. Ambiguous or multi-specialist work goes through SkillShelfMaster. Independent reads may run concurrently; shared-file work is serial.
