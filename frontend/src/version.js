// Single source of truth for the frontend version and brand.
//
// CRA's ModuleScopePlugin forbids importing ../package.json from src/, so this
// literal is the canonical frontend value. Keep it in sync with the root
// version.py and package.json via `python scripts/bump_version.py X.Y.Z`
// (tests/test_version_consistency.py guards against drift).
export const APP_VERSION = '5.0.0';
export const APP_NAME = 'Agency Core';
export const APP_TAGLINE = 'Autonomous AI Platform';

// Human-facing label, e.g. "Agency Core v5.0".
export const APP_LABEL = `${APP_NAME} v${APP_VERSION.split('.').slice(0, 2).join('.')}`;
