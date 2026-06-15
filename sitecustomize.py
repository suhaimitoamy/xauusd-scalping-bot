try:
    from src.brain_runtime_patches import apply_patches
    apply_patches()
except Exception:
    pass
