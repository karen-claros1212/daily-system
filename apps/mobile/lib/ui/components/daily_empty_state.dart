// ─── Daily Empty State ─────────────────────────────────────────────
// Empty state with illustration placeholder and CTA.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';
import 'daily_primary_button.dart';

class DailyEmptyState extends StatelessWidget {
  final String title;
  final String message;
  final IconData? icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  const DailyEmptyState({
    super.key,
    required this.title,
    required this.message,
    this.icon,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(DailyTokens.shapeLG),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon ?? Icons.inbox_outlined,
              size: 56,
              color: DailyTokens.outlineVariant,
            ),
            const SizedBox(height: DailyTokens.shapeMD),
            Text(
              title,
              style: const TextStyle(
                fontSize: 18, fontWeight: FontWeight.w600,
                color: DailyTokens.textPrimary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: DailyTokens.shapeSM),
            Text(
              message,
              style: const TextStyle(fontSize: 14, color: DailyTokens.outlineVariant),
              textAlign: TextAlign.center,
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: DailyTokens.shapeMD),
              DailyPrimaryButton(
                label: actionLabel!,
                onPressed: onAction!,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
