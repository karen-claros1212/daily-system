// ─── Daily Error State ─────────────────────────────────────────────
// Recoverable error with explanation and retry.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';
import 'daily_primary_button.dart';

class DailyErrorState extends StatelessWidget {
  final String title;
  final String message;
  final String actionLabel;
  final VoidCallback onRetry;
  final bool isNetworkError;

  const DailyErrorState({
    super.key,
    required this.title,
    required this.message,
    required this.actionLabel,
    required this.onRetry,
    this.isNetworkError = false,
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
              isNetworkError ? Icons.wifi_off : Icons.error_outline,
              size: 48,
              color: DailyTokens.error,
            ),
            const SizedBox(height: DailyTokens.shapeMD),
            Text(
              title,
              style: const TextStyle(
                fontSize: 16, fontWeight: FontWeight.w600,
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
            const SizedBox(height: DailyTokens.shapeMD),
            DailyPrimaryButton(
              label: actionLabel,
              onPressed: onRetry,
              icon: Icons.refresh,
            ),
          ],
        ),
      ),
    );
  }
}
