// ─── Daily Metric Card ─────────────────────────────────────────────
// Compact card for displaying a single metric with label and value.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailyMetricCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData? icon;
  final Color? valueColor;
  final Color? bgColor;
  final VoidCallback? onTap;

  const DailyMetricCard({
    super.key,
    required this.label,
    required this.value,
    this.icon,
    this.valueColor,
    this.bgColor,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final card = Material(
      color: bgColor ?? DailyTokens.surface,
      borderRadius: BorderRadius.circular(DailyTokens.shapeLG),
      child: InkWell(
        borderRadius: BorderRadius.circular(DailyTokens.shapeLG),
        onTap: onTap,
        child: Container(
          decoration: BoxDecoration(
            color: bgColor ?? DailyTokens.surface,
            borderRadius: BorderRadius.circular(DailyTokens.shapeLG),
            border: Border.all(color: DailyTokens.surfaceVariant, width: 0.5),
          ),
          child: Padding(
            padding: const EdgeInsets.all(DailyTokens.shapeMD),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: DailyTokens.spacingXS),
                    child: Icon(icon, size: 20, color: DailyTokens.outlineVariant),
                  ),
                Text(
                  label,
                  style: const TextStyle(
                    fontSize: 12, fontWeight: FontWeight.w500,
                    color: DailyTokens.outlineVariant,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: TextStyle(
                    fontSize: 20, fontWeight: FontWeight.w700,
                    color: valueColor ?? DailyTokens.textPrimary,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    if (onTap != null) {
      return card;
    }
    return MergeSemantics(child: card);
  }
}
