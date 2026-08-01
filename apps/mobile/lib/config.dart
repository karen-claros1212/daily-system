// ─── Config / Feature flags ──────────────────────────────────────

/// Demo flag — set to false to hide demo info in release builds.
/// Compile-time: `--dart-define=DAILY_DEMO=true`.
const bool kDailyDemo = bool.fromEnvironment('DAILY_DEMO', defaultValue: false);
